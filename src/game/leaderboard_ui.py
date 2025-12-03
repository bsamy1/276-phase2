import logging
from typing import Any, Dict, List

from fastapi import Depends
from nicegui import APIRouter, ui

from game import repos
from phase2.leaderboard import (
    LeaderboardEntrySchema,
    LeaderboardRepository,
    get_leaderboard_repository,
)

logger = logging.getLogger("game.leaderboard_ui")
router = APIRouter(prefix="/leaderboard")


async def fetch_leaderboard():
    """Try to fetch leaderboard from backend; fallback to fake data."""
    leaderboard_repo: LeaderboardRepository = repos["leaderboard_repo"]
    entry_models = await leaderboard_repo.get_all()

    entries = []
    if entry_models:
        for entry in entry_models:
            entries.append(LeaderboardEntrySchema.from_db_model(entry).model_dump())
        return entries

    # Fake data
    rows: List[Dict[str, Any]] = [
        {
            "entry_id": 1,
            "user_id": "Bob",
            "daily_streak": 3,
            "longest_daily_streak": 7,
            "average_daily_guesses": 4,
            "average_daily_time": "35.2s",
            "longest_survival_streak": 9,
            "high_score": 1234,
        },
        {
            "entry_id": 2,
            "user_id": "Charlie",
            "daily_streak": 1,
            "longest_daily_streak": 5,
            "average_daily_guesses": 3,
            "average_daily_time": "28.0s",
            "longest_survival_streak": 12,
            "high_score": 1450,
        },
        {
            "entry_id": 3,
            "user_id": "Amy",
            "daily_streak": 10,
            "longest_daily_streak": 12,
            "average_daily_guesses": 2,
            "average_daily_time": "19.7s",
            "longest_survival_streak": 20,
            "high_score": 2005,
        },
        {
            "entry_id": 4,
            "user_id": "Dave",
            "daily_streak": 0,
            "longest_daily_streak": 1,
            "average_daily_guesses": 5,
            "average_daily_time": "42.0s",
            "longest_survival_streak": 4,
            "high_score": 980,
        },
    ]

    return rows


@router.page("/")
async def leaderboard_page(
    leaderboard_repo: LeaderboardRepository = Depends(get_leaderboard_repository),
):
    ui.label("Leaderboard").classes("text-3xl font-bold mb-4")

    columns = [
        {"name": "rank", "label": "Rank", "field": "rank", "sortable": True},
        {"name": "user_id", "label": "User_ID", "field": "user_id", "sortable": True},
        {
            "name": "daily_streak",
            "label": "Daily Streak",
            "field": "daily_streak",
            "sortable": True,
        },
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
        {
            "name": "longest_survival_streak",
            "label": "Survival Streak",
            "field": "longest_survival_streak",
            "sortable": True,
        },
        {"name": "high_score", "label": "High Score", "field": "high_score", "sortable": True},
    ]
    new_rows = await fetch_leaderboard()

    table = ui.table(
        columns=columns,
        rows=new_rows,
        row_key="entry_id",
    ).classes("w-full")

    async def load_data():
        table.rows = await fetch_leaderboard()

    async def load_friends_leaderboard():
        user_id = 1
        new_rows = await fetch_friends_leaderboard(leaderboard_repo, user_id)
        print(new_rows)
        table.rows = new_rows

    ui.button("Refresh", on_click=load_data).classes("mt-4")
    ui.button("Load friends leaderboard", on_click=load_friends_leaderboard)


async def fetch_friends_leaderboard(leaderboard_repo: LeaderboardRepository, user_id: int | None):
    """Fetch friends-only leaderboard data using Leaderboard class."""
    print("called")
    if not user_id:
        user_id = 1

    entries = await leaderboard_repo.get_friends_entries(user_id)
    if entries:
        return entries

        entries = [
            {
                "entry_id": 3,
                "user_id": "Amy",
                "daily_streak": 10,
                "longest_daily_streak": 12,
                "average_daily_guesses": 2,
                "average_daily_time": "19.7s",
                "longest_survival_streak": 20,
                "high_score": 2005,
            },
            {
                "entry_id": 4,
                "user_id": "Dave",
                "daily_streak": 0,
                "longest_daily_streak": 1,
                "average_daily_guesses": 5,
                "average_daily_time": "42.0s",
                "longest_survival_streak": 4,
                "high_score": 980,
            },
        ]

    return entries


if __name__ in {"__main__", "__mp_main__"}:
    leaderboard_page()
    ui.run()
