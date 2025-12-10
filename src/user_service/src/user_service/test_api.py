import asyncio
import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from PIL import Image
from pytest_postgresql import factories
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import user_service.api as api
from shared.database import Base
from user_service.analytics import redis as analytics_redis

from .api import AuthModel, app
from .models.auth import AuthRepository, get_auth_repository
from .models.friends import FriendshipRepository, get_friendship_repository
from .models.session_analytics import (
    SessionAnalyticsRepository,
    get_session_analytics_repository,
)
from .models.user import UserRepository, get_user_repository

# Postgres-specific testing database
if os.getenv("CI"):  # ignore if we're testing in git
    pass
else:
    postgresql_in_docker = factories.postgresql_noproc(
        host="10.5.0.2", dbname="test-api", user="admin", password="admin"
    )
    postgresql = factories.postgresql("postgresql_in_docker", dbname="test-api")


@pytest.fixture(scope="function")
def postgres_engine(postgresql):
    engine = create_engine(
        f"postgresql+psycopg2://{postgresql.info.user}:{postgresql.info.password}@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def postgres_session(postgres_engine):
    conn = postgres_engine.connect()
    conn.begin()
    db = Session(bind=conn)
    yield db
    db.rollback()
    conn.close()


@pytest.fixture(scope="function")
def postgres_client(postgres_session):
    app.dependency_overrides[get_user_repository] = lambda: get_user_repository(postgres_session)
    app.dependency_overrides[get_auth_repository] = lambda: get_auth_repository(postgres_session)
    app.dependency_overrides[get_session_analytics_repository] = (
        lambda: get_session_analytics_repository(postgres_session)
    )
    app.dependency_overrides[get_friendship_repository] = lambda: get_friendship_repository(
        postgres_session
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _mock_redis():
    """
    Avoid talking to real Redis during tests.

    We replace the analytics.redis helpers (get_redis, is_active, mark_event)
    with test-friendly stubs that never open a network connection.
    """

    class DummyRedis:
        async def exists(self, *args, **kwargs):
            return False

        async def sismember(self, *args, **kwargs):
            return False

        async def sadd(self, *args, **kwargs):
            return 1

        async def srem(self, *args, **kwargs):
            return 1

    async def mock_get_redis():
        # Whatever calls get_redis() gets a harmless in-memory fake client
        return DummyRedis()

    async def mock_is_active(user, r=None):
        # Pretend no one is active; allows auth creation to proceed
        return False

    async def mock_mark_event(user, r=None):
        # Do nothing for analytics in tests
        return None

    # Patch the *actual module* used in the stack trace: analytics.redis
    analytics_redis.get_redis = MagicMock(return_value=mock_get_redis)
    analytics_redis.is_active = MagicMock(return_value=mock_is_active)
    analytics_redis.mark_event = MagicMock(return_value=mock_mark_event)

    """monkeypatch.setattr(analytics_redis, "get_redis", fake_get_redis, raising=False)
    monkeypatch.setattr(analytics_redis, "is_active", fake_is_active, raising=False)
    monkeypatch.setattr(analytics_redis, "mark_event", fake_mark_event, raising=False)"""


@pytest_asyncio.fixture(scope="function")
@patch("user_service.models.session_analytics.date")
@patch("user_service.models.session_analytics.datetime")
async def created_analytics(mock_datetime, mock_date, postgres_session):
    session_analytics_repo = get_session_analytics_repository(postgres_session)
    # Create stats for multiple hours across today
    new_start = datetime.now(timezone.utc)
    for i in range(10):
        new_start = datetime(
            year=new_start.year,
            month=new_start.month,
            day=new_start.day,
            hour=i,
            minute=0,
            second=0,
            tzinfo=new_start.tzinfo,
        )

        mock_date.today.return_value = new_start.date()
        mock_datetime.now.return_value = new_start

        # calls sqlalchemy's func.now(), which isn't mocked
        session = await session_analytics_repo.create()

        # updating session_start to get around being unable to mock func.now()
        session.session_start = new_start

        new_end = new_start + timedelta(hours=1)
        mock_date.today.return_value = new_end.date()
        mock_datetime.now.return_value = new_end

        # only calls datetime.now()
        await session_analytics_repo.end(session_id=session.id)

    # Create stats across multiple days 1-10 of this month
    for i in range(1, 11):
        new_start = datetime(
            year=new_start.year,
            month=new_start.month,
            day=i,
            hour=new_start.hour,
            minute=new_start.minute,
            second=new_start.second,
            tzinfo=new_start.tzinfo,
        )

        mock_datetime.now.return_value = new_start
        mock_date.today.return_value = new_start.date()

        # calls sqlalchemy's func.now(), which isn't mocked
        session = await session_analytics_repo.create()

        # updating session_start to get around being unable to mock func.now()
        session.session_start = new_start

        mock_datetime.now.return_value = new_end
        mock_date.today.return_value = new_end.date()

        # only calls datetime functions, which are mocked, so no need to update
        await session_analytics_repo.end(session_id=session.id)

    postgres_session.commit()


@pytest.fixture(scope="function")
def engine():
    engine = create_engine("sqlite:///:memory:?check_same_thread=False")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def session(engine):
    conn = engine.connect()
    conn.begin()
    db = Session(bind=conn)
    yield db
    db.rollback()
    conn.close()


@pytest.fixture(scope="function")
def repo(session):
    yield UserRepository(session)


@pytest.fixture(scope="function")
def client(repo):
    app.dependency_overrides[get_user_repository] = lambda: repo
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def created_user(session):
    user_data = {"name": "foo", "email": "foo@example.com", "password": "secret123"}
    session.execute(
        text(
            "INSERT INTO users (name, email, password) "
            "VALUES (:name, :email, :password)"
        ),
        user_data,
    )
    session.commit()
    return user_data


# used for get avatar only
@pytest.fixture
def v2_created_avatar(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    img_bytes = make_test_image()
    response = v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    assert response.status_code == 200
    return uid


def test_read_user(client, created_user):
    response = client.get("/users/foo")

    user_data = response.json()["user"]

    assert response.status_code == 200
    assert user_data["name"] == created_user["name"]
    assert user_data["email"] == created_user["email"]
    assert "id" in user_data  # ignore auto-generated DB id


def test_create_user(client):
    user_json = {"name": "foobar", "email": "foo@bar.com", "password": "secret123"}
    response_json = {
        "id": 1,
        "name": "foobar",
        "email": "foo@bar.com",
        "password": "********",
    }
    response = client.post(
        "/users/",
        json=user_json,
    )
    assert response.status_code == 201
    assert response.json() == {"user": response_json}


def test_create_existing_user(client, created_user):
    response = client.post(
        "/users/",
        json=created_user,
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "User or email already exists"}


def test_upload_avatar(client):
    img = Image.new("RGB", (512, 512), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    uid = 1
    response = client.post(
        f"/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Avatar uploaded"}


def test_get_avatar(client):
    uid = 1
    response = client.get(f"/users/{uid}/avatar")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")


def test_upload_invalid_avatar_file(client):
    file_data = io.BytesIO(b"not an image")
    response = client.post(
        "/users/1/avatar",
        files={"file": ("fake.txt", file_data, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported file type"}


def test_get_nonexistent_avatar(client):
    response = client.get("/users/999/avatar")
    assert response.status_code == 404
    assert response.json() == {"detail": "Avatar not found"}


def test_avatar_resized(client):
    img = Image.new("RGB", (1000, 500), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    uid = 1
    client.post(
        f"/users/{uid}/avatar",
        files={"file": ("avatar.jpeg", img_bytes, "image/jpeg")},
    )

    avatar_path = Path("avatars") / f"{uid}.jpg"
    with Image.open(avatar_path) as avatar_img:
        assert max(avatar_img.size) <= 256


def test_delete_user(client, created_user):
    # check if user exists
    response = client.get(f"/users/{created_user['name']}")
    assert response.status_code == 200
    assert response.json()

    # delete user
    response = client.post(
        "/users/delete",
        json=created_user,
    )
    assert response.status_code == 202
    assert response.json() == {"detail": f"'{created_user['name']}' deleted"}

    # check if user is gone
    response = client.get(f"/users/{created_user['name']}")
    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_delete_nonexistent_user(client):
    fake_user_data = {
        "name": "foo",
        "email": "foo@bar.com",
        "password": "secret123",
    }
    response = client.post(
        "/users/delete",
        json=fake_user_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "No users to delete"}


# v2 tests
def make_test_image(width=512, height=512, color="blue"):
    img = Image.new("RGB", (width, height), color=color)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    return img_bytes


# create a temporary directory for avatars
@pytest.fixture
def avatar_dir(tmp_path):
    avatar_path = tmp_path / "avatars"
    avatar_path.mkdir(exist_ok=True)
    api.AVATAR_DIR = avatar_path
    return avatar_path


# cleans avatar directory for each v2 test
@pytest.fixture(autouse=True)
def clean_avatar_dir(request, tmp_path):
    # skip v1 tests
    if not request.node.name.startswith("test_v2_"):
        return

    avatar_path = tmp_path / "avatars"
    if avatar_path.exists():
        for file in avatar_path.iterdir():
            file.unlink()
    avatar_path.mkdir(exist_ok=True)
    api.AVATAR_DIR = avatar_path
    return avatar_path


@pytest.fixture
def session_analytics_repo(session):
    yield SessionAnalyticsRepository(session)


@pytest.fixture
def auth_repo(session):
    yield AuthRepository(session)


@pytest.fixture
def friendship_repo(session):
    yield FriendshipRepository(session)


@pytest.fixture
def v2_client(repo, auth_repo, friendship_repo, session_analytics_repo):
    app.dependency_overrides[get_user_repository] = lambda: repo
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    app.dependency_overrides[get_session_analytics_repository] = lambda: session_analytics_repo
    app.dependency_overrides[get_friendship_repository] = lambda: friendship_repo
    with TestClient(app) as client:
        yield client


@pytest.fixture
def v2_created_user(repo):
    user_data = {
        "name": "v2user",
        "email": "v2user@v2user.com",
        "password": "secret123",
    }
    user = asyncio.run(repo.create(**user_data))
    return user


# V2 Tests
@pytest.mark.asyncio
async def test_v2_list_users(v2_client, repo):
    await repo.create("v2user1", "v2user@v2user1.com", "secret123")
    await repo.create("v2user2", "v2user@v2user2.com", "secret123")

    resp = v2_client.get("/v2/users/")
    assert resp.status_code == 200

    data = resp.json()
    users = data["users"]

    seen = {(u["name"], u["email"]) for u in users}
    assert seen == {
        ("v2user1", "v2user@v2user1.com"),
        ("v2user2", "v2user@v2user2.com"),
    }

    for u in users:
        assert set(u.keys()) == {"id", "name", "email"}
        assert isinstance(u["id"], int)


@pytest.mark.asyncio
async def test_get_user_by_id(v2_client, repo, v2_created_user):
    resp = v2_client.get(f"/v2/users/id/{v2_created_user.id}")
    assert resp.status_code == 200
    assert resp.json()["user"] == {
        "id": v2_created_user.id,
        "name": v2_created_user.name,
        "email": v2_created_user.email,
    }


@pytest.mark.asyncio
async def test_get_user_by_name(v2_client, repo, v2_created_user):
    resp = v2_client.get(f"/v2/users/name/{v2_created_user.name}")
    assert resp.status_code == 200
    assert resp.json()["user"] == {
        "id": v2_created_user.id,
        "name": v2_created_user.name,
        "email": v2_created_user.email,
    }


@pytest.mark.asyncio
async def test_v2_create_user(v2_client):
    body = {"name": "alice", "email": "alice@example.com", "password": "pw"}
    r = v2_client.post("/v2/users/", json=body)
    assert r.status_code == 201
    data = r.json()
    assert set(data.keys()) == {"id", "name", "email"}
    assert data["name"] == "alice"
    assert data["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_v2_update_user_fields(v2_client, repo, v2_created_user, v2_created_auth):
    json = {
        "name": "alice2",
        "email": "alice2@example.com",
        "auth": {"user_id": v2_created_user.id, "jwt": v2_created_auth},
    }

    r = v2_client.put(f"/v2/users/{v2_created_user.id}", json=json)
    assert r.status_code in (200, 201)
    data = r.json()
    assert (
        data["id"] == v2_created_user.id
        and data["name"] == "alice2"
        and data["email"] == "alice2@example.com"
    )


@pytest.mark.asyncio
async def test_v2_update_user_password(v2_client, repo, v2_created_user, v2_created_auth):
    body = {
        "new_password": "newpw123",
        "auth": {"user_id": v2_created_user.id, "password": "secret123", "jwt": v2_created_auth},
    }
    r = v2_client.put(f"/v2/users/{v2_created_user.id}", json=body)
    assert r.status_code in (200, 201)


@pytest.mark.asyncio
async def test_v2_delete_user(v2_client, repo, v2_created_user, v2_created_auth):
    body = {"user_id": v2_created_user.id, "jwt": v2_created_auth}
    r = v2_client.request("delete", f"/v2/users/{v2_created_user.id}", json=body)
    assert r.status_code == 202

    r2 = v2_client.get(f"/v2/users/id/{v2_created_user.id}")
    assert r2.status_code == 404


@pytest.fixture
def v2_created_auth(v2_client, v2_created_user):
    time = datetime.now(timezone.utc) + timedelta(minutes=30)
    json = {
        "id": v2_created_user.id,
        "password": "secret123",
        "expiry": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=json)
    return response.json()["jwt"]


@pytest.mark.asyncio
async def test_v2_create_avatar(v2_client, v2_created_user, v2_created_auth, avatar_dir):
    uid = v2_created_user.id
    token = v2_created_auth

    img_bytes = make_test_image()
    response = v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Avatar created"
    assert (avatar_dir / f"{uid}.jpg").exists()


@pytest.mark.asyncio
async def test_v2_create_avatar_already_exists(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    # first upload
    v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", make_test_image(), "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    # second upload
    img_bytes = make_test_image()
    response = v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Avatar already exists"


@pytest.mark.asyncio
async def test_v2_create_avatar_no_jwt(v2_client, v2_created_user):
    uid = v2_created_user.id
    img_bytes = make_test_image()
    response = v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid})},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_v2_get_avatar(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", make_test_image(), "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    response = v2_client.get(f"/v2/users/{uid}/avatar")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")


@pytest.mark.asyncio
async def test_v2_get_avatar_user_not_found(v2_client):
    response = v2_client.get("/v2/users/999/avatar")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_v2_update_avatar(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", make_test_image(), "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    img_bytes = make_test_image(color="green")
    response = v2_client.put(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Avatar updated"


@pytest.mark.asyncio
async def test_v2_update_avatar_not_found(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    img_bytes = make_test_image()
    response = v2_client.put(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", img_bytes, "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Avatar not found"


@pytest.mark.asyncio
async def test_v2_delete_avatar_no_jwt(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", make_test_image(), "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    response = v2_client.request(
        "DELETE",
        f"/v2/users/{uid}/avatar",
        data={"auth": json.dumps({"user_id": uid})},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_v2_delete_avatar(v2_client, v2_created_user, v2_created_auth, avatar_dir):
    uid = v2_created_user.id
    token = v2_created_auth
    v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("avatar.jpg", make_test_image(), "image/jpeg")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )
    response = v2_client.request(
        "DELETE",
        f"/v2/users/{uid}/avatar",
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Avatar deleted"
    assert not (avatar_dir / f"{uid}.jpg").exists()


@pytest.mark.asyncio
async def test_v2_delete_avatar_not_found(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    response = v2_client.request(
        "DELETE",
        f"/v2/users/{uid}/avatar",
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Avatar not found"


@pytest.mark.asyncio
async def test_v2_create_avatar_invalid_file(v2_client, v2_created_user, v2_created_auth):
    uid = v2_created_user.id
    token = v2_created_auth
    file_data = io.BytesIO(b"not an image")
    response = v2_client.post(
        f"/v2/users/{uid}/avatar",
        files={"file": ("fake.txt", file_data, "text/plain")},
        data={"auth": json.dumps({"user_id": uid, "jwt": token})},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type"


@pytest.mark.asyncio
async def test_analytics(postgres_client, created_analytics):
    response = postgres_client.get("/v2/analytics")

    assert response.status_code == 200
    assert response.json()


@pytest.mark.asyncio
async def test_analytics_on(postgres_client, created_analytics):
    day = date.today()
    day = date(year=day.year, month=day.month, day=1)

    response = postgres_client.get(f"/v2/analytics?on={day.isoformat()}")

    assert response.status_code == 200
    assert response.json()


@pytest.mark.asyncio
async def test_analytics_since(postgres_client, created_analytics):
    day = date.today()
    day = date(year=day.year, month=day.month, day=1)

    response = postgres_client.get(f"/v2/analytics?since={day.isoformat()}")

    assert response.status_code == 200
    assert response.json()


@pytest.mark.asyncio
async def test_create_auth(v2_client, v2_created_user):
    time = datetime.now(timezone.utc) + timedelta(minutes=30)
    json = {
        "id": v2_created_user.id,
        "password": "secret123",
        "expiry": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=json)

    assert response.status_code == 200
    assert response.json()["jwt"]


@pytest.mark.asyncio
async def test_create_auth_invalid_password(v2_client, v2_created_user):
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    json = {
        "id": v2_created_user.id,
        "password": "wrong",
        "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=json)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid password!"


@pytest.mark.asyncio
async def test_create_existing_auth(v2_client, v2_created_user, v2_created_auth):
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    json = {
        "id": v2_created_user.id,
        "password": "secret123",
        "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=json)

    assert response.status_code == 200
    assert response.json()["jwt"]


@pytest.mark.asyncio
async def test_create_auth_passed_time(v2_client, v2_created_user):
    expiry = datetime.now(timezone.utc) - timedelta(minutes=30)
    json = {
        "id": v2_created_user.id,
        "password": "secret123",
        "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=json)

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Invalid expiry! Expiry time must be some time within the next hour."
    )


@pytest.mark.asyncio
async def test_create_auth_invalid_time(v2_client, v2_created_user):
    expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    json = {
        "id": v2_created_user.id,
        "password": "secret123",
        "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=json)

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Invalid expiry! Expiry time must be some time within the next hour."
    )


@pytest.mark.asyncio
async def test_delete_auth(v2_client, v2_created_auth, v2_created_user, auth_repo):
    auth = await auth_repo.get_by_id(v2_created_user.id)

    response = v2_client.request("delete", "/v2/authentications", json={"jwt": auth.token})

    assert response.status_code == 200
    assert response.json()["detail"] == "Token deleted."


@pytest.mark.asyncio
async def test_authenticate(v2_client, v2_created_auth, v2_created_user, repo, auth_repo):
    auth = await auth_repo.get_by_id(v2_created_user.id)
    req = AuthModel(user_id=v2_created_user.id, jwt=auth.token)

    assert await api.authenticate(req, repo, auth_repo)

    # Test authenticating with just a password
    req.password = "secret123"
    req.jwt = None

    assert await api.authenticate(req, repo, auth_repo)

    # Test with both
    req.jwt = auth.token

    assert await api.authenticate(req, repo, auth_repo)


@pytest.mark.asyncio
async def test_authenticate_invalid_token(
    v2_client, v2_created_auth, v2_created_user, repo, auth_repo
):
    auth = await auth_repo.get_by_id(v2_created_user.id)
    req = AuthModel(user_id=v2_created_user.id, jwt=auth.token)

    await auth_repo.delete(v2_created_user.id)

    assert not await api.authenticate(req, repo, auth_repo)


@pytest.mark.asyncio
async def test_get_friend_requests(v2_client, v2_created_user):
    # Test valid query
    response = v2_client.get(f"/v2/users/{v2_created_user.id}/friend-requests/?q=incoming")

    assert response.status_code == 200
    assert response.json()["requests"] == []

    response = v2_client.get(f"/v2/users/{v2_created_user.id}/friend-requests/?q=outgoing")

    assert response.status_code == 200
    assert response.json()["requests"] == []

    # Test unsupported query
    response = v2_client.get(f"/v2/users/{v2_created_user.id}/friend-requests/?q=bad")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported query. Use q=incoming or q=outgoing"


@pytest.mark.asyncio
async def test_create_friend_request(v2_client, v2_created_user, v2_created_auth, repo, auth_repo):
    auth = await auth_repo.get_by_id(v2_created_user.id)

    uid = v2_created_user.id

    json = {
        "requestor": uid,
        "auth": {"user_id": uid, "jwt": auth.token},
    }

    receiver = await repo.create("alice", "alice@example.com", "pw")
    rid = receiver.id

    # Test without authentication
    response = v2_client.post(
        f"/v2/users/{rid}/friend-requests/", json={"requestor": v2_created_user.id}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized!"

    # Test sending a request to yourself
    response = v2_client.post(f"/v2/users/{uid}/friend-requests/", json=json)

    assert response.status_code == 400
    assert response.json()["detail"] == "Can't send a friend request to yourself."

    # Test sending a request to a non-existent user
    response = v2_client.post("/v2/users/99/friend-requests/", json=json)

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."

    # Test sending a typical response
    response = v2_client.post(f"/v2/users/{rid}/friend-requests/", json=json)

    assert response.status_code == 200
    assert response.json()["request_id"]
    assert response.json()["sender_id"] == uid
    assert response.json()["receiver_id"] == rid
    assert response.json()["status"] == "pending"
    assert response.json()["message"] == f"Friend request sent to {receiver.name}."

    # Test sending a duplicate friend request
    response = v2_client.post(f"/v2/users/{rid}/friend-requests/", json=json)

    assert response.status_code == 400
    assert response.json()["detail"] == "A pending request already exists from you."

    # Test cancelling a friend request without authentication
    response = v2_client.delete(f"/v2/users/{rid}/friend-requests/{uid}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized!"

    # Test cancelling a friend request from the wrong account
    auth = json["auth"]
    auth["user_id"] = 5
    response = v2_client.request("delete", f"/v2/users/{rid}/friend-requests/{uid}", json=auth)

    assert response.status_code == 403
    assert response.json()["detail"] == "You can only cancel your own outgoing friend requests."

    # Test cancelling properly
    auth["user_id"] = uid
    response = v2_client.request("delete", f"/v2/users/{rid}/friend-requests/{uid}", json=auth)

    assert response.status_code == 202
    assert response.json()["detail"] == f"Friend request to user {rid} has been cancelled."


@pytest.mark.asyncio
async def test_answering_friend_request(
    v2_client, v2_created_user, v2_created_auth, repo, auth_repo
):
    auth = await auth_repo.get_by_id(v2_created_user.id)

    uid = v2_created_user.id

    json1 = {
        "requestor": uid,
        "auth": {"user_id": uid, "jwt": auth.token},
    }

    receiver = await repo.create("alice", "alice@example.com", "pw")
    rid = receiver.id

    time = datetime.now(timezone.utc) + timedelta(minutes=30)
    auth_json = {
        "id": rid,
        "password": "pw",
        "expiry": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    response = v2_client.post("/v2/authentications", json=auth_json)
    json2 = {
        "decision": "decline",
        "auth": {"user_id": rid, "jwt": response.json()["jwt"]},
    }
    # Test trying to accept a non-existent request
    response = v2_client.put(f"/v2/users/{rid}/friend-requests/{uid}", json=json2)

    assert response.status_code == 404
    assert response.json()["detail"] == "No pending request from this user."

    # Test cancelling a non-existent request
    response = v2_client.request(
        "delete", f"/v2/users/{rid}/friend-requests/{uid}", json=json1["auth"]
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No pending friend request found to cancel."

    # Send a friend request to alice
    response = v2_client.post(f"/v2/users/{rid}/friend-requests/", json=json1)

    assert response.status_code == 200

    # Test answering without authentication
    response = v2_client.put(f"/v2/users/{rid}/friend-requests/{uid}", json={"decision": "accept"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized!"

    # Test answering as the wrong user
    json2["auth"]["user_id"] = uid
    response = v2_client.put(f"/v2/users/{rid}/friend-requests/{uid}", json=json2)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not your request to answer."

    json2["auth"]["user_id"] = rid
    # Test declining correctly
    response = v2_client.put(f"/v2/users/{rid}/friend-requests/{uid}", json=json2)

    assert response.status_code == 200
    assert response.json()["detail"] == "Friend request declined."

    # Re-send a friend request to alice
    response = v2_client.post(f"/v2/users/{rid}/friend-requests/", json=json1)

    # Test accepting correctly
    json2["decision"] = "accept"
    response = v2_client.put(f"/v2/users/{rid}/friend-requests/{uid}", json=json2)

    assert response.status_code == 200
    assert response.json()["detail"] == "Friend request accepted."
    assert response.json()["friendship"] == {"user_id": rid, "other_id": uid}

    # Test sending a friend request to an existing friend
    response = v2_client.post(f"/v2/users/{rid}/friend-requests/", json=json1)

    assert response.status_code == 400
    assert response.json()["detail"] == "You are already friends."

    # Test listing all friends for both users
    response = v2_client.get(f"/v2/users/{rid}/friends/")

    assert response.status_code == 200
    assert response.json()["friends"]

    response = v2_client.get(f"/v2/users/{uid}/friends/")

    assert response.status_code == 200
    assert response.json()["friends"]

    # Test getting a friend by name and id for both users
    response = v2_client.get(f"/v2/users/{rid}/friends/name/{v2_created_user.name}")

    assert response.status_code == 200
    assert response.json()["friend"]

    response = v2_client.get(f"/v2/users/{rid}/friends/name/beeble")

    assert response.status_code == 404
    assert response.json()["detail"] == "Friend not found."

    response = v2_client.get(f"/v2/users/{uid}/friends/name/alice")

    assert response.status_code == 200
    assert response.json()["friend"]

    response = v2_client.get(f"/v2/users/{rid}/friends/id/{uid}")

    assert response.status_code == 200
    assert response.json()["friend"]

    response = v2_client.get(f"/v2/users/{rid}/friends/id/99")

    assert response.status_code == 404
    assert response.json()["detail"] == "Friend not found."

    response = v2_client.get(f"/v2/users/{uid}/friends/id/{rid}")

    assert response.status_code == 200
    assert response.json()["friend"]

    # Test deleting a friend without authentication
    response = v2_client.delete(f"/v2/users/{rid}/friends/id/{uid}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized!"

    # Test deleting from the wrong user account
    response = v2_client.request("delete", f"/v2/users/{rid}/friends/id/{uid}", json=json1["auth"])

    assert response.status_code == 403
    assert response.json()["detail"] == "Not allowed."

    # Test deleting normally
    response = v2_client.request("delete", f"/v2/users/{rid}/friends/id/{uid}", json=json2["auth"])

    assert response.status_code == 202
    assert response.json()["detail"] == f"Friendship with user {uid} deleted."

    # Test deleting a non-existent user
    response = v2_client.request("delete", f"/v2/users/{rid}/friends/id/3", json=json2["auth"])

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

    # Test deleting a non-existent friendship
    response = v2_client.request("delete", f"/v2/users/{rid}/friends/id/{uid}", json=json2["auth"])

    assert response.status_code == 404
    assert response.json()["detail"] == "No friendship found to delete."



