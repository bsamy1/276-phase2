from datetime import date, datetime, time, timedelta

import pytest
from shared.database import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from phase2.leaderboard import LeaderboardEntry
from phase2.round import RoundStats
from phase2.statistics import RoundStatistics, RoundStatisticsRepository


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
    yield RoundStatisticsRepository(session)


def test_get_nonexistent_stats(repo):
    assert not repo.get_leaderboard_stats_for_user(0)


async def test_add_round(repo, session):
    user_id = 1
    today = date(2025, 11, 20)

    round_stats = RoundStats(mode="daily")
    round_stats.start_round()
    round_stats.end_round()
    round_stats.user_id = user_id
    round_stats.won = True
    round_stats.guesses = 4
    round_stats.start_time = datetime.combine(today, time())
    round_stats.round_length = timedelta(seconds=30)

    result = await repo.add_round(round_stats)

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


async def test_get_daily_round(repo, session):
    today = date(2024, 11, 20)

    round_stats = RoundStats(mode="daily")
    round_stats.start_round()
    round_stats.end_round()
    round_stats.user_id = 1
    round_stats.won = True
    round_stats.guesses = 4
    round_stats.start_time = datetime.combine(today, time())

    created = await repo.add_round(round_stats)
    fetched = repo.get_daily_round(user_id=1, day=today)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.user_id == 1
    assert fetched.daily_date == today


async def test_get_leaderboard_stats_for_user(repo):
    today = date(2024, 11, 20)

    round_stats = RoundStats(mode="daily")
    round_stats.start_round()
    round_stats.end_round()
    round_stats.user_id = 1
    round_stats.won = True
    round_stats.guesses = 4
    round_stats.start_time = datetime.combine(today, time())

    created = await repo.add_round(round_stats)

    stats = repo.get_leaderboard_stats_for_user(user_id=1)

    assert stats
    assert stats.average_daily_guesses == created.guesses
    assert stats.average_daily_time == created.round_length
    assert stats.daily_streak == 1
    assert stats.longest_survival_streak == 0

    # Test daily streak counting
    round_stats.daily_date = today + timedelta(days=1)
    created = await repo.add_round(round_stats)

    stats = repo.get_leaderboard_stats_for_user(user_id=1)

    assert stats.daily_streak == 2

    # Test daily streak breaking
    round_stats.daily_date = today + timedelta(days=2)
    round_stats.won = False
    created = await repo.add_round(round_stats)

    stats = repo.get_leaderboard_stats_for_user(user_id=1)

    assert stats.daily_streak == 0
