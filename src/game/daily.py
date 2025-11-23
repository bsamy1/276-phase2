import logging
import random
from datetime import date

from phase2.country import Country, get_country, get_random_country
from phase2.round import GuessFeedback, RoundStats

logger = logging.getLogger("phase2.daily")


def get_daily_country() -> Country:
    """
    Gets a country for today's date, deterministically
    """
    today_str = date.today().isoformat()
    random.seed(today_str)  # seed random with date (every daily country is the same)
    return get_random_country()


def handle_guess(input: str, round_stats: RoundStats):
    """
    Assumes input str is a valid country string

    Processes the given input. Ends the game if either end condition is reached
    (reached max guesses or guessed correctly)
    """
    country = get_country(input)
    daily_country = get_daily_country()

    # Start the round if it isn't started already
    if not round_stats.start_time:
        round_stats.start_round()

    # Error handling in case the countryinfo API isn't able to serve info we need
    try:
        feedback: GuessFeedback = compare_countries(country, daily_country)
    except AttributeError:
        round_stats.guess_error.emit()
        return

    round_stats.guessed_names.append(country.name)
    round_stats.guesses += 1

    if feedback.name:  # correct guess
        end_game(True, round_stats)
        round_stats.end_round()
    elif round_stats.guesses >= round_stats.max_guesses:  # too many guesses
        end_game(False, round_stats)
        round_stats.end_round()

    round_stats.guess_graded.emit(country, feedback)


def compare_countries(guess: Country, answer: Country) -> GuessFeedback:
    """
    Check if the two countries match.
    If they match, return True.
    If not, compare the following statistics:
    - Population
    - Geographical Size
    - Currencies
    - Languages
    - Timezones
    - Region

    Returns a GuessFeedback structure containing the results of the comparison
    """
    feedback = GuessFeedback()

    # Check if countries match (correct guess)
    feedback.name = guess.name == answer.name

    # Compare population
    if guess.population and answer.population:
        ratio = guess.population / answer.population
        if ratio < 1:
            feedback.population = "<"
        elif ratio > 1:
            feedback.population = ">"
        elif ratio == 1:
            feedback.population = True

    # Compare size (area)
    if guess.size and answer.size:
        ratio = guess.size / answer.size
        if ratio < 1:
            feedback.size = "<"
        elif ratio > 1:
            feedback.size = ">"
        elif ratio == 1:
            feedback.size = True

    # Compare region
    feedback.region = guess.region == answer.region

    # Compare currencies
    guess_currencies = set(guess.currencies) if guess.currencies else set()
    answer_currencies = set(answer.currencies) if answer.currencies else set()

    if answer_currencies:
        if guess_currencies == answer_currencies:
            feedback.currencies = True
        elif guess_currencies & answer_currencies:  # Has intersection
            feedback.currencies = "partial"
        else:
            feedback.currencies = False

    # Compare languages
    guess_languages = set(guess.languages) if guess.languages else set()
    answer_languages = set(answer.languages) if answer.languages else set()

    if answer_languages:
        if guess_languages == answer_languages:
            feedback.languages = True
        elif guess_languages & answer_languages:  # Has intersection
            feedback.languages = "partial"
        else:
            feedback.languages = False

    # Compare timezones
    guess_timezones = set(guess.timezones) if guess.timezones else set()
    answer_timezones = set(answer.timezones) if answer.timezones else set()

    if answer_timezones:
        if guess_timezones == answer_timezones:
            feedback.timezones = True
        elif guess_timezones & answer_timezones:  # Has intersection
            feedback.timezones = "partial"
        else:
            feedback.timezones = False

    return feedback


def end_game(won: bool, round_stats: RoundStats):
    """
    End the game in either a win or a loss, and pass this game's statistics
    on to be processed in statistics.py, and show a breakdown of this game's
    stats to the user
    """

    round_stats.end_round()

    # TODO (milestone 2): Get the user id of the currently playing user, if there is one

    # TODO (milestone 3): Add in the number of survival rounds completed

    # TODO (milestone 2): Add round to the rounds database properly
    """round_statistics_repo = RoundStatisticsRepository()
    round_statistics_repo.add_round(
        time_to_complete=round_stats.round_time,
        won=won,
        guesses=round_stats.guesses,
        mode=round_stats.mode,
    )"""

    # Show game stats in UI
    round_stats.game_ended.emit(won)
