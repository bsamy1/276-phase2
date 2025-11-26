import logging
import os

from nicegui import ui
from nicegui.events import KeyEventArguments

from game import game_ui
from game.daily import get_daily_country
from game.leaderboard_ui import leaderboard_page

logger = logging.getLogger("phase2")



class LogElementHandler(logging.Handler):
    """A logging handler that emits messages to a log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:  # pragma: no cover
        self.element = element
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            msg = self.format(record)
            self.element.push(msg)
        except Exception:
            self.handleError(record)


FORMAT = logging.Formatter(
    "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s] %(levelname)s: %(message)s"
)


@ui.page("/")
def index_page():
    # Code to allow a log window to be displayed during the game by pressing 'l'
    def enable_logger():
        log_window.visible = not log_window.visible

    # Handles keyboard inputs
    def handle_key(e: KeyEventArguments):
        if e.action.keydown:
            if e.key == "l" and not e.action.repeat:
                enable_logger()

    # Creates an element at the bottom of the screen to display the log
    with ui.page_sticky(position="bottom", expand=True) as log_window:
        log_element = ui.log(max_lines=10).classes("w-full h-48")

    # Binds the the logger to the log element through the LogElementHandler class
    if os.environ.get("NICEGUI_USER_SIMULATION") or os.environ.get("NICEGUI_SCREEN_TEST_PORT"):
        # Just assign to a standard log handler if we're testing
        handler = logging.StreamHandler()
    else:
        handler = LogElementHandler(log_element)  # pragma: no cover
    handler.setFormatter(FORMAT)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Ensure that the handler is removed when a client disconnects
    ui.context.client.on_disconnect(lambda: logger.removeHandler(handler))
    log_window.visible = False

    logger.info("Initialized")
    logger.info(f"Today's daily country is {get_daily_country().name.title()}")

    ui.keyboard(on_key=handle_key)

    game_ui.content()



@ui.page("/leaderboard")
def _():
    leaderboard_page()



ui.run(title="CMPT276 Project", dark=None)
