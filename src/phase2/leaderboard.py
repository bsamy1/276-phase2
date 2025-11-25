from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy import Integer, Interval, Sequence, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column

Base = declarative_base()


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entry"

    entry_id: Mapped[int] = mapped_column(Integer, Sequence("entry_id_seq"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # ForeignKey(user_id). once users table is linked

    daily_streak: Mapped[int] = mapped_column(
        Integer, default=0
    )  # current streak of dailies completed
    longest_daily_streak: Mapped[int] = mapped_column(
        Integer, default=0
    )  # highest daily streak ever recorded
    average_daily_guesses: Mapped[int] = mapped_column(Integer, default=0)
    average_daily_time: Mapped[timedelta] = mapped_column(
        Interval, default=0
    )  # average time to complete the daily in seconds
    longest_survival_streak: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, nullable=False)


class Leaderboard:
    def __init__(self, session: Session, stats_repo=None):
        self.session = session
        self.stats_repo = stats_repo

    async def sync_user_entry(self, user_id: int) -> LeaderboardEntry | None:
        """
        Creates a new LeaderboardEntry for the given user,
        If one already exist, then it simply updates  it.
        Stats are based on their statistics from StatisticsRepository
        """

        # gets stats from stats repo
        stats = self.stats_repo.get_leaderboard_stats_for_user(user_id)
        if stats is None:
            # no rounds recorded; nothing to sync
            return None

        # Look for an existing leaderboard entry
        entry: LeaderboardEntry | None = (
            self.session.execute(
                select(LeaderboardEntry).where(LeaderboardEntry.user_id == stats.user_id)
            )
            .scalars()
            .first()
        )

        # If it doesn't exist, create it
        if entry is None:
            entry = LeaderboardEntry(
                user_id=stats.user_id,
                daily_streak=stats.daily_streak,
                longest_daily_streak=stats.longest_daily_streak,
                average_daily_guesses=stats.average_daily_guesses,
                average_daily_time=stats.average_daily_time,
                longest_survival_streak=stats.longest_survival_streak,
                score=stats.score,
            )
            self.session.add(entry)

        # If it does exist, update it
        else:
            entry.daily_streak = stats.daily_streak
            entry.longest_daily_streak = stats.longest_daily_streak
            entry.average_daily_guesses = stats.average_daily_guesses
            entry.average_daily_time = stats.average_daily_time
            entry.longest_survival_streak = stats.longest_survival_streak

            if stats.score > entry.score:
                entry.score = stats.score

        try:
            self.session.commit()
            self.session.refresh(entry)
        except IntegrityError:
            self.session.rollback()
            return None

        return entry

    async def get_entry(self, user_id: int) -> LeaderboardEntry:
        """
        Get a leaderboard entry by user id
        """
        result = (
            self.session.execute(
                select(LeaderboardEntry).where(LeaderboardEntry.user_id == user_id)
            )
            .scalars()
            .first()
        )

        return result

    async def get_all(
        self,
    ) -> list[LeaderboardEntry]:
        """Get all users"""
        users = self.session.scalars(select(LeaderboardEntry)).all()
        return users

    async def get_top_10_entries(self) -> list[LeaderboardEntry]:
        """
        Gets top 10 leaderboard entries
        """
        stmt = select(LeaderboardEntry).order_by(LeaderboardEntry.score.desc()).limit(10)

        top10 = self.session.execute(stmt).scalars().all()

        return top10

    async def get_250_entries(self, position: int) -> list[LeaderboardEntry]:
        """
        Get 250 leaderboard entries from the given position (from the top)
        """
        offset_value = max(position - 1, 0)  # convert to 0-based offset

        stmt = (
            select(LeaderboardEntry)
            .order_by(LeaderboardEntry.score.desc())
            .offset(offset_value)
            .limit(250)
        )

        return self.session.execute(stmt).scalars().all()

    async def get_friend_entries(self, user_id: int) -> list[LeaderboardEntry]:
        """
        Get all leaderboard entries for the given user's friends only
        (including the given user)
        """

        #  TODO this one's a bit harder so still working on the logic for it

        pass

    async def get_score(self, user_id: int) -> int:
        """
        calculates user score
        """
        entry = (
            self.session.execute(
                select(LeaderboardEntry).where(LeaderboardEntry.user_id == user_id)
            )
            .scalars()
            .first()
        )

        if entry is None:
            return 0

        return entry.score


class LeaderboardEntrySchema(BaseModel):
    id: int
    user_id: int
    daily_streak: int
    longest_daily_streak: int
    average_daily_guesses: int
    average_daily_time: timedelta
    longest_survival_streak: int
