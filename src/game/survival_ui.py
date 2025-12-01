import json
from datetime import datetime, timezone

from nicegui import ui
from phase2.survival import (
    SurvivalStats,
    handle_survival_guess,
    survival_mode,
)

from phase2.country import Country
from phase2.round import GuessFeedback, RoundStats  


def survival_content():
    """Main UI content for survival mode"""
    survival_stats, round_stats = survival_mode()

    options = []
    with open("src/game/countries.json") as file:
        options = json.load(file)

    ui.add_css("""
    .r-scroll-area-centered .q-scrollarea__content {
        align-items: center;
        justify-content: center;
    }
    """)

    correct_bg = "bg-green-500 "
    similar_bg = "bg-yellow-500 "
    incorrect_bg = "bg-red-500 "
    greater_than_arrow = r"clip-path: polygon(97% 40%,80% 40%,80% 95%,20% 95%,20% 40%,3% 40%,50% 5%)"
    less_than_arrow = r"clip-path: polygon(98% 60%,80% 60%,80% 5%,20% 5%,20% 60%,3% 60%,50% 95%)"

    def list_to_str(items: list):
        return ", ".join(str(x) for x in items)

    def is_guess_valid(guess: str) -> str | None:
        """Validates the given guess"""
        if guess.lower() not in options:
            return "Not a valid country!"
        elif guess.lower() in round_stats.guessed_names:
            return "Already guessed!"
        else:
            return None

    async def try_guess():
        """Validates and processes a guess"""
        if guess_input.validate():
            val = guess_input.value
            guess_input.value = ""
            await handle_survival_guess(val, round_stats, survival_stats)

    @round_stats.guess_graded.subscribe
    def display_feedback(country: Country, feedback: GuessFeedback):
        """Display feedback for the guess"""
        with guesses:
            for attr, value in vars(feedback).items():
                classes = "aspect-square h-28 justify-center text-center p-0 "
                arrow_style = None

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

        # Update stats display
        update_stats()

        # Show notification
        if feedback.name:
            ui.notify("✅ Correct! New country loaded.", type="positive")
        else:
            remaining = round_stats.max_guesses - round_stats.guesses
            if remaining > 0:
                ui.notify(f"❌ Wrong! {remaining} guesses left", type="warning")

    @round_stats.guess_error.subscribe
    def guess_error():
        """Display error notification"""
        ui.notify("There was an issue processing that guess. Try something else!")

    @round_stats.game_ended.subscribe
    def display_results(won: bool):
        """Display game over dialog"""
        timer.cancel()
        guess_input.disable()
        submit.disable()

        with ui.dialog() as dialog, ui.card(align_items="center").style("max-width: none"):
            ui.label("Game Over! 💀").classes("text-2xl font-bold")
            ui.label(f"Final Streak: {survival_stats.streak}").classes("text-xl")
            ui.label(f"Countries Guessed: {survival_stats.total_countries_guessed}")

            if round_stats.round_length:
                time_str = str(round_stats.round_length).split(".")[0]
                ui.label(f"Time: {time_str}")

            ui.button("Close", on_click=dialog.close)

        dialog.open()

    def update_stats():
        """Update lives and streak displays"""
        hearts = "❤️ " * survival_stats.lives
        lives_label.set_text(f"Lives: {hearts}")
        streak_label.set_text(f"Streak: {survival_stats.streak} 🔥")

    with ui.column(align_items="center").classes("mx-auto p-4"):
        ui.label("Survival Mode").classes("text-3xl font-bold")

        # Stats row
        with ui.row().classes("gap-8 mb-4"):
            lives_label = ui.label()
            streak_label = ui.label()

        update_stats()

        # Timer
        timer_text = ui.label("0:00:00").mark("timer")

        def update_timer():
            if not round_stats.start_time:
                return
            timer_text.set_text(
                f"{str(datetime.now(timezone.utc) - round_stats.start_time).split('.')[0]}"
            )

        timer = ui.timer(1.0, update_timer)

        # Guesses grid
        guesses = ui.grid(columns=7).classes("w-full")

        # Input card
        with ui.card(align_items="center"):

            def clear_input_error():
                guess_input.error = None

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

        # Instructions
        with ui.card().classes("w-full max-w-2xl p-4 mt-4"):
            ui.label("How to Play:").classes("font-bold text-lg")
            ui.label("• You start with 3 lives")
            ui.label("• Guess the country correctly to continue")
            ui.label("• You have 5 guesses per country")
            ui.label("• Lose a life if you run out of guesses")
            ui.label("• Earn a bonus life every 5 correct guesses")
            ui.label("• Game ends when you run out of lives")

        # Navigation button
        ui.button("Back to Menu", on_click=lambda: ui.navigate.to("/"))