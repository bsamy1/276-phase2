"""
This file contains classes and methods to be used for managing a game round.
"""

from datetime import datetime, timedelta, timezone
from enum import IntEnum

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


class Comparison(IntEnum):
    """
    Enum used for comparisons when values don't match exactly
    """

    # For comparing numeric values (population, size)
    GREATER_THAN = 2
    LESS_THAN = 3

    # For comparing sets (currencies, timezones)
    NO_OVERLAP = 4
    PARTIAL_OVERLAP = 5


class GuessFeedback:
    """
    Class that contains feedback for a guess. Any thing that is an exact
    match is set to True; otherwise, it is given a comparison enum (with
    the exceptions of name and region, which can only be 0 (False) or 1 (True))

    All comparisons are in the form <guess> OP <answer>.
    """

    name: int
    population: bool | Comparison
    size: bool | Comparison
    region: int
    currencies: bool | Comparison
    languages: bool | Comparison
    timezones: bool | Comparison

    def __init__(
        self,
        name: bool,
        population: bool | Comparison,
        size: bool | Comparison,
        region: bool,
        currencies: bool | Comparison,
        languages: bool | Comparison,
        timezones: bool | Comparison,
    ):
        self.name = name
        self.population = population
        self.size = size
        self.region = region
        self.currencies = currencies
        self.languages = languages
        self.timezones = timezones
