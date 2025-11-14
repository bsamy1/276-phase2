import json
from datetime import datetime

from nicegui import Event, ui

from game.daily import handle_guess

# NiceGUI elements go here

# display the game (guess input, guess feedback, timer, # of guesses, etc.)
"""
game

    - guess entry box
    - guess button
    - guess feedback

    - win/loss popup
"""

# TODO: Replace with data type containing actual guess feedback
guess_graded = Event[str]()
game_ended = Event[bool]()


def try_guess(guess_input, feedback):
    if guess_input.validate():
        handle_guess(guess_input.value)
        guess_input.clear()
        # TODO: Move this emit into the actual handle_guess function
        guess_graded.emit()


@game_ended.subscribe
def display_results(won: bool):
    # TODO: Add pop-up that will display whether you won or lost,
    # your # of guesses and time, and (in future) the leaderboard info

    pass


def content():
    options = []
    with open("src/game/countries.json") as file:
        options = json.load(file)

    # TODO: Add actual feedback instead of placeholder data
    @guess_graded.subscribe
    def display_feedback():
        """
        Displays the feedback passed as an argument in the feedback table
        """
        row = {
            "name": "Test",
            "population": "25",
            "size": "like 2",
            "region": "Azerbaijan",
            "languages": "Evil French, Polish",
            "currencies": "Doubloons",
            "timezones": "UTC, PST, ETC",
        }
        feedback.add_row(row)

    with ui.column(align_items="center").classes("mx-auto w-full max-w-md p-4"):
        timer = ui.label()
        # TODO: Replace with actual game timer, not just current time
        ui.timer(1.0, lambda: timer.set_text(f"{datetime.now():%X}"))

        columns = [
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "population", "label": "Population", "field": "population"},
            {"name": "size", "label": "Size", "field": "size"},
            {"name": "region", "label": "Region", "field": "region"},
            {"name": "languages", "label": "Languages", "field": "languages"},
            {"name": "currencies", "label": "Currencies", "field": "currencies"},
            {"name": "timezones", "label": "Timezones", "field": "timezones"},
        ]
        rows = []
        # TODO: Style table
        feedback = ui.table(
            rows=rows, columns=columns, column_defaults={"align": "center"}, row_key="name"
        )

        with ui.card(align_items="center"):
            guess_input = (
                ui.input(
                    label="Guess",
                    placeholder="Enter a country",
                    autocomplete=options,
                    validation={"Not a valid country!": lambda value: value.lower() in options},
                )
                .without_auto_validation()
                .on("keydown.enter", lambda: try_guess(guess_input, feedback))
            )
            ui.button("Submit", on_click=lambda: try_guess(guess_input, feedback))


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
