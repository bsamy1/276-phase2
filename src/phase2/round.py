"""
This file contains classes and methods to be used for managing a game round.
"""

from datetime import datetime, timedelta, timezone

from nicegui import Event

from phase2.country import Country

MAX_GUESSES = 5


class RoundStats:
    """
    Class to hold all of the data for a single round, to be passed around while
    playing.
    """

    guesses: int = 0
    max_guesses: int
    round_start: datetime
    guess_graded: Event[str]
    game_ended: Event[bool]
    round_time: timedelta

    def __init__(self):
        self.guesses = 0
        self.max_guesses = MAX_GUESSES
        self.round_start = datetime.now(timezone.utc)

        self.guess_graded = Event[Country, GuessFeedback]()
        self.game_ended = Event[bool]()
        self.round_time = timedelta()

    def end_round(self):
        self.round_time = datetime.now(timezone.utc) - self.round_start


class GuessFeedback:
    """
    Class that contains feedback for a guess. Any thing that is an exact
    match is set to True.
    Any numerical comparisons are either '<' or '>'
    Set comparisons are either False (no overlap) or 'partial'

    All comparisons are in the form <guess> <operator> <answer>.
    """

    name: int
    population: bool | str
    size: bool | str
    region: int
    currencies: bool | str
    languages: bool | str
    timezones: bool | str

    def __init__(
        self,
        name: bool,
        population: bool | str,
        size: bool | str,
        region: bool,
        currencies: bool | str,
        languages: bool | str,
        timezones: bool | str,
    ):
        self.name = name
        self.population = population
        self.size = size
        self.region = region
        self.currencies = currencies
        self.languages = languages
        self.timezones = timezones
