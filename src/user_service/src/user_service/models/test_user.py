import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.database import Base

from .user import UserRepository, UserSchema


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


@pytest.mark.asyncio
async def test_get_user_by_name(repo):
    await repo.create("Bob", "bob@bob.com", "bob")
    result = await repo.get_by_name("Bob")
    assert result is not None


@pytest.mark.asyncio
async def test_get_all_users_single(repo):
    await repo.create("Bob", "bob@bob.com", "bob")
    user_models = await repo.get_all()
    users = []
    for model in user_models:
        users.append(UserSchema.from_db_model(model).model_dump())
    assert users == [
        {
            "email": "bob@bob.com",
            "id": 1,
            "name": "Bob",
            "password": "********"
        }
    ]


@pytest.mark.asyncio
async def test_get_all_users_empty(repo):
    user_models = await repo.get_all()
    assert user_models == []
