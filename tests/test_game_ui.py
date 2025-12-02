import asyncio
from unittest.mock import patch

import pytest
from nicegui import ui
from nicegui.testing import User
from shared.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from game.game_ui import concat_data, list_to_str
from phase2.country import get_country
from phase2.statistics import RoundStatisticsRepository

pytest_plugins = ["nicegui.testing.user_plugin"]


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


@pytest.fixture
def mocked_stats_repo(session):
    patcher = patch("game.daily.get_statistics_repository")
    mock = patcher.start()
    mock.return_value = RoundStatisticsRepository(session)
    yield mock
    patcher.stop()


@pytest.fixture(autouse=True)
def mocked_get_daily_country(request):
    """
    Automatically patches get_daily_country in both of the places it's
    called (daily.py and game_ui.py) for each test to ensure test results
    won't change based on the date.
    """
    if "noautofixt" in request.keywords:
        yield "Nil"
    else:
        daily_patcher = patch("game.daily.get_daily_country")
        ui_patcher = patch("game.game_ui.get_daily_country")
        daily_mock = daily_patcher.start()
        ui_mock = ui_patcher.start()
        daily_mock.return_value = get_country("united states")
        ui_mock.return_value = get_country("united states")
        yield
        daily_patcher.stop()
        ui_patcher.stop()


@pytest.mark.noautofixt
def test_concat_data():
    assert concat_data("a", "b") == "a|b"


@pytest.mark.noautofixt
def test_list_to_str():
    items = ["a", "b", "c"]

    string = list_to_str(items)

    assert isinstance(string, str)
    assert string == "a, b, c"


async def test_layout(user: User) -> None:
    await user.open("/")

    await user.should_see(marker="timer")
    await user.should_see("0:00:00")
    await user.should_see(ui.grid)
    await user.should_see("Guess")
    await user.should_see("Submit")

    await user.should_not_see(ui.dialog)


async def test_typing(user: User) -> None:
    await user.open("/")

    user.find("Guess").type("asdf")
    await user.should_not_see("Not a valid country!")
    await user.should_not_see("Already guessed!")


async def test_invalid_entry(user: User) -> None:
    await user.open("/")

    user.find("Guess").type("wrong")
    user.find("Submit").click()
    await user.should_see("Not a valid country!")
    await user.should_see("0:00:00")


async def test_error_entry(user: User) -> None:
    await user.open("/")

    user.find("Guess").type("Wales")
    user.find("Submit").click()
    await user.should_see("There was an issue processing that guess. Try something else!")


async def test_valid_entry(user: User) -> None:
    await user.open("/")

    guess = user.find("Guess")
    guess.type("Canada").trigger("keydown.enter")

    await user.should_see(ui.grid)
    await user.should_see(marker="arrow")
    await user.should_see("Canada")
    await user.should_see("Americas")
    await user.should_see("CAD")
    await user.should_see(
        content="UTC−08:00, UTC−07:00, UTC−06:00, UTC−05:00, UTC−04:00, UTC−03:30"
    )


async def test_repeat_guess(user: User) -> None:
    await user.open("/")

    guess = user.find("Guess")
    guess.type("Canada").trigger("keydown.enter")

    await asyncio.sleep(0.1)

    guess.type("Canada").trigger("keydown.enter")
    await user.should_see("Already guessed!")


async def test_win_game(user: User, mocked_stats_repo) -> None:
    await user.open("/")

    guess = user.find("Guess")
    guess.type("United States").trigger("keydown.enter")

    await asyncio.sleep(0.1)

    await user.should_see(ui.dialog)
    await user.should_see("Congratulations!")
    await user.should_see("The correct country was United States")
    await user.should_see(ui.table)


async def test_lose_game(user: User, mocked_stats_repo) -> None:
    await user.open("/")

    await user.should_see(ui.grid)

    guesses = ["Canada", "Germany", "Ireland", "India", "China", "Japan"]
    guess = user.find("Guess")
    for i in range(6):
        guess.type(guesses[i]).trigger("keydown.enter")
        await asyncio.sleep(0.1)

    await user.should_see(ui.dialog)
    await user.should_see("Too bad!")
    await user.should_see("The correct country was United States")
    await user.should_see(ui.table)
