import os
import time

import pytest
import pytest_asyncio
from pytest_postgresql import factories
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.database import Base

from .session_analytics import (
    SessionAnalyticsRepository,
    get_session_analytics_repository,
)
from .user import UserRepository

if os.getenv("CI"):
    pass
else:
    postgresql_in_docker = factories.postgresql_noproc(
        host="10.5.0.2", dbname="test", user="admin", password="admin"
    )
    postgresql = factories.postgresql("postgresql_in_docker", dbname="test")


@pytest.fixture(scope="function")
def engine(postgresql):
    engine = create_engine(
        f"postgresql+psycopg2://{postgresql.info.user}:{postgresql.info.password}@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
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


@pytest_asyncio.fixture
async def created_user(user_repo):
    user = await user_repo.create(name="Foo", email="foo@bar.com", password="password123")
    return user


@pytest.fixture(scope="function")
def session_analytics_repo(session):
    yield SessionAnalyticsRepository(session)


@pytest_asyncio.fixture
async def created_session(created_user, session_analytics_repo):
    session_analytics = await session_analytics_repo.create(user=created_user)
    yield session_analytics
    await session_analytics_repo.end(session_id=session_analytics.id)


def test_get_session_analytics_repository(session):
    assert isinstance(get_session_analytics_repository(session), SessionAnalyticsRepository)
    assert isinstance(get_session_analytics_repository(), SessionAnalyticsRepository)


@pytest.mark.asyncio
async def test_create_session(user_repo, created_user, session_analytics_repo):
    session_analytics = await session_analytics_repo.create(created_user)

    assert session_analytics
    assert session_analytics.id
    assert session_analytics.user_id
    assert session_analytics.session_start
    assert not session_analytics.session_end
    assert not session_analytics.session_length

    await session_analytics_repo.end(user=created_user)


@pytest.mark.asyncio
async def test_create_session_no_user(session_analytics_repo):
    session_analytics = await session_analytics_repo.create()

    assert session_analytics
    assert session_analytics.id
    assert not session_analytics.user_id
    assert session_analytics.session_start
    assert not session_analytics.session_end
    assert not session_analytics.session_length

    await session_analytics_repo.end(session_id=session_analytics.id)


@pytest.mark.asyncio
async def test_end_session(created_user, session_analytics_repo, created_session):
    session_analytics1 = await session_analytics_repo.end(user=created_user)

    assert session_analytics1
    assert session_analytics1.session_start == created_session.session_start
    assert session_analytics1.session_end
    assert session_analytics1.session_length

    session_analytics2 = await session_analytics_repo.end(user=created_user)

    assert not session_analytics2, ".end() on a user with no active sessions should return None"


@pytest.mark.asyncio
async def test_end_session_no_user(session_analytics_repo, created_session):
    session_analytics = await session_analytics_repo.end(session_id=created_session.id)

    assert session_analytics
    assert session_analytics.session_start == created_session.session_start
    assert session_analytics.session_end
    assert session_analytics.session_length


@pytest.mark.asyncio
async def test_end_nonexistent_session(session_analytics_repo, created_user):
    session_analytics1 = await session_analytics_repo.end(session_id=1)
    session_analytics2 = await session_analytics_repo.end(user=created_user)
    session_analytics3 = await session_analytics_repo.end()

    assert not session_analytics1, ".end() on an invalid id should return None"
    assert not session_analytics2, ".end() on a user with no active sessions should return None"
    assert not session_analytics3, ".end() with no argument should return None"


@pytest.mark.asyncio
async def test_get_session(session_analytics_repo, created_user, created_session):
    result1 = await session_analytics_repo.get(user=created_user)
    result2 = await session_analytics_repo.get(session_id=created_session.id)
    result3 = await session_analytics_repo.get(user=created_user, session_id=created_session.id)
    result4 = await session_analytics_repo.get(session_id=50)

    assert result1 == created_session
    assert result2 == created_session
    assert result3 == created_session
    assert not result4, ".get() on an invalid id should return None"


@pytest.mark.asyncio
async def test_session_statistics(session_analytics_repo, created_user, created_session):
    # Min/Max, Mean, Median, 95th percentile, current active users
    assert await session_analytics_repo.get_current_active_users() == 1
    assert await session_analytics_repo.get_max_active_users() == 1

    time.sleep(0.1)
    await session_analytics_repo.end(session_id=created_session.id)

    assert await session_analytics_repo.get_current_active_users() == 0
    assert await session_analytics_repo.get_max_active_users() == 1, (
        "Max active users shouldn't change"
    )

    min1 = await session_analytics_repo.min_session_length()
    max1 = await session_analytics_repo.max_session_length()
    mean1 = await session_analytics_repo.mean_session_length()
    median1 = await session_analytics_repo.median_session_length()
    percentile1 = await session_analytics_repo.percentile_session_length(95)

    assert min1
    assert max1
    assert mean1
    assert median1
    assert percentile1
    assert min1 == max1 == mean1 == median1 == percentile1, (
        "All values should be identical when there's only one session"
    )

    # Check that values change across multiple recorded sessions
    await session_analytics_repo.create(user=created_user)
    for i in range(10):
        await session_analytics_repo.create()
    time.sleep(0.1)
    for i in range(10):
        # + 3 to skip the first 2 users we created earlier
        await session_analytics_repo.end(session_id=i + 3)

    await session_analytics_repo.end(user=created_user)

    assert await session_analytics_repo.get_current_active_users() == 0, (
        "There should be 0 users left"
    )
    assert await session_analytics_repo.get_max_active_users() == 11

    min2 = await session_analytics_repo.min_session_length()
    max2 = await session_analytics_repo.max_session_length()
    mean2 = await session_analytics_repo.mean_session_length()
    median2 = await session_analytics_repo.median_session_length()
    percentile2 = await session_analytics_repo.percentile_session_length(95)

    assert min2 <= min1
    assert max2 >= max1
    assert mean1 != mean2
    assert median1 != median2
    assert percentile1 != percentile2
