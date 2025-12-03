import json
from datetime import datetime, timezone

from nicegui import app, ui

from game import repos
from game.daily import get_daily_country, handle_guess
from game.leaderboard_ui import fetch_leaderboard
from phase2.account_ui import SESSION_STORAGE_NAME as USER_SESSION_STORAGE
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
    round_stats.stats_repo = repos["stats_repo"]

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
        elif guess.lower() in round_stats.guessed_names:
            return "Already guessed!"
        else:
            return None

    async def try_guess():
        """
        Validates an inputted guess and passes it into the guess handler
        if it's valid.
        """
        if guess_input.validate():
            val = guess_input.value
            guess_input.value = ""
            await handle_guess(val, round_stats)

    @round_stats.guess_graded.subscribe
    def display_feedback(country: Country, feedback: GuessFeedback):
        """
        Displays the feedback passed as an argument
        """
        guess_display.text = f"{round_stats.guesses}/{round_stats.max_guesses} guesses"

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
    async def display_results(won: bool):
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

        with ui.dialog() as dialog, ui.card(align_items="center").style("max-width: none"):
            ui.label(text)
            ui.label("The correct country was " + get_daily_country().name.title())
            ui.label(f"Time: {str(round_stats.round_length).split('.')[0]}")
            ui.label(f"Guesses: {round_stats.guesses}")

            # Display leaderboard only if user is logged in
            if app.storage.user.get(USER_SESSION_STORAGE, False):
                await popup_leaderboard("daily")
            ui.button("Close", on_click=dialog.close)

            dialog.open()

    def go_to_account():
        user_session = app.storage.user.get(USER_SESSION_STORAGE, False)
        if user_session.get("user"):
            ui.navigate.to("/account")
        else:
            ui.navigate.to("/login?redirect_to=/account")

    with ui.page_sticky(position="top-right", x_offset=20, y_offset=20):
        with ui.button(icon="menu"):
            with ui.menu().props("auto-close") as menu:
                ui.menu_item("Account", go_to_account)
                ui.separator()
                ui.menu_item("Close", menu.close)

    with ui.column(align_items="center").classes("mx-auto p-4 h-screen"):
        ui.label("CountryClue").classes("text-h2")
        timer_text = ui.label("0:00:00").classes("text-h6").mark("timer")

        def update_timer():
            if not round_stats.start_time:
                return
            (
                timer_text.set_text(
                    f"{str(datetime.now(timezone.utc) - round_stats.start_time).split('.')[0]}"
                ),
            )

        timer = ui.timer(1.0, update_timer)

        guesses = ui.grid(columns=7).classes("w-full text-center")
        with guesses:
            ui.label("Country Name")
            ui.label("Population")
            ui.label("Size")
            ui.label("Region")
            ui.label("Currencies")
            ui.label("Language(s)")
            ui.label("Timezone(s)")

        with ui.card(align_items="center").classes("mt-auto"):

            def clear_input_error():
                guess_input.error = None

            guess_display = ui.label(f"{round_stats.guesses}/{round_stats.max_guesses} guesses")
            guess_input = (
                ui.input(
                    label="Guess",
                    placeholder="Enter a country",
                    autocomplete=options,
                    validation=is_guess_valid,
                    on_change=clear_input_error,
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


async def popup_leaderboard(mode: str):
    columns = [
        {"name": "user_id", "label": "Player", "field": "user_id", "sortable": True},
        {
            "name": "daily_streak",
            "label": "Daily Streak",
            "field": "daily_streak",
            "sortable": True,
        },
    ]

    if mode == "daily":
        columns = columns + [
            {
                "name": "longest_daily_streak",
                "label": "Longest Daily Streak",
                "field": "longest_daily_streak",
                "sortable": True,
            },
            {
                "name": "average_daily_guesses",
                "label": "Avg Guesses",
                "field": "average_daily_guesses",
                "sortable": True,
            },
            {
                "name": "average_daily_time",
                "label": "Avg Time",
                "field": "average_daily_time",
                "sortable": True,
            },
        ]

    elif mode == "survival":
        columns.append(
            {
                "name": "longest_survival_streak",
                "label": "Survival Streak",
                "field": "longest_survival_streak",
                "sortable": True,
            }
        )
    new_rows = await fetch_leaderboard()
    table = ui.table(columns=columns, rows=new_rows, row_key="entry_id", pagination=10)

    user_session = app.storage.user.get(USER_SESSION_STORAGE, False)
    user_id = user_session["user"].id
    row_index = None
    # Iterate through table until finding the correct entry
    for i, entry in enumerate(new_rows):
        if entry["user_id"] == user_id:
            row_index = i
    if not row_index:
        return

    # Jump to page containing the given user
    target_page = (row_index // 10) + 1
    table.pagination = {"rowsPerPage": 10, "page": target_page}

    # Scroll to user's entry
    table.run_method("scrollTo", row_index)


# button to open account management menu
"""
account management

    - create account
    - see account stats
    - edit account info (username/password/email)
    - friends/friend requests
"""
