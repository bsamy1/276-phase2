
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from shared.database import Base

from .friends import (
    FriendRequest,
    FriendshipRepository,
    get_friendship_repository,
)
from .user import UserRepository


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
def friend_repo(session):
    yield FriendshipRepository(session)

def test_get_friendship_repository(session):
    assert isinstance(get_friendship_repository(session), FriendshipRepository)
    assert isinstance(get_friendship_repository(), FriendshipRepository)

@pytest.mark.asyncio
async def test_get_all_requests(user_repo, friend_repo):
    # Create users Bob and Jane
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    # Bob sends friend request to Jane
    await friend_repo.send_request(bob.id, jane.id)

    requests = await friend_repo.get_all_requests()

    # Make sure we actually returned something
    assert requests


@pytest.mark.asyncio
async def test_user_can_send_friend_request(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    request = await friend_repo.send_request(bob.id, jane.id)

    assert request is not None
    assert request.requestor_id == bob.id
    assert request.requestee_id == jane.id
    assert request.status == "pending"

    db_request = friend_repo.session.scalar(
        select(FriendRequest).where(FriendRequest.id == request.id)
    )
    assert db_request is not None
    assert db_request.status == "pending"


@pytest.mark.asyncio
async def test_send_duplicate_friend_request(user_repo, friend_repo):
    # Create users Bob and Jane
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    # Bob sends friend request to Jane
    await friend_repo.send_request(bob.id, jane.id)
    request2 = await friend_repo.send_request(bob.id, jane.id)

    # Verify that the second friend request was not created
    assert request2 is None


@pytest.mark.asyncio
async def test_accept_friend_request(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    req = await friend_repo.send_request(bob.id, jane.id)

    await friend_repo.accept_request(req.id)

    db_req = friend_repo.session.query(FriendRequest).filter_by(id=req.id).one()
    assert db_req.status == "accepted"


@pytest.mark.asyncio
async def test_get_friendship_status(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    status_none = await friend_repo.get_friendship_status(bob.id, jane.id, "")
    assert not status_none

    await friend_repo.send_request(bob.id, jane.id)
    status_pending = await friend_repo.get_friendship_status(bob.id, jane.id, "")
    assert status_pending.status == "pending"

    req = friend_repo.session.scalar(
        select(FriendRequest).where(FriendRequest.requestor_id == bob.id)
    )
    await friend_repo.accept_request(req.id)

    status_accepted = await friend_repo.get_friendship_status(bob.id, jane.id, "")
    assert status_accepted.status == "accepted"

    specific_status = await friend_repo.get_friendship_status(bob.id, jane.id, "accepted")
    assert specific_status.status == "accepted"

    wrong_status = await friend_repo.get_friendship_status(bob.id, jane.id, "pending")
    assert not wrong_status


@pytest.mark.asyncio
async def test_list_friends_returns_only_accepted(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")
    tom = await user_repo.create("Tom", "tom@tom.com", "tom")

    req1 = await friend_repo.send_request(bob.id, jane.id)
    await friend_repo.accept_request(req1.id)

    await friend_repo.send_request(bob.id, tom.id)

    friends_of_bob = await friend_repo.list_friends(bob.id)

    ids = {u.id for u in friends_of_bob}
    assert jane.id in ids
    assert tom.id not in ids
    assert bob.id not in ids


@pytest.mark.asyncio
async def test_get_friend_by_id_found_and_not_found(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")
    tom = await user_repo.create("Tom", "tom@tom.com", "tom")

    req = await friend_repo.send_request(bob.id, jane.id)
    await friend_repo.accept_request(req.id)

    await friend_repo.send_request(bob.id, tom.id)

    friend = await friend_repo.get_friend_by_id(bob.id, jane.id)
    assert friend
    assert friend.id == jane.id

    not_friend = await friend_repo.get_friend_by_id(bob.id, tom.id)
    assert not not_friend


@pytest.mark.asyncio
async def test_get_friend_by_name_found_and_not_found(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    req = await friend_repo.send_request(bob.id, jane.id)
    await friend_repo.accept_request(req.id)

    friend = await friend_repo.get_friend_by_name(bob.id, "Jane")
    assert friend is not None
    assert friend.id == jane.id

    not_friend = await friend_repo.get_friend_by_name(bob.id, "Tom")
    assert not_friend is None

    nobody = await friend_repo.get_friend_by_name(bob.id, "Nope")
    assert nobody is None


@pytest.mark.asyncio
async def test_delete_friendship(user_repo, friend_repo):
    bob = await user_repo.create("Bob", "bob@bob.com", "bob")
    jane = await user_repo.create("Jane", "jane@jane.com", "jane")

    req = await friend_repo.send_request(bob.id, jane.id)
    await friend_repo.accept_request(req.id)

    friend = await friend_repo.get_friend_by_id(bob.id, jane.id)
    assert friend is not None

    deleted = await friend_repo.delete_friendship(bob.id, jane.id)
    assert deleted is True
    friend_after = await friend_repo.get_friend_by_id(bob.id, jane.id)
    assert friend_after is None

    deleted_again = await friend_repo.delete_friendship(bob.id, jane.id)
    assert not deleted_again
