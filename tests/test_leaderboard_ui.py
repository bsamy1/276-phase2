from typing import Any, Dict, List
from unittest.mock import patch

import httpx
import pytest
from nicegui import ui
from nicegui.testing import User

from game import leaderboard_ui
from game.leaderboard_ui import fetch_leaderboard

pytest_plugins = ["nicegui.testing.user_plugin"]



# GUI TESTS
async def test_leaderboard_page_loads(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """The leaderboard page should render with a title, table, and refresh button."""
    fake_rows: List[Dict[str, Any]] = [
        {
            "entry_id": 1,
            "user_id": "Bob",
            "daily_streak": 3,
            "longest_daily_streak": 7,
            "average_daily_guesses": 4,
            "average_daily_time": "35.2s",
            "longest_survival_streak": 9,
            "high_score": 1234,
            "rank": 1,
        }
    ]

    def fake_fetch() -> List[Dict[str, Any]]:
        return fake_rows
    
    monkeypatch.setattr(leaderboard_ui, "fetch_leaderboard", fake_fetch)

    await user.open("/leaderboard")

    await user.should_see("Leaderboard")   
    await user.should_see("Refresh")      
    await user.should_see(kind=ui.table)   #


async def test_leaderboard_refresh_button(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Clicking the Refresh button should keep the page usable
    """
    fake_rows: List[Dict[str, Any]] = [
        {
            "entry_id": 1,
            "user_id": "Bob",
            "daily_streak": 3,
            "longest_daily_streak": 7,
            "average_daily_guesses": 4,
            "average_daily_time": "35.2s",
            "longest_survival_streak": 9,
            "high_score": 1234,
            "rank": 1,
        }
    ]

    def fake_fetch() -> List[Dict[str, Any]]:
        return fake_rows

    monkeypatch.setattr(leaderboard_ui, "fetch_leaderboard", fake_fetch)

    await user.open("/leaderboard")

    user.find("Refresh").click()

    await user.should_see("Leaderboard")
    await user.should_see(kind=ui.table)


# Non-GUI tests for fetch_leaderboard (HTTP-based)
class DummyResponse:
    """Minimal fake httpx response object for testing."""
    def __init__(self, json_data: List[Dict[str, Any]], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self) -> List[Dict[str, Any]]:
        return self._json_data


class DummyClient:
    """Context-manager fake for httpx.Client used in the success-path test."""
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._response: DummyResponse | None = None

    def __enter__(self) -> "DummyClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def set_response(self, response: DummyResponse) -> None:
        self._response = response

    def get(self, path: str) -> DummyResponse:
        assert path == "/leaderboard"
        assert self._response is not None
        return self._response

# Will update these when the DB is wired
def test_fetch_leaderboard_with_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the backend works, fetch_leaderboard should use its data, sort it, and add ranks."""
    backend_rows: List[Dict[str, Any]] = [
        {"entry_id": 1, "user_id": "X", "daily_streak": 3},
        {"entry_id": 2, "user_id": "Y", "daily_streak": 10},
        {"entry_id": 3, "user_id": "Z", "daily_streak": 1},
    ]

    dummy_client = DummyClient(base_url="http://example.com", timeout=2.0)
    dummy_client.set_response(DummyResponse(backend_rows))

    # monkeypatch httpx.Client used inside leaderboard_ui
    def fake_client(*args, **kwargs):
        return dummy_client

    monkeypatch.setattr(leaderboard_ui.httpx, "Client", fake_client)

    result = fetch_leaderboard()

    # same number of entries
    assert len(result) == 3

    # sorted by daily_streak DESC
    streaks = [e["daily_streak"] for e in result]
    assert streaks == [10, 3, 1]

    # ranks assigned 1..n
    ranks = [e["rank"] for e in result]
    assert ranks == [1, 2, 3]

    # using backend user_ids, not fallback ones
    user_ids = {e["user_id"] for e in result}
    assert user_ids == {"X", "Y", "Z"}


def test_fetch_leaderboard_with_fallback_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the HTTP client fails, fetch_leaderboard should return the local fake data."""

    # Make httpx.Client itself blow up so we hit the except block
    def fake_client(*args, **kwargs):
        raise httpx.ConnectError("boom", request=None)

    monkeypatch.setattr(leaderboard_ui.httpx, "Client", fake_client)

    rows = fetch_leaderboard()

    # Fallback data has 4 rows in your code
    assert len(rows) == 4

    # Fallback rows sorted by daily_streak DESC
    streaks = [e["daily_streak"] for e in rows]
    assert streaks == sorted(streaks, reverse=True)

    # The top entry should be Amy with highest streak (10) and rank 1
    top = rows[0]
    assert top["user_id"] == "Amy"
    assert top["daily_streak"] == 10
    assert top["rank"] == 1


# Non-GUI test for fetch_friends_leaderboard
def test_fetch_friends_leaderboard(monkeypatch: pytest.MonkeyPatch) -> None:

    from game.leaderboard_ui import fetch_friends_leaderboard

    fake_user_id = 42

    # Mock DB connection
    patcher = patch("phase2.leaderboard.get_db")
    mock_db = patcher.start()
    mock_db.return_value = None

    result = fetch_friends_leaderboard(fake_user_id)

    mock_db.assert_called_once()

    # Returned rows
    assert result

    patcher.stop()