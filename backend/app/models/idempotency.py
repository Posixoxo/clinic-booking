from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from app.database.connection import Base

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String, primary_key=True, index=True)
    request_hash = Column(String, nullable=False)   # hash of the body
    booking_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())