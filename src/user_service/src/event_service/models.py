from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    when = Column(DateTime, nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
