"""
Tests all execution paths in game/daily.py. Notably, compare_countries() does not need to be tested,
since every path it can take it covered by the handle_guess() tests.
"""

from unittest.mock import MagicMock, patch

import pytest

from game.daily import end_game, get_daily_country, handle_guess
from phase2.country import Country, get_country
from phase2.round import RoundStats


@pytest.fixture
def round_stats() -> RoundStats:
    return RoundStats(mode="daily")


@pytest.fixture()
def mocked_get_daily_country():
    patcher = patch("game.daily.get_daily_country")
    mock = patcher.start()
    mock.return_value = get_country("united states")
    yield mock
    patcher.stop()


@pytest.fixture
def mocked_end_game():
    patcher = patch("game.daily.end_game")
    mock = patcher.start()
    yield mock
    patcher.stop()


@pytest.mark.noautofixt
def test_get_daily_country_same_country_for_same_day():
    first_call = get_daily_country()
    second_call = get_daily_country()

    assert isinstance(first_call, Country)
    assert first_call.name == second_call.name


# region handle_guess() Tests


def test_handle_correct_guess(round_stats, mocked_get_daily_country, mocked_end_game):
    user_guess = "united states"

    handle_guess(user_guess, round_stats)

    assert round_stats.guesses == 1
    assert round_stats.guessed_names == [user_guess]
    mocked_get_daily_country.assert_called_once()
    mocked_end_game.assert_called_once()


def test_handle_incorrect_guess(round_stats, mocked_get_daily_country, mocked_end_game):
    user_guess = "panama"

    handle_guess(user_guess, round_stats)

    assert round_stats.guesses == 1
    assert round_stats.guessed_names == [user_guess]
    mocked_get_daily_country.assert_called_once()
    mocked_end_game.assert_not_called()


def test_handle_invalid_guess(round_stats, mocked_get_daily_country, mocked_end_game):
    user_guess = "wales"

    round_stats.guess_error.emit = MagicMock()

    handle_guess(user_guess, round_stats)

    assert round_stats.guesses == 0, "Errors should not increment guesses!"
    assert round_stats.guessed_names == []
    mocked_get_daily_country.assert_called_once()
    mocked_end_game.assert_not_called()
    round_stats.guess_error.emit.assert_called_once()


def test_handle_guess_limit(round_stats, mocked_get_daily_country, mocked_end_game):
    round_stats.guesses = round_stats.max_guesses - 1

    user_guess = "india"

    handle_guess(user_guess, round_stats)

    assert round_stats.guesses == round_stats.max_guesses
    assert round_stats.guessed_names == [user_guess]
    mocked_get_daily_country.assert_called_once()
    mocked_end_game.assert_called_once()


# endregion
# region end_game() tests
def test_win_game(round_stats):
    round_stats.game_ended.emit = MagicMock()
    round_stats.end_round = MagicMock()

    end_game(True, round_stats)

    round_stats.game_ended.emit.assert_called_once_with(True)
    round_stats.end_round.assert_called_once()


def test_lose_game(round_stats):
    round_stats.game_ended.emit = MagicMock()
    round_stats.end_round = MagicMock()

    end_game(False, round_stats)

    round_stats.game_ended.emit.assert_called_once_with(False)
    round_stats.end_round.assert_called_once()


# endregion
