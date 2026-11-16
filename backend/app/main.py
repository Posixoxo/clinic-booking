from fastapi import FastAPI, Depends, HTTPException, Query, Header, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Optional, List, Dict
import hashlib
import json
from collections import defaultdict

from app.database.connection import get_db, engine, Base, get_settings
from app.models import Slot, Booking, IdempotencyKey
from app.schemas import (
    ResetRequest,
    SlotWithAvailability,
    NewBooking,
    BookingOut,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clinic Booking API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()

# Simple in-memory rate limiter: email → list of timestamps
rate_limit_store: Dict[str, list] = defaultdict(list)
RATE_LIMIT = 5          # max attempts
RATE_WINDOW = 60        # seconds


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None)
):
    # Allow CORS preflight requests to pass
    if request.method == "OPTIONS":
        return None

    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Unauthorized"}
        )
    return x_api_key


def make_request_hash(payload: dict) -> str:
    normalized = {
        "slot_id": payload.get("slot_id", "").strip(),
        "name": payload.get("name", "").strip(),
        "email": payload.get("email", "").strip().lower(),
    }
    raw = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def check_rate_limit(email: str) -> Optional[int]:
    """
    Returns None if allowed.
    Returns seconds to wait if rate limited.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=RATE_WINDOW)

    # Clean old attempts
    attempts = [t for t in rate_limit_store[email] if t > window_start]
    rate_limit_store[email] = attempts

    if len(attempts) >= RATE_LIMIT:
        # Calculate how many seconds until the oldest attempt expires
        oldest = min(attempts)
        retry_after = int((oldest + timedelta(seconds=RATE_WINDOW) - now).total_seconds()) + 1
        return max(retry_after, 1)

    # Record this attempt
    rate_limit_store[email].append(now)
    return None


@app.get("/")
def health():
    return {"status": "ok", "message": "Clinic Booking API is running"}


@app.post("/reset", status_code=200, dependencies=[Depends(verify_api_key)])
def reset_slots(payload: ResetRequest, db: Session = Depends(get_db)):
    db.execute(delete(Booking))
    db.execute(delete(Slot))
    db.execute(delete(IdempotencyKey))
    rate_limit_store.clear()          # also clear rate limits on reset

    for s in payload.slots:
        slot = Slot(
            id=s.id,
            provider=s.provider,
            start=s.start,
            end=s.end,
        )
        db.add(slot)

    db.commit()
    return {"message": "ok"}


@app.get("/slots", response_model=List[SlotWithAvailability], dependencies=[Depends(verify_api_key)])
def list_slots(
    provider: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = select(Slot).order_by(Slot.start.asc())

    if provider:
        query = query.where(Slot.provider == provider)

    slots = db.scalars(query).all()

    result = []
    for slot in slots:
        confirmed = db.scalar(
            select(Booking).where(
                Booking.slot_id == slot.id,
                Booking.status == "confirmed"
            )
        )
        result.append(
            SlotWithAvailability(
                id=slot.id,
                provider=slot.provider,
                start=slot.start,
                end=slot.end,
                available=confirmed is None,
            )
        )

    return result


@app.post("/bookings", response_model=BookingOut, status_code=201, dependencies=[Depends(verify_api_key)])
def create_booking(
    payload: NewBooking,
    response: Response,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    name = payload.name.strip()
    email = payload.email.strip().lower()
    slot_id = payload.slot_id.strip()

    if not name or not email or not slot_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing or empty required field"}
        )

    # ----- Level 5: Rate limiting -----
    retry_after = check_rate_limit(email)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many attempts for this email"},
            headers={"Retry-After": str(retry_after)}
        )

    # ----- Level 4: Idempotency -----
    request_hash = make_request_hash({
        "slot_id": slot_id,
        "name": name,
        "email": email,
    })

    if idempotency_key:
        existing_key = db.get(IdempotencyKey, idempotency_key)

        if existing_key:
            if existing_key.request_hash != request_hash:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "Idempotency-Key reused with a different body"}
                )
            booking = db.get(Booking, existing_key.booking_id)
            if booking:
                return booking

    # ----- Normal booking logic -----
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail={"error": "slot not found"})

    now = datetime.now(timezone.utc)
    if slot.start <= now:
        raise HTTPException(status_code=400, detail={"error": "slot has already started"})

    existing = db.scalar(
        select(Booking).where(
            Booking.slot_id == slot_id,
            Booking.status == "confirmed"
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail={"error": "slot already booked"})

    booking = Booking(
        id=str(uuid4()),
        slot_id=slot_id,
        name=name,
        email=email,
        status="confirmed",
    )
    db.add(booking)
    db.flush()

    if idempotency_key:
        db.add(IdempotencyKey(
            key=idempotency_key,
            request_hash=request_hash,
            booking_id=booking.id,
        ))

    db.commit()
    db.refresh(booking)
    return booking


@app.get("/bookings/{booking_id}", response_model=BookingOut, dependencies=[Depends(verify_api_key)])
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail={"error": "booking not found"})
    return booking


@app.delete("/bookings/{booking_id}", response_model=BookingOut, dependencies=[Depends(verify_api_key)])
def cancel_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)

    if not booking:
        raise HTTPException(status_code=404, detail={"error": "booking not found"})

    if booking.status == "cancelled":
        raise HTTPException(status_code=409, detail={"error": "already cancelled"})

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)
    return booking


@app.get("/bookings", dependencies=[Depends(verify_api_key)])
def list_person_bookings(
    email: str = Query(...),
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    query = (
        select(Booking)
        .where(Booking.email == email)
        .order_by(Booking.created_at.asc(), Booking.id.asc())
    )

    if cursor:
        cursor_booking = db.get(Booking, cursor)
        if cursor_booking:
            query = query.where(
                (Booking.created_at > cursor_booking.created_at) |
                (
                    (Booking.created_at == cursor_booking.created_at) &
                    (Booking.id > cursor_booking.id)
                )
            )

    bookings = db.scalars(query.limit(limit + 1)).all()

    next_cursor = None
    if len(bookings) > limit:
        next_cursor = bookings[limit - 1].id
        bookings = bookings[:limit]

    return {
        "bookings": bookings,
        "next_cursor": next_cursor
    }