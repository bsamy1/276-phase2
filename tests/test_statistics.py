from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from phase2.leaderboard import Base as LeaderboardBase
from phase2.leaderboard import LeaderboardEntry
from phase2.statistics import Base as StatsBase
from phase2.statistics import RoundStatistics, RoundStatisticsRepository


@pytest.fixture(scope="function")
def engine():
    engine = create_engine("sqlite:///:memory:?check_same_thread=False")
    StatsBase.metadata.create_all(bind=engine)
    LeaderboardBase.metadata.create_all(bind=engine)
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
    yield RoundStatisticsRepository(session)


def test_get_nonexistent_stats(repo):
    assert not repo.get_leaderboard_stats_for_user(0)


def test_add_round(repo, session):
    user_id = 1
    today = date(2025, 11, 20)

    result = repo.add_round(
        user_id=user_id,
        round_length=timedelta(seconds=30),
        won=True,
        guesses=4,
        mode="daily",
        daily_date=today,
    )
    assert isinstance(result, RoundStatistics)
    assert result.user_id == user_id
    assert result.mode == "daily"
    assert result.daily_date == today
    assert result.round_length == timedelta(seconds=30)

    statement = select(LeaderboardEntry).where(LeaderboardEntry.user_id == user_id)
    entry = session.execute(statement).scalars().one()

    assert entry.daily_streak == 1
    assert entry.longest_daily_streak == 1
    assert entry.average_daily_guesses == 4
    assert entry.average_daily_time == result.round_length


def test_get_daily_round(repo, session):
    today = date(2024, 11, 20)

    created = repo.add_round(
        user_id=1,
        round_length=timedelta(seconds=75),
        won=True,
        guesses=4,
        mode="daily",
        daily_date=today,
    )
    fetched = repo.get_daily_round(user_id=1, day=today)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.user_id == 1
    assert fetched.daily_date == today


def test_get_leaderboard_stats_for_user(repo):
    today = date(2024, 11, 20)
    created = repo.add_round(
        user_id=1,
        round_length=timedelta(seconds=75),
        won=True,
        guesses=3,
        mode="daily",
        daily_date=today,
    )

    stats = repo.get_leaderboard_stats_for_user(user_id=1)

    assert stats
    assert stats.average_daily_guesses == created.guesses
    assert stats.average_daily_time == created.round_length
    assert stats.daily_streak == 1
    assert stats.longest_survival_streak == 0

    # Test daily streak counting
    created = repo.add_round(
        user_id=1,
        round_length=timedelta(seconds=30),
        won=True,
        guesses=3,
        mode="daily",
        daily_date=today + timedelta(days=1),
    )

    stats = repo.get_leaderboard_stats_for_user(user_id=1)

    assert stats.daily_streak == 2

    # Test daily streak breaking
    created = repo.add_round(
        user_id=1,
        round_length=timedelta(seconds=30),
        won=False,
        guesses=5,
        mode="daily",
        daily_date=today + timedelta(days=1),
    )

    stats = repo.get_leaderboard_stats_for_user(user_id=1)

    assert stats.daily_streak == 0
