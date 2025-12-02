from datetime import date, timedelta

import pytest
from shared.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from phase2.friends import Friendship
from phase2.leaderboard import Leaderboard, LeaderboardEntry
from phase2.statistics import RoundStatistics


@pytest.fixture(scope="function")
def engine():
    engine = create_engine("sqlite:///:memory:?check_same_thread=False")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def session(engine):
    conn = engine.connect()
    conn.begin()
    db = Session(bind=conn)
    yield db
    db.rollback()
    conn.close()


@pytest.fixture(scope="function")
def repo(session):
    yield Leaderboard(session)


class FakeStats:
    def __init__(
        self,
        user_id: int,
        daily_streak: int,
        longest_daily_streak: int,
        average_daily_guesses: int,
        average_daily_time: timedelta,
        longest_survival_streak: int,
        score: int,
    ):
        self.user_id = user_id
        self.daily_streak = daily_streak
        self.longest_daily_streak = longest_daily_streak
        self.average_daily_guesses = average_daily_guesses
        self.average_daily_time = average_daily_time
        self.longest_survival_streak = longest_survival_streak
        self.score = score


class FakeStatsRepo:
    def __init__(self, stats_by_user: dict[int, FakeStats]):
        self._stats_by_user = stats_by_user

    def get_leaderboard_stats_for_user(self, user_id: int):
        return self._stats_by_user.get(user_id)


def create_entry(
    session: Session,
    user_id: int,
    score: int,
    daily_streak: int = 0,
    longest_daily_streak: int = 0,
    average_daily_guesses: int = 0,
    average_daily_time: timedelta = timedelta(),
    longest_survival_streak: int = 0,
) -> LeaderboardEntry:
    """Helper to create a LeaderboardEntry directly in the DB."""
    entry = LeaderboardEntry(
        user_id=user_id,
        score=score,
        daily_streak=daily_streak,
        longest_daily_streak=longest_daily_streak,
        average_daily_guesses=average_daily_guesses,
        average_daily_time=average_daily_time,
        longest_survival_streak=longest_survival_streak,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry



def add_round(db, user_id, won=True, guesses=3, mode="daily", streak=1):
    """Insert a RoundStatistics row."""
    row = RoundStatistics(
        user_id=user_id,
        round_length=timedelta(seconds=60),
        won=won,
        guesses=guesses,
        mode=mode,
        daily_date=date.today(),
        survival_streak=streak,
    )
    db.add(row)
    db.commit()


@pytest.mark.asyncio
async def test_sync_user_entry_creates_new_entry(repo, session):
    user_id = 1

    fake_stats = FakeStats(
        user_id=user_id,
        daily_streak=3,
        longest_daily_streak=5,
        average_daily_guesses=4,
        average_daily_time=timedelta(seconds=12.5),
        longest_survival_streak=7,
        score=42,
    )

    repo.stats_repo = FakeStatsRepo({user_id: fake_stats})

    entry = await repo.sync_user_entry(user_id)

    assert entry is not None
    assert entry.user_id == user_id
    assert entry.daily_streak == 3
    assert entry.longest_daily_streak == 5
    assert entry.average_daily_guesses == 4
    assert entry.average_daily_time == timedelta(seconds=12.5)
    assert entry.longest_survival_streak == 7
    # use high_score or score depending on what your model actually has:
    assert entry.score == 42  # or entry.score == 42


@pytest.mark.asyncio
async def test_get_entry_returns_entry_when_exists(repo, session):
    """
    get_entry should return the correct LeaderboardEntry when one exists for the user_id.
    """
    # Arrange: create an entry directly in the DB
    created = create_entry(session, user_id=10, score=123)

    # Act
    entry = await repo.get_entry(10)

    # Assert
    assert entry is not None
    assert isinstance(entry, LeaderboardEntry)
    assert entry.entry_id == created.entry_id
    assert entry.user_id == 10
    assert entry.score == 123


@pytest.mark.asyncio
async def test_get_entry_returns_none_when_missing(repo):
    """
    get_entry should return None when there is no entry for the given user_id.
    """
    entry = await repo.get_entry(999)  # some user_id that doesn't exist
    assert entry is None


@pytest.mark.asyncio
async def test_get_top_10_entries_empty(repo):
    """
    get_top_10_entries should return an empty list when no entries exist.
    """
    top10 = await repo.get_top_10_entries()
    assert top10 == []


@pytest.mark.asyncio
async def test_get_top_10_entries_returns_top_10(repo, session):
    """
    get_top_10_entries should return the highest 10 entries by score.
    """
    # Create 15 entries with increasing scores
    for i in range(15):
        create_entry(session, user_id=i, score=i)

    top10 = await repo.get_top_10_entries()

    # Should only contain 10 entries
    assert len(top10) == 10

    # Scores should be from 14 down to 5
    scores = [entry.score for entry in top10]
    assert scores == list(range(14, 4, -1))


@pytest.mark.asyncio
async def test_get_250_entries_from_position_50(repo, session):
    """
    get_250_entries(position=50) should skip the first 49 entries (positions 1–49)
    and return entries ranked 50 to 299.
    """

    # Create 400 entries with scores equal to user_id
    for i in range(400):
        create_entry(session, user_id=i, score=i)

    # Act
    entries = await repo.get_250_entries(position=50)

    # Assert length
    assert len(entries) == 250

    # Extract scores
    scores = [e.score for e in entries]

    # Expected range:
    # Rank 50 = score 350
    # Rank 299 = score 101
    expected_scores = list(range(350, 100, -1))

    assert scores == expected_scores


@pytest.mark.asyncio
async def test_get_friends_entries_returns_sorted_results(session):
    db = session
    
    # Setup: user 1 is friends with 2 and 3
    db.add_all([
        Friendship(user_id=1, friend_id=2),
        Friendship(user_id=1, friend_id=3),
    ])
    db.commit()

    leaderboard = Leaderboard(db)

    # Insert leaderboard entries directly with known scores
    # user 2 → highest score
    # user 1 → medium
    # user 3 → lowest
    db.add_all([
        LeaderboardEntry(user_id=1, score=50),
        LeaderboardEntry(user_id=2, score=100),
        LeaderboardEntry(user_id=3, score=10),
    ])
    db.commit()

    # Act
    entries = leaderboard.get_friends_entries(1)

    # Assert
    assert len(entries) == 3

    # Sorted by score DESCENDING
    assert [e.user_id for e in entries] == [2, 1, 3]