import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from event_service.api import router
from event_service.models import Base, Event
from shared.database import get_db


@pytest.fixture(scope="function")
def engine():
    # Use SQLite in-memory DB for tests
    engine = create_engine("sqlite:///:memory:?check_same_thread=False")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def session(engine):
    conn = engine.connect()
    conn.begin()

    # Keep your percentile extension setup for compatibility
    try:
        conn.connection.enable_load_extension(True)
        conn.connection.load_extension("tools/percentile")
        conn.connection.enable_load_extension(False)
    except Exception:
        # Ignore if not available (e.g., on Windows)
        pass

    db = Session(bind=conn)
    yield db
    db.rollback()
    conn.close()


@pytest.fixture(scope="function")
def client(session):
    """Create a FastAPI TestClient with the same dependency override style."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c


# ----------------------------------------------------------------
# Actual Tests
# ----------------------------------------------------------------

def test_create_event_success(client, session):
    """Check that a new event can be created and stored correctly."""
    event_data = {
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "http://localhost/test",
        "type": "click",
        "payload": {"button": "subscribe"},
        "user": str(uuid.uuid4()),
    }

    resp = client.post("/v2/events/", json=event_data)
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "click"
    assert body["source"] == "http://localhost/test"
    assert "id" in body

    # Confirm it was stored in DB
    db_event = session.query(Event).first()
    assert db_event is not None
    assert db_event.type == "click"


def test_get_events_returns_list(client):
    """Ensure /v2/events returns a list of events in reverse time order."""
    now = datetime.now(timezone.utc)

    for i in range(3):
        client.post(
            "/v2/events/",
            json={
                "when": (now + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "source": "http://localhost/blog",
                "type": f"event-{i}",
                "payload": {"index": i},
            },
        )

    resp = client.get("/v2/events/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["when"] >= data[-1]["when"]  # newest first


def test_get_events_with_filters(client):
    """Check filtering by type and time range."""
    now = datetime.now(timezone.utc)
    client.post(
        "/v2/events/",
        json={
            "when": now.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "http://localhost/blog",
            "type": "text-highlight",
            "payload": {"key": "A"},
        },
    )
    client.post(
        "/v2/events/",
        json={
            "when": (now + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "source": "http://localhost/blog",
            "type": "link-out",
            "payload": {"key": "B"},
        },
    )

    # Filter by event_type
    resp = client.get("/v2/events/?event_type=text-highlight")
    assert resp.status_code == 200
    results = resp.json()
    assert all(ev["type"] == "text-highlight" for ev in results)

    # Filter by time range
    after = (now - timedelta(minutes=1)).isoformat()
    before = (now + timedelta(minutes=2)).isoformat()
    resp = client.get(f"/v2/events/?after={after}&before={before}")
    assert resp.status_code == 200
    filtered = resp.json()
    for ev in filtered:
        event_time = datetime.fromisoformat(ev["when"])
        assert datetime.fromisoformat(after) <= event_time <= datetime.fromisoformat(before)


def test_create_event_invalid_data(client):
    """Ensure invalid payload returns a 422 validation error."""
    resp = client.post("/v2/events/", json={"type": "click"})
    assert resp.status_code == 422
