import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    when: datetime
    source: str
    type: str
    payload: dict
    user: Optional[uuid.UUID] = None


class EventRead(BaseModel):
    id: int
    when: datetime
    source: str
    type: str
    payload: dict
    user: Optional[uuid.UUID] = None
    model_config = ConfigDict(from_attributes=True)
