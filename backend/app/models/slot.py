from sqlalchemy import Column, String, DateTime
from app.database.connection import Base

class Slot(Base):
    __tablename__ = "slots"

    id = Column(String, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    start = Column(DateTime(timezone=True), nullable=False)
    end = Column(DateTime(timezone=True), nullable=False)