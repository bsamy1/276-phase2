import random
from datetime import date

from phase2.country import Country, get_country, get_random_country
from phase2.round import GuessFeedback, RoundStats


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
    round_stats.guesses += 1
    country = get_country(input)
    daily_country = get_daily_country()

    feedback: GuessFeedback = compare_countries(country, daily_country)

    # TODO: Remove placeholder feedback
    feedback = GuessFeedback(
        name=False,
        population=">",
        size="<",
        currencies="partial",
        languages=False,
        timezones="partial",
        region=True,
    )

    if feedback.name:  # correct guess
        end_game(True, round_stats)
        round_stats.end_round()
    elif round_stats.guesses >= round_stats.max_guesses:  # too many guesses
        end_game(False, round_stats)
        round_stats.end_round()

    round_stats.guess_graded.emit(country, feedback)


def compare_countries(guess: Country, answer: Country):
    """
    Check if the two countries, match.
    If not, compare the following statistics for two countries:
    - Population
    - Geographical Size
    - Currencies
    - Languages
    - Timezones
    - Region
    """
    pass


def end_game(won: bool, round_stats: RoundStats):
    """
    End the game in either a win or a loss, and pass this game's statistics
    on to be processed in statistics.py, and show a breakdown of this game's
    stats to the user
    """
    pass
