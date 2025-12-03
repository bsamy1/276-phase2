import asyncio
from unittest.mock import patch

import pytest
from nicegui import ui
from nicegui.testing import User

from phase2.country import get_country

pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.fixture(autouse=True)
def mocked_get_random_country(request):
    """Mock get_random_country to return consistent country for testing"""
    if "noautofixt" in request.keywords:
        yield "Nil"
    else:
        patcher = patch("game.survival.get_random_country")
        mock = patcher.start()
        mock.return_value = get_country("united states")
        yield mock
        patcher.stop()


@pytest.fixture
def mocked_stats_repo(session=None):
    """Mock the statistics repository"""
    patcher = patch("game.survival.get_statistics_repository")
    mock = patcher.start()
    yield mock
    patcher.stop()


async def test_survival_layout(user: User) -> None:
    """Test that survival mode UI loads with all required elements"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    await user.should_see("Survival Mode")
    await user.should_see("Lives:")
    await user.should_see("Streak:")
    await user.should_see(marker="timer")
    await user.should_see("0:00:00")
    await user.should_see(ui.grid)
    await user.should_see("Guess")
    await user.should_see("Submit")
    await user.should_see("How to Play:")
    await user.should_not_see(ui.dialog)


async def test_survival_typing(user: User) -> None:
    """Test input field accepts typing"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    user.find("Guess").type("asdf")
    await user.should_not_see("Not a valid country!")
    await user.should_not_see("Already guessed!")


async def test_survival_invalid_entry(user: User) -> None:
    """Test invalid country entry shows error"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    user.find("Guess").type("wrong")
    user.find("Submit").click()
    await user.should_see("Not a valid country!")


async def test_survival_valid_entry(user: User) -> None:
    """Test valid guess displays feedback"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    guess = user.find("Guess")
    guess.type("Canada").trigger("keydown.enter")

    await asyncio.sleep(0.1)

    await user.should_see(ui.grid)
    await user.should_see(marker="arrow")
    await user.should_see("Canada")


async def test_survival_correct_guess(user: User) -> None:
    """Test correct guess updates streak"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    guess = user.find("Guess")
    guess.type("United States").trigger("keydown.enter")

    await asyncio.sleep(0.1)

    await user.should_see("Streak: 1")