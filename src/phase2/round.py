"""
This file contains classes and methods to be used for managing a game round.
"""

from datetime import datetime, timedelta, timezone

from nicegui import Event

from phase2.country import Country

MAX_GUESSES = 5


class GuessFeedback:
    """
    Class that contains feedback for a guess. Any thing that is an exact
    match is set to True.
    Any numerical comparisons are either '<' or '>'
    Set comparisons are either False (no overlap) or 'partial'

    All comparisons are in the form <guess> <operator> <answer>.
    """

    name: bool
    population: bool | str
    size: bool | str
    region: bool
    currencies: bool | str
    languages: bool | str
    timezones: bool | str


class RoundStats:
    """
    Class to hold all of the data for a single round, to be passed around while
    playing.
    """

    guesses: int
    guessed_names: [str]
    max_guesses: int
    mode: str
    start_time: datetime
    guess_graded: Event[Country, GuessFeedback]
    game_ended: Event[bool]
    guess_error: Event
    round_length: timedelta

    def __init__(self, mode: str):
        self.guesses = 0
        self.guessed_names = []
        self.max_guesses = MAX_GUESSES
        self.mode = mode

        self.start_time = None

        self.guess_graded = Event[Country, GuessFeedback]()
        self.game_ended = Event[bool]()
        self.guess_error = Event()

    def start_round(self):
        self.start_time = datetime.now(timezone.utc)

    def end_round(self):
        self.round_length = datetime.now(timezone.utc) - self.start_time
