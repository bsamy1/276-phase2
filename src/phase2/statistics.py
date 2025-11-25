import asyncio
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column
from sqlalchemy.types import Boolean, Date, Integer, Interval, String

from phase2.leaderboard import Leaderboard

Base = declarative_base()


class RoundStatistics(Base):
    __tablename__ = "round_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # entry id
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)  # user id to users table
    round_length: Mapped[timedelta] = mapped_column(Interval, nullable=False)  # length of round
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)  # won or lost
    guesses: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # number of guesses the round took
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # gamemode, daily/survival
    daily_date: Mapped[date] = mapped_column(Date, nullable=False)  # the day this daily took place
    survival_streak: Mapped[int] = mapped_column(Integer, nullable=False)


# non ORM LeaderboardStats class
class LeaderboardStats:
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


class RoundStatisticsRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_round(
        self,
        *,
        user_id: int,
        round_length: timedelta,
        won: bool,
        guesses: int,
        mode: str,
        daily_date: date,
        survival_streak: int = None,
    ) -> RoundStatistics:
        """
        Receives statistics for a round from the game,
        updates the user's stats table accordingly and
        returns the RoundStatistics instance
        """
        if not survival_streak:
            survival_streak = 0
        round_row = RoundStatistics(
            user_id=user_id,
            round_length=round_length,
            won=won,
            guesses=guesses,
            mode=mode,
            daily_date=daily_date,
            survival_streak=survival_streak,
        )

        self.session.add(round_row)  # log the round stats

        lb_repo = Leaderboard(self.session)
        lb_repo.stats_repo = self
        asyncio.run(lb_repo.sync_user_entry(user_id))

        self.session.commit()
        return round_row

    def get_daily_round(self, user_id: int, day: date) -> RoundStatistics:
        """
        Get a daily round's stats by user_id and the date
        """
        statement = select(RoundStatistics).where(
            RoundStatistics.user_id == user_id,
            RoundStatistics.mode == "daily",
            RoundStatistics.daily_date == day,
        )
        return self.session.execute(statement).scalars().one_or_none()

    def get_leaderboard_stats_for_user(self, user_id: int) -> LeaderboardStats or None:
        """
        Grab and put RoundStatistics rows for this user into a single
        LeaderboardStats object (same shape as FakeStats in tests).
        """
        statement = select(RoundStatistics).where(RoundStatistics.user_id == user_id)
        rounds = self.session.execute(statement).scalars().all()

        if not rounds:
            return None

        daily_rounds = [r for r in rounds if r.mode == "daily"]
        survival_rounds = [r for r in rounds if r.mode == "survival"]

        daily_streak = 0
        longest_daily_streak = 0
        average_daily_guesses = 0
        average_daily_time = timedelta()

        if daily_rounds:
            # get rounds sorted by date to check streaks
            daily_rounds_sorted = sorted(daily_rounds, key=lambda r: r.daily_date)

            # count current streak (ending at most recent day) and longest streak (of all time)
            current = 0
            for r in reversed(daily_rounds_sorted):
                average_daily_guesses += r.guesses
                average_daily_time += r.round_length
                if r.won:
                    current += 1
                    if current > longest_daily_streak:
                        longest_daily_streak = current
                else:
                    # Update the daily streak once when we reach the day it started
                    if not daily_streak:
                        daily_streak = current
                    current = 0

            # Update the daily streak if it wasn't updated in the loop
            if not daily_streak and daily_rounds_sorted[-1].won:
                daily_streak = current

            average_daily_guesses /= len(daily_rounds)
            average_daily_time /= len(daily_rounds)
        else:
            average_daily_guesses = 0
            average_daily_time = timedelta()

        longest_survival_streak = 0
        for r in survival_rounds:
            if r.survival_streak > longest_survival_streak:
                longest_survival_streak = r.survival_streak

        score = longest_survival_streak + longest_daily_streak

        return LeaderboardStats(
            user_id=user_id,
            daily_streak=daily_streak,
            longest_daily_streak=longest_daily_streak,
            average_daily_guesses=average_daily_guesses,
            average_daily_time=average_daily_time,
            longest_survival_streak=longest_survival_streak,
            score=score,
        )
