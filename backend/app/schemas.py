from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List

class SlotBase(BaseModel):
    id: str
    provider: str
    start: datetime
    end: datetime

class SlotCreate(SlotBase):
    pass

class SlotWithAvailability(SlotBase):
    available: bool

    class Config:
        from_attributes = True

class NewBooking(BaseModel):
    slot_id: str
    name: str
    email: EmailStr

class BookingOut(BaseModel):
    id: str
    slot_id: str
    name: str
    email: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ResetRequest(BaseModel):
    slots: List[SlotCreate]

class ErrorResponse(BaseModel):
    error: str