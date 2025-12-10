import time
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from joserfc import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.database import Base

from .auth import Auth, AuthRepository, get_auth_repository
from .user import User, UserRepository


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
def user_repo(session):
    yield UserRepository(session)


@pytest.fixture(scope="function")
def auth_repo(session):
    yield AuthRepository(session)


@pytest_asyncio.fixture
async def created_user(user_repo) -> User:
    user = await user_repo.create("foo", "foo@bar.com", "secret123")
    return user


@pytest_asyncio.fixture
async def created_auth(auth_repo, created_user) -> Auth:
    token = await auth_repo.create(created_user.id)
    return token


def test_get_auth_repository(session):
    assert isinstance(get_auth_repository(session), AuthRepository)
    assert isinstance(get_auth_repository(), AuthRepository)


@pytest.mark.asyncio
async def test_get_auth_by_user_id(auth_repo, created_auth, created_user):
    auth = await auth_repo.get_by_id(created_user.id)

    assert auth.id == created_user.id
    assert auth.token


@pytest.mark.asyncio
async def test_get_nonexistent_auth(auth_repo, created_user):
    auth = await auth_repo.get_by_id(created_user.id)

    assert auth is None


@pytest.mark.asyncio
async def test_create_auth(auth_repo, created_user):
    token = await auth_repo.create(created_user.id)

    assert token
    assert await auth_repo.get_by_id(created_user.id)


@pytest.mark.asyncio
async def test_create_auth_with_specific_expiry(auth_repo, created_user):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = await auth_repo.create(created_user.id, expiry)

    assert token
    assert await auth_repo.get_by_id(created_user.id)


@pytest.mark.asyncio
async def test_create_expired_auth(auth_repo, created_user):
    expiry = datetime.now(timezone.utc) - timedelta(minutes=30)
    token = await auth_repo.create(created_user.id, expiry)

    assert token is None
    assert await auth_repo.get_by_id(created_user.id) is None


@pytest.mark.asyncio
async def test_create_auth_longer_than_hour(auth_repo, created_user):
    expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    token = await auth_repo.create(created_user.id, expiry)

    assert token is None
    assert await auth_repo.get_by_id(created_user.id) is None


@pytest.mark.asyncio
async def test_create_existing_auth(auth_repo, created_user, created_auth):
    token = await auth_repo.create(created_user.id)

    assert token
    assert await auth_repo.get_by_id(created_user.id)


@pytest.mark.asyncio
async def test_delete_auth(auth_repo, created_user, created_auth):
    assert await auth_repo.get_by_id(created_user.id)

    await auth_repo.delete(created_user.id)

    assert await auth_repo.get_by_id(created_user.id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_auth(auth_repo, created_user):
    assert await auth_repo.get_by_id(created_user.id) is None

    await auth_repo.delete(created_user.id)

    assert await auth_repo.get_by_id(created_user.id) is None


@pytest.mark.asyncio
async def test_delete_by_token(auth_repo, created_user):
    token = await auth_repo.create(created_user.id)

    await auth_repo.delete_by_token(token)

    assert await auth_repo.get_by_id(created_user.id) is None

    await auth_repo.delete_by_token(token)

    assert await auth_repo.get_by_id(created_user.id) is None


@pytest.mark.asyncio
async def test_validate_token(auth_repo, created_user, created_auth):
    token = created_auth

    assert await auth_repo.validate(token)


@pytest.mark.asyncio
async def test_validate_invalid_tokens(auth_repo, created_user, created_auth):
    token = created_auth
    token2 = token

    # Validation should fail if the key doesn't contain the correct expiration time
    data = jwt.decode(token2, auth_repo.key)
    data.claims["exp"] = datetime.now(timezone.utc) + timedelta(hours=2)

    token2 = jwt.encode(data.header, data.claims, auth_repo.key)

    assert not await auth_repo.validate(token2)

    # Validation should fail when the token is missing from the database
    await auth_repo.delete(created_user.id)
    assert not await auth_repo.validate(token)


@pytest.mark.asyncio
async def test_validate_expired_token(auth_repo, created_user):
    expiry = datetime.now(timezone.utc) + timedelta(seconds=2)
    token = await auth_repo.create(created_user.id, expiry)

    time.sleep(3)

    assert not await auth_repo.validate(token)
    assert await auth_repo.get_by_id(created_user.id) is None
