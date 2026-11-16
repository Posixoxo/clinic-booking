from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database.connection import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, index=True)
    slot_id = Column(String, ForeignKey("slots.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="confirmed")  # confirmed | cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())