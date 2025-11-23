import json
from datetime import datetime, timezone

from nicegui import ui

from game.daily import get_daily_country, handle_guess
from phase2.country import Country
from phase2.round import GuessFeedback, RoundStats

# NiceGUI elements go here

# display the game (guess input, guess feedback, timer, # of guesses, etc.)


def concat_data(feedback, data) -> str:
    return str(feedback) + "|" + str(data)


def list_to_str(items: list):
    return ", ".join(str(x) for x in items)


correct_bg = "bg-green-500 "
similar_bg = "bg-yellow-500 "
incorrect_bg = "bg-red-500 "

greater_than_arrow = r"clip-path: polygon(97% 40%,80% 40%,80% 95%,20% 95%,20% 40%,3% 40%,50% 5%)"
less_than_arrow = r"clip-path: polygon(98% 60%,80% 60%,80% 5%,20% 5%,20% 60%,3% 60%,50% 95%)"


def content():
    round_stats = RoundStats(mode="daily")

    options = []
    with open("src/game/countries.json") as file:
        options = json.load(file)

    ui.add_css("""
    .r-scroll-area-centered .q-scrollarea__content {
        align-items: center;
        justify-content: center;
    }
    """)

    def is_guess_valid(guess: str) -> str | None:
        """
        Validates the given guess, either returning an error
        message if it's invalid, or None if it's valid.
        """
        if guess.lower() not in options:
            return "Not a valid country!"
        if guess.lower() in round_stats.guessed_names:
            return "Already guessed!"
        return None

    def try_guess():
        """
        Validates an inputted guess and passes it into the guess handler
        if it's valid.
        """
        if guess_input.validate():
            handle_guess(guess_input.value, round_stats)
            guess_input.value = ""

    @round_stats.guess_graded.subscribe
    def display_feedback(country: Country, feedback: GuessFeedback):
        """
        Displays the feedback passed as an argument
        """

        with guesses:
            for attr, value in vars(feedback).items():
                classes = "aspect-square h-28 justify-center text-center p-0 "
                arrow_style = None
                # Style card based on the feedback given
                match value:
                    case "<":
                        classes += similar_bg
                        arrow_style = greater_than_arrow
                    case ">":
                        classes += similar_bg
                        arrow_style = less_than_arrow
                    case "partial":
                        classes += similar_bg
                if isinstance(value, bool):
                    if value:
                        classes += correct_bg
                    else:
                        classes += incorrect_bg

                # Create a card with the given style and the attribute formatted cleanly
                with ui.card(align_items="center").classes(classes):
                    if arrow_style:
                        ui.element("div").classes("absolute inset-0 bg-black/40").style(
                            arrow_style
                        ).mark("arrow")

                    attr_content = getattr(country, attr)
                    text = str(attr_content)
                    with ui.scroll_area().classes("r-scroll-area-centered"):
                        if attr == "name":
                            text = attr_content.title()
                        elif attr == "population":
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

    @round_stats.guess_error.subscribe
    def guess_error():
        """
        Displays a notification when there is some kind of problem handling
        a guess.
        """
        ui.notify("There was an issue processing that guess. Try something else!")

    @round_stats.game_ended.subscribe
    def display_results(won: bool):
        """
        Displays the game results pop-up
        """
        timer.cancel()
        guess_input.disable()
        submit.disable()

        if won:
            text = "Congratulations!"
        else:
            text = "Too bad!"

        with ui.dialog() as dialog, ui.card():
            ui.label(text)
            ui.label("The correct country was " + get_daily_country().name.title())
            ui.label(f"Time: {str(round_stats.round_length).split('.')[0]}")
            ui.label(f"Guesses: {round_stats.guesses}")
            ui.button("Close", on_click=dialog.close)

            # TODO: Display leaderboard/player stats here?

            dialog.open()

    with ui.column(align_items="center").classes("mx-auto p-4"):
        timer_text = ui.label("0:00:00").mark("timer")

        def update_timer():
            if not round_stats.start_time:
                return
            (
                timer_text.set_text(
                    f"{str(datetime.now(timezone.utc) - round_stats.start_time).split('.')[0]}"
                ),
            )

        timer = ui.timer(1.0, update_timer)

        guesses = ui.grid(columns=7).classes("w-full")

        with ui.card(align_items="center"):
            guess_input = (
                ui.input(
                    label="Guess",
                    placeholder="Enter a country",
                    autocomplete=options,
                    validation=is_guess_valid,
                )
                .without_auto_validation()
                .on("keydown.enter", try_guess)
            )
            submit = ui.button("Submit", on_click=try_guess)


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
