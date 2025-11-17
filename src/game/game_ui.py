import json
from datetime import datetime, timezone

from nicegui import ui

from game.daily import get_daily_country, handle_guess
from phase2.country import Country
from phase2.round import Comparison, GuessFeedback, RoundStats

# NiceGUI elements go here

# display the game (guess input, guess feedback, timer, # of guesses, etc.)
"""
game

    - guess entry box
    - guess button
    - guess feedback

    - win/loss popup
"""


def concat_data(feedback, data) -> str:
    return str(feedback) + "|" + str(data)


def list_to_str(items: list):
    res = ""
    for item in items:
        if item != items[0]:
            res += ", "
        res += item
    return res


correct_bg = "bg-green-500 "
similar_bg = "bg-yellow-500 "
incorrect_bg = "bg-red-500 "

greater_than_arrow = r"clip-path: polygon(97% 40%,80% 40%,80% 95%,20% 95%,20% 40%,3% 40%,50% 5%)"
less_than_arrow = r"clip-path: polygon(98% 60%,80% 60%,80% 5%,20% 5%,20% 60%,3% 60%,50% 95%)"


def content():
    round_stats = RoundStats()
    guessed_names = []

    options = []
    with open("src/game/countries.json") as file:
        options = json.load(file)

    def is_guess_valid(guess: str) -> str | None:
        """
        Validates the given guess, either returning an error
        message if it's invalid, or None if it's valid.
        """
        if guess.lower() not in options:
            return "Not a valid country!"
        if guess.lower() in guessed_names:
            return "Already guessed!"
        guessed_names.append(guess.lower())
        return None

    def try_guess():
        """
        Validates an inputted guess and passes it into the guess handler
        if it's valid.
        """
        if guess_input.validate():
            handle_guess(guess_input.value, round_stats)
            guess_input.value = ""

            # TODO: Move this emit into game_end()
            # round_stats.game_ended.emit(False)

    # TODO: Add actual feedback instead of placeholder data
    @round_stats.guess_graded.subscribe
    def display_feedback(country: Country, feedback: GuessFeedback):
        """
        Displays the feedback passed as an argument
        """

        with guesses:
            for attr, value in vars(feedback).items():
                classes = "aspect-square h-24 justify-center text-center "
                style = None
                match value:
                    case Comparison.GREATER_THAN:
                        classes += similar_bg
                        style = greater_than_arrow
                    case Comparison.LESS_THAN:
                        classes += similar_bg
                        style = less_than_arrow
                    case Comparison.NO_OVERLAP:
                        classes += incorrect_bg
                    case Comparison.PARTIAL_OVERLAP:
                        classes += similar_bg
                if isinstance(value, bool):
                    if value:
                        classes += correct_bg
                    else:
                        classes += incorrect_bg

                with ui.card(align_items="center").classes(classes):
                    if style:
                        ui.element("div").classes("absolute inset-0 bg-black/40").style(style)

                    with ui.row().classes("items-center"):
                        attr_content = getattr(country, attr)
                        text = str(attr_content)

                        if attr == "population":
                            text = format(attr_content, ",")
                        elif attr == "size":
                            text = format(attr_content, ",")
                        elif attr == "currencies":
                            text = list_to_str(attr_content)
                        elif attr == "languages":
                            text = list_to_str(attr_content)
                        elif attr == "timezones":
                            text = list_to_str(attr_content)

                        ui.label(text).classes("break-all")

    @round_stats.game_ended.subscribe
    def display_results(won: bool):
        """
        Displays the game results pop-up
        """
        if won:
            text = "Congratulations!"
        else:
            text = "Too bad!"

        with ui.dialog() as dialog, ui.card():
            ui.label(text)
            ui.label("The correct country was " + get_daily_country().name)
            ui.label(f"Time: {str(round_stats.round_time).split('.')[0]}")
            ui.label(f"Guesses: {round_stats.guesses}")
            ui.button("Close", on_click=dialog.close)

            # TODO: Display leaderboard/player stats here?

            dialog.open()

    with ui.column(align_items="center").classes("mx-auto p-4"):
        timer = ui.label().mark("timer")
        ui.timer(
            1.0,
            lambda: timer.set_text(
                f"{str(datetime.now(timezone.utc) - round_stats.round_start).split('.')[0]}"
            ),
        )

        guesses = ui.grid(columns=7).classes("w-full")
        with guesses:
            pass

        with ui.card(align_items="center"):
            guess_input = (
                ui.input(
                    label="Guess",
                    placeholder="Enter a country",
                    autocomplete=options,
                    validation=is_guess_valid,
                )
                .without_auto_validation()
                .on("keydown.enter", lambda: try_guess())
            )
            ui.button("Submit", on_click=lambda: try_guess())


# button to display leaderboards
"""
leaderboard

    - by default, display ~250 entries around the user
    - allow switch to friends-only or global leaderboard
    - allow jumping to top-ranked players
"""

# button to open account management menu
"""
account management

    - create account
    - see account stats
    - edit account info (username/password/email)
    - friends/friend requests
"""
