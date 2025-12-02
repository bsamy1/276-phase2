from typing import Any, Dict, List

import httpx  # Will update to getting directly from DB once wired
from nicegui import ui

from phase2.leaderboard import get_leaderboard_repository

API_BASE_URL = "http://localhost:8000" 


def fetch_leaderboard() -> List[Dict[str, Any]]:
    """Try to fetch leaderboard from backend; fallback to fake data."""

    try:
        with httpx.Client(base_url=API_BASE_URL, timeout=2.0) as client:
            response = client.get("/leaderboard")
            response.raise_for_status()
            entries = response.json()

        entries.sort(key=lambda e: e["daily_streak"], reverse=True)
        for i, e in enumerate(entries, start=1):
            e["rank"] = i

        return entries

    except Exception:
        # Backend is missing / unreachable → fallback to fake
        pass

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

    # sort by daily streak + rank
    rows.sort(key=lambda e: e["daily_streak"], reverse=True)
    for i, e in enumerate(rows, start=1):
        e["rank"] = i

    return rows


def leaderboard_page() -> None:
    ui.label("Leaderboard").classes("text-3xl font-bold mb-4")

    columns = [
        {"name": "rank", "label": "Rank", "field": "rank", "sortable": True},
        {"name": "user_id", "label": "User_ID", "field": "user_id", "sortable": True},
        {"name": "daily_streak", "label": "Daily Streak", 
         "field": "daily_streak", "sortable": True},
        {"name": "longest_daily_streak", "label": "Longest Daily Streak", 
         "field": "longest_daily_streak", "sortable": True},
        {"name": "average_daily_guesses", "label": "Avg Guesses", 
         "field": "average_daily_guesses", "sortable": True},
        {"name": "average_daily_time", "label": "Avg Time", 
         "field": "average_daily_time", "sortable": True},
        {"name": "longest_survival_streak", "label": "Survival Streak", \
         "field": "longest_survival_streak", "sortable": True},
        {"name": "high_score", "label": "High Score", 
         "field": "high_score", "sortable": True},
    ]

    table = ui.table(
        columns=columns,
        rows=fetch_leaderboard(),  
        row_key="entry_id",
    ).classes("w-full")

    def load_data():
        table.rows = fetch_leaderboard()

    def load_friends_leaderboard():
        user_id = 1
        new_rows = fetch_friends_leaderboard(user_id)
        print(new_rows)
        table.rows = new_rows

    ui.button("Refresh", on_click=load_data).classes("mt-4")
    ui.button("Load friends leaderboard", on_click=load_friends_leaderboard)

def fetch_friends_leaderboard(user_id: int | None):
    """Fetch friends-only leaderboard data using Leaderboard class."""
    print("called")
    if not user_id:
        user_id = 1

    try:
        lb = get_leaderboard_repository()
        entries = lb.get_friends_entries(user_id)
    except AttributeError:
        entries = [{
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
        },]
    
    return entries

        

if __name__ in {"__main__", "__mp_main__"}:
    leaderboard_page()
    ui.run()
