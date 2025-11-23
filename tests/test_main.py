from nicegui import ui
from nicegui.events import GenericEventArguments
from nicegui.testing import User

pytest_plugins = ["nicegui.testing.user_plugin"]


async def test_logger(user: User):
    await user.open("/")

    await user.should_not_see(kind=ui.page_sticky)

    # Manually trigger the keyboard's event handler because NiceGUI currently
    # has no better way to do it (read https://nicegui.io/documentation/keyboard for details)
    keyboard = user.find(ui.keyboard).elements.pop()
    args = GenericEventArguments(
        sender=keyboard,
        client=user.client,
        args={
            "action": "keydown",
            "repeat": False,
            "altKey": False,
            "ctrlKey": False,
            "metaKey": False,
            "shiftKey": False,
            "key": "l",
            "code": "KeyL",
            "location": 0,
        },
    )
    keyboard._handle_key(args)

    await user.should_see(kind=ui.page_sticky)
