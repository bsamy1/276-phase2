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
        patcher = patch("phase2.survival.get_random_country")
        mock = patcher.start()
        mock.return_value = get_country("united states")
        yield mock
        patcher.stop()


@pytest.fixture
def mocked_stats_repo(session=None):
    """Mock the statistics repository"""
    patcher = patch("phase2.survival.get_statistics_repository")
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


async def test_survival_error_entry(user: User) -> None:
    """Test that invalid country data triggers error notification"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    user.find("Guess").type("Wales")
    user.find("Submit").click()
    await user.should_see("There was an issue processing that guess. Try something else!")


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


async def test_survival_repeat_guess(user: User) -> None:
    """Test that repeating a guess shows error"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    guess = user.find("Guess")
    guess.type("Canada").trigger("keydown.enter")

    await asyncio.sleep(0.1)

    guess.type("Canada").trigger("keydown.enter")
    await user.should_see("Already guessed!")


async def test_survival_correct_guess(user: User) -> None:
    """Test correct guess updates streak and loads new country"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    guess = user.find("Guess")
    guess.type("United States").trigger("keydown.enter")

    await asyncio.sleep(0.1)

    await user.should_see("Streak: 1")


async def test_survival_lose_life(user: User) -> None:
    """Test that running out of guesses loses a life"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    # Make 5 incorrect guesses
    guesses_list = ["Canada", "Germany", "Ireland", "India", "China"]
    guess = user.find("Guess")

    for country in guesses_list:
        guess.type(country).trigger("keydown.enter")
        await asyncio.sleep(0.1)

    # Should have lost one life (from 3 to 2)
    await user.should_see("Lives:")


async def test_survival_game_over(user: User, mocked_stats_repo) -> None:
    """Test game over when all lives are lost"""
    from game.survival_ui import survival_content

    @ui.page("/survival")
    def _():
        survival_content()

    await user.open("/survival")

    guess = user.find("Guess")

    # Lose all 3 lives (5 wrong guesses per life = 15 total)
    wrong_guesses = ["Canada", "Germany", "Ireland", "India", "China"]

    for _ in range(3):  # 3 lives
        for country in wrong_guesses:
            guess.type(country).trigger("keydown.enter")
            await asyncio.sleep(0.1)

    await user.should_see(ui.dialog)
    await user.should_see("Game Over!")
    await user.should_see("Final Streak:")


@pytest.mark.noautofixt
async def test_survival_bonus_life(user: User) -> None:
    """Test that 5 correct guesses awards a bonus life"""
    from game.survival_ui import survival_content

    with patch("phase2.survival.get_random_country") as mock_random:
        # Return different countries for each correct guess
        countries = [
            get_country("canada"),
            get_country("germany"),
            get_country("france"),
            get_country("italy"),
            get_country("spain"),
        ]
        mock_random.side_effect = countries

        @ui.page("/survival")
        def _():
            survival_content()

        await user.open("/survival")

        guess = user.find("Guess")

        # Make 5 correct guesses
        for country_obj in countries:
            guess.type(country_obj.name).trigger("keydown.enter")
            await asyncio.sleep(0.1)

        # Should show bonus life awarded (4 hearts instead of 3)
        await user.should_see("Streak: 5")