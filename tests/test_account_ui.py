import asyncio
import io

import pytest
from nicegui.testing import User
from PIL import Image

from local_repos.auth import LocalAuthRepo
from local_repos.friends import LocalFriendsRepo
from local_repos.stats import LocalStatisticsRepo
from local_repos.users import LocalUserRepo
from phase2.account_ui import (
    MAX_AVATAR_SIZE,
    SESSION,
    account_ui,
    avatar_static_url,
    local_authenticate,
    save_avatar,
)


@pytest.fixture
def user_repo():
    return LocalUserRepo()

@pytest.fixture
def friends_repo(user_repo):
    return LocalFriendsRepo(user_repo)

@pytest.fixture
def auth_repo():
    return LocalAuthRepo()

@pytest.fixture
def stats_repo():
    return LocalStatisticsRepo()


@pytest.fixture
def setup_ui(user_repo, friends_repo, auth_repo, stats_repo):
    account_ui(user_repo, friends_repo, auth_repo, stats_repo)
    class Setup:
        pass

    s = Setup()
    s.TEST = True
    s.user_repo = user_repo
    s.friends_repo = friends_repo
    s.auth_repo = auth_repo
    s.stats_repo = stats_repo
    return s


async def login_as(user_obj, setup_ui):
    SESSION["user"] = user_obj
    SESSION["token"] = await setup_ui.auth_repo.create(user_obj.id)


@pytest.mark.asyncio
async def test_ensure_authenticated_redirect(user: User):
    from phase2 import account_ui as ui_mod
    ui_mod.SESSION["user"] = None
    ui_mod.SESSION["token"] = None

    await user.open("/account/profile")
    await user.should_see("Login")


@pytest.mark.asyncio
async def test_try_login_invalid_creds(user: User):
    """Hit lines 106-109, 134-137: try_login invalid branch"""
    await user.open("/login")
    user.find("Username").type("wrong")
    user.find("Password").type("wrong")
    user.find("Login").click()
    await user.should_see("Invalid credentials")


@pytest.mark.asyncio
async def test_friends_accept_reject_branches(setup_ui):
    """Hit lines 253, 266-270, 282-287: friends accept/reject branches"""
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    bob = await setup_ui.user_repo.create("bob", "bob@test.com", "pass123")
    await login_as(alice, setup_ui)

    # send a request
    req = await setup_ui.friends_repo.send_request(alice.id, bob.id)
    assert req is not None

    # accept
    await setup_ui.friends_repo.accept_request(req.id)
    friends = await setup_ui.friends_repo.list_friends(alice.id)
    assert len(friends) == 1

    # reject/delete friendship
    await setup_ui.friends_repo.delete_friendship(alice.id, bob.id)
    friends_after = await setup_ui.friends_repo.list_friends(alice.id)
    assert len(friends_after) == 0

@pytest.mark.asyncio
async def test_stats_no_data_page(user: User, setup_ui):
    """Hit lines 298, 313: stats page with no data"""
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)

    # Clear stats for user
    setup_ui.stats_repo.stats[alice.id] = None

    await user.open("/stats")
    await user.should_see("You have no game statistics yet.")


@pytest.mark.asyncio
async def test_local_authenticate_success_and_failure():
    repo = LocalUserRepo()
    user = await repo.create("alice", "alice@test.com", "password123")
    
    # password correct
    auth_user = await local_authenticate(repo, "alice", "password123")
    assert auth_user is not None
    assert auth_user.id == user.id

    # password incorrect
    auth_user_fail = await local_authenticate(repo, "alice", "wrongpass")
    assert auth_user_fail is None

    # username does not exist
    auth_user_none = await local_authenticate(repo, "bob", "password123")
    assert auth_user_none is None


@pytest.mark.asyncio
async def test_save_avatar_creates_file(tmp_path):
    img = Image.new("RGB", (500, 500), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    class DummyFile:
        async def read(self):
            return img_bytes.getvalue()

    output_path = tmp_path / "avatar.jpg"
    await save_avatar(output_path, DummyFile())

    assert output_path.exists()
    saved_img = Image.open(output_path)
    assert saved_img.size == MAX_AVATAR_SIZE


def test_avatar_static_url_contains_filename_and_timestamp(tmp_path):
    path = tmp_path / "file.jpg"
    url = avatar_static_url(path)
    assert "file.jpg" in url
    assert "?t=" in url
    ts = int(url.split("?t=")[1])
    assert isinstance(ts, int)
    

@pytest.mark.asyncio
async def test_login(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)

    await user.open("/account")
    await user.should_see("Welcome, alice!")


@pytest.mark.asyncio
async def test_login_invalid(user: User):
    await user.open("/login")
    user.find("Username").type("wrong")
    user.find("Password").type("wrong")
    user.find("Login").click()
    await user.should_see("Invalid credentials")


@pytest.mark.asyncio
async def test_register_duplicate(user: User, setup_ui):
    await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await user.open("/register")
    user.find("Username").type("alice")
    user.find("Email").type("alice@test.com")
    user.find("Password").type("pass123")
    user.find("Register").click()
    await user.should_see("Username or email already exists")


@pytest.mark.asyncio
async def test_account_requires_login(user: User):
    SESSION["user"] = None
    SESSION["token"] = None
    await user.open("/account")
    await user.should_see("Login")


@pytest.mark.asyncio
async def test_profile_update(user: User, setup_ui):
    bob = await setup_ui.user_repo.create("bob", "bob@test.com", "pass123")
    await login_as(bob, setup_ui)

    await user.open("/profile")
    await user.should_see("Edit Profile")

    await setup_ui.user_repo.update_user(bob.id, name="bobby")
    SESSION["user"].name = "bobby" 

    await user.open("/account")
    await user.should_see("Welcome, bobby!")


@pytest.mark.asyncio
async def test_friends_page(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    bob = await setup_ui.user_repo.create("bob", "bob@test.com", "pass123")

    await login_as(alice, setup_ui)

    await user.open("/friends")
    await user.should_see("Friends")

    # Send & accept request
    req = await setup_ui.friends_repo.send_request(alice.id, bob.id)
    await setup_ui.friends_repo.accept_request(req.id)

    friends = await setup_ui.friends_repo.list_friends(alice.id)
    assert len(friends) == 1
    assert friends[0].name == "bob"


@pytest.mark.asyncio
async def test_friends_reject(setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    bob = await setup_ui.user_repo.create("bob", "bob@test.com", "pass123")
    await login_as(alice, setup_ui)

    req = await setup_ui.friends_repo.send_request(alice.id, bob.id)
    assert req is not None

    await setup_ui.friends_repo.accept_request(req.id) # accept first
    await setup_ui.friends_repo.delete_friendship(alice.id, bob.id)  # then remove

    friends = await setup_ui.friends_repo.list_friends(alice.id)
    assert len(friends) == 0


@pytest.mark.asyncio
async def test_friends_empty_list(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)

    await user.open("/friends")
    await user.should_see("You have no friends yet.")
    

@pytest.mark.asyncio
async def test_friends_no_requests(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)

    await user.open("/friends")
    await user.should_see("No pending requests.")
    

@pytest.mark.asyncio
async def test_friends_duplicate(setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    bob = await setup_ui.user_repo.create("bob", "bob@test.com", "pass123")
    await login_as(alice, setup_ui)
    req = await setup_ui.friends_repo.send_request(alice.id, bob.id)
    req2 = await setup_ui.friends_repo.send_request(alice.id, bob.id)
    assert req is not None
    assert req2 is None


@pytest.mark.asyncio
async def test_stats_display(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)

    stats = setup_ui.stats_repo.stats[alice.id]
    stats.daily_streak = 5
    stats.longest_daily_streak = 9
    stats.average_daily_guesses = 3.2
    stats.longest_survival_streak = 7
    stats.score = 150

    await user.open("/stats")

    await user.should_see("Daily Streak: 5")
    await user.should_see("Longest Daily Streak: 9")
    await user.should_see("Average Daily Guesses: 3.20")
    await user.should_see("Longest Survival Streak: 7")
    await user.should_see("Overall Score: 150")


@pytest.mark.asyncio
async def test_stats_no_data(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)
    
    setup_ui.stats_repo.get_leaderboard_stats_for_user(alice.id)

    await user.open("/stats")
    await user.should_see("You have no game statistics yet.")


@pytest.mark.asyncio
async def test_logout(user: User, setup_ui):
    alice = await setup_ui.user_repo.create("alice", "alice@test.com", "pass123")
    await login_as(alice, setup_ui)

    await user.open("/account")
    await user.should_see("Logout")

    user.find("Logout").click()
    await asyncio.sleep(0.1)

    assert SESSION["user"] is None
    assert SESSION["token"] is None
