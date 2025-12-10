import logging
import os

from fastapi import Depends, Request
from nicegui import APIRouter, app, ui

from user_service.models.user import (
    UserRepository,
    UserSchema,
    get_user_repository,
)

logger = logging.getLogger("uvicorn.error")


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SESSION_STORAGE_NAME = os.getenv("ADMIN_SESSION_STORAGE_NAME", "admin_session")

router = APIRouter(prefix="/admin")


@ui.refreshable
async def user_list(user_repo: UserRepository) -> None:
    user_models = await user_repo.get_all()
    users = []
    for model in user_models:
        users.append(UserSchema.from_db_model(model).model_dump())

    ui.label(f"All Users ({len(users)})")

    """
    Selected is used in both `delete()` and `toggle_delete_button()`, where
    it is accessed as a global variable
    """
    selected = []  # noqa: F841

    async def delete():
        global selected
        for user in selected:
            result = await user_repo.delete(user["name"])
            if result.rowcount > 0:
                ui.notify(f"Deleted user '{user['name']}'")
                grid.update()
            else:
                ui.notify(f"Unable to delete user `{user['name']}'")

        user_list.refresh()

    button = ui.button(on_click=delete, icon="delete")

    button.disable()

    async def toggle_delete_button():
        global selected
        selected = await grid.get_selected_rows()
        if len(selected) > 0:
            button.enable()
        else:
            button.disable()

    """
    Options defined here are used for the AGGrid that displays the user info.
    """
    grid_options = {
        "columnDefs": [
            {
                "headerName": "ID",
                "field": "id",
                "sortable": "true",
                "initialSort": "asc",
            },
            {
                "headerName": "Name",
                "field": "name",
                "sortable": "true",
            },
            {
                "headerName": "Email",
                "field": "email",
                "sortable": "true",
            },
            {
                "headerName": "Password (pretend you don't see this.)",
                "field": "password",
                "sortable": "false",
            },
        ],
        "rowData": users,
        "rowSelection": {"mode": "multiRow"},
        "paginaton": "true",
    }

    grid = ui.aggrid(grid_options).on("rowSelected", toggle_delete_button)


@router.page("/login")
async def login(request: Request):
    # redirect to admin page if user has valid cookie session
    if app.storage.user.get(SESSION_STORAGE_NAME, False):
        ui.navigate.to("/admin")
        return

    ui.label("Admin Login").classes("text-2xl mt-8")
    password = ui.input("Password", password=True)

    def auth():
        if password.value == ADMIN_PASSWORD:
            # set cookies for user session as logged in (valid)
            app.storage.user.update({SESSION_STORAGE_NAME: True})
            ui.navigate.to("/admin")
        else:
            ui.notify("Incorrect password")

    ui.button("Login", on_click=auth)


@router.page("/")
async def index(request: Request, user_repo: UserRepository = Depends(get_user_repository)):
    # check if user has valid cookie session; if not, redirect to login
    if not app.storage.user.get(SESSION_STORAGE_NAME, False):
        ui.notify("Please login")
        ui.navigate.to("/admin/login")
        return

    async def create() -> None:
        if not name.value or not email.value or not password.value:
            ui.notify("Please fill all fields", color="red")
            return

        await user_repo.create(
            name=name.value,
            email=email.value,
            password=password.value,
        )

        name.value = ""
        email.value = ""
        password.value = ""
        ui.notify("User created successfully!")
        user_list.refresh()

    with ui.column().classes("mx-auto w-full max-w-md space-y-4 p-4"):
        ui.label("Create New User").classes("text-xl font-bold mb-2")

        name = ui.input(label="Name")
        email = ui.input(label="Email")
        password = ui.input(label="Password", password=True, password_toggle_button=True)
        ui.button("Add User", on_click=create, icon="add")
        await user_list(user_repo)


@router.page("/logout")
def logout():
    # delete cookie session and redirect to login page
    app.storage.user.update({SESSION_STORAGE_NAME: False})
