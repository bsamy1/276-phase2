import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from phase2.leaderboard import Base, Leaderboard


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
    yield Leaderboard(session)

@pytest.mark.asyncio
async def test_update_user_entry(repo):
    pass

@pytest.mark.asyncio
async def test_get_entry(repo):
    pass

@pytest.mark.asyncio
async def test_get_top_10_entry(repo):
    leaderboard_models = await repo.get_all()
    assert leaderboard_models == []

@pytest.mark.asyncio
async def test_get_250_entries(repo):
    leaderboard_models = await repo.get_all()
    assert leaderboard_models == []

@pytest.mark.asyncio
async def get_friend_entries(repo):
    pass