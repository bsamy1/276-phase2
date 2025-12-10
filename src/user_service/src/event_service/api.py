import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.database import get_db

from .models import Event
from .schemas import EventCreate, EventRead

router = APIRouter()


# POST endpoint: create event
@router.post("/v2/events/", response_model=EventRead)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    try:
        db_event = Event(
            when=event.when,
            source=event.source,
            type=event.type,
            payload=event.payload,
            user_id=event.user,
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create event: {e}")


# GET endpoint: query events with optional filters
@router.get("/v2/events/", response_model=List[EventRead])
def get_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    user: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Event)

    if event_type:
        query = query.filter(Event.type == event_type)
    if source:
        query = query.filter(Event.source == source)
    if before:
        query = query.filter(Event.when <= before)
    if after:
        query = query.filter(Event.when >= after)
    if user:
        query = query.filter(Event.user_id == user)

    # Order newest events first
    return query.order_by(Event.when.desc()).all()
