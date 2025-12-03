
from nicegui import ui
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import httpx

API_BASE_URL = "http://localhost:8000"  # same style as leaderboard


def fetch_session_analytics() -> List[Dict[str, Any]]:
    """Try to fetch all session analytics otherwise fallback to fake data."""

    try:
        with httpx.Client(base_url=API_BASE_URL, timeout=2.0) as client:
            response = client.get("/session-analytics")
            response.raise_for_status()
            rows = response.json()

        return rows

    except Exception:
        # use fake data if backend is missing
        pass

    # Fake data
    now = datetime.now()

    rows: List[Dict[str, Any]] = [
        {
            "user_id": 1,
            "session_date": date.today(),
            "session_start": now - timedelta(minutes=30),
            "session_end": now,
            "session_length": timedelta(minutes=30),
        },
        {
            "user_id": 2,
            "session_date": date.today(),
            "session_start": now - timedelta(hours=10, minutes=15),
            "session_end": now - timedelta(minutes=5),
            "session_length": timedelta(hours=1, minutes=10),
        },
        {
            "user_id": None,
            "session_date": date.today() - timedelta(days=1),
            "session_start": now - timedelta(days=1, minutes=5),
            "session_end": None,          
            "session_length": None,
        },
    ]

    return rows

def session_analytics_page() -> None:
    ui.label('Session Analytics').classes('text-2xl font-bold mb-4')

    table = ui.table(
        title='Sessions',
        columns=[
            {'name': 'session_date',   'label': 'Date',   'field': 'session_date'},
            {'name': 'user_id',        'label': 'User ID','field': 'user_id'},
            {'name': 'session_start',  'label': 'Start',  'field': 'session_start'},
            {'name': 'session_end',    'label': 'End',    'field': 'session_end'},
            {'name': 'session_length', 'label': 'Length', 'field': 'session_length'},
        ],
        rows=[],
        row_key='id',
    ).classes('w-full')

    def load_data():
        rows = []

        for r in fetch_session_analytics():
            if r["session_date"]:
                session_date = r["session_date"].strftime("%Y-%m-%d")
            else:
                session_date = ""

            if r["session_start"]:
                start = r["session_start"].strftime("%Y-%m-%d %H:%M:%S")
            else:
                start = ""

            if r["session_end"]:
                end = r["session_end"].strftime("%Y-%m-%d %H:%M:%S")
            else:
                end = ""


            if r["session_length"]:
                length = str(r["session_length"])
            else:
                length = ""

            rows.append(
                {
                    "session_date": session_date,
                    "user_id": r["user_id"] or "None",
                    "session_start": start,
                    "session_end": end,
                    "session_length": length,
                }
            )

        table.rows = rows

    ui.button('Refresh', on_click=load_data).classes('mt-2')
    load_data()

if __name__ in {"__main__", "__mp_main__"}:
    session_analytics_page()
    ui.run()