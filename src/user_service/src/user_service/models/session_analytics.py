import os
from datetime import date, datetime, timedelta, timezone
from typing import List

from fastapi import Depends
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Interval, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from shared.database import get_db

from .user import Base, User

AUTH_TTL_SECONDS = int(os.getenv("AUTH_TTL_SECONDS", "300"))


class SessionAnalytics(Base):
    """
    Model for a session and it's statistics. All times are in UTC.
    """

    __tablename__ = "session_analytics"

    # Identifying info
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Day associated with this session
    day: Mapped["DayAnalytics"] = relationship(back_populates="sessions")
    session_date: Mapped[date] = mapped_column(ForeignKey("day_analytics.date"))

    # Session stats
    _session_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    _session_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_length: Mapped[timedelta | None] = mapped_column(Interval)

    @hybrid_property
    def projected_end(self) -> datetime | None:
        """
        When this session is expected to expire based on AUTH_TTL_SECONDS.
        """
        if not self._session_start:
            return None
        return self._session_start + timedelta(seconds=AUTH_TTL_SECONDS)

    @hybrid_property
    def session_start(self) -> datetime:
        return self._session_start.astimezone(timezone.utc)

    @session_start.setter
    def session_start(self, start):
        self._session_start = start

    @hybrid_property
    def session_end(self) -> datetime:
        if self._session_end:
            return self._session_end.astimezone(timezone.utc)
        else:
            return None

    @session_end.setter
    def session_end(self, end):
        self._session_end = end

    @session_end.expression
    def session_end(cls):
        return cls._session_end


class DayAnalytics(Base):
    """
    Model for a specific day's stats and sessions
    """

    __tablename__ = "day_analytics"

    # Identifying info and sessions that took place on this day
    date: Mapped[date] = mapped_column(Date, primary_key=True, server_default=func.current_date())
    sessions: Mapped[List["SessionAnalytics"]] = relationship(back_populates="day")

    # Day stats
    min_session_length: Mapped[timedelta | None] = mapped_column(Interval)
    max_session_length: Mapped[timedelta | None] = mapped_column(Interval)
    mean_session_length: Mapped[timedelta | None] = mapped_column(Interval)
    current_active_users: Mapped[int] = mapped_column(Integer, default=0)
    max_active_users: Mapped[int] = mapped_column(Integer, default=0)


class SessionAnalyticsRepository:
    """
    Handles creating/starting, ending, and retrieving session data.
    """

    def __init__(self, session: Session):
        self.session = session

    async def create(self, user: User = None) -> SessionAnalytics:
        """
        Creates a session, with the given user if applicable. Cannot create a
        session if a user already has an active session.
        """
        # First check if there is a row in the day_analytics table for this date
        day_analytics = self.session.get(DayAnalytics, date.today())

        if not day_analytics:
            # Create a new day_analytics row to represent today
            day_analytics = DayAnalytics(date=date.today())
            self.session.add(day_analytics)
            self.session.commit()

        session_analytics = SessionAnalytics(session_date=day_analytics.date)

        # Update day analytics user stats
        day_analytics.current_active_users += 1

        if day_analytics.current_active_users > day_analytics.max_active_users:
            day_analytics.max_active_users = day_analytics.current_active_users

        if user:
            session_analytics.user_id = user.id

        self.session.add(session_analytics)
        self.session.commit()
        return session_analytics

    async def update_user_session(self, user: User) -> SessionAnalytics | None:
        """
        Extends the user's most recent active session by 5 minutes,
        and updates session_length and day's max_session_length.

        """

        # Accept either a User object or a raw user_id
        if isinstance(user, User):
            user_id = user.id
        else:
            user_id = int(user)

        # Ensure today's DayAnalytics exists
        day = self.session.get(DayAnalytics, date.today())
        if not day:
            day = DayAnalytics(date=date.today())
            self.session.add(day)
            self.session.commit()

        # 1Fetch the most recent session for this user
        latest = self.session.execute(
            select(SessionAnalytics)
            .where(SessionAnalytics.user_id == user_id)
            .order_by(SessionAnalytics._session_start.desc())
            .limit(1)
        ).scalar_one_or_none()

        if latest is None:
            return None

        # Refresh so that server_default (e.g. NOW() + INTERVAL) resolves to a real datetime
        self.session.refresh(latest)

        now = datetime.now(timezone.utc)

        # Move session end to now + TTL
        latest._session_end = now + timedelta(seconds=AUTH_TTL_SECONDS)

        # --- make both aware before subtracting ---
        start = latest._session_start
        # _session_start comes from DB as naive — make it UTC-aware
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        end = latest._session_end  # already aware

        latest.session_length = end - start

        # Update day analytics (max_session_length)
        if (day.max_session_length is None) or (latest.session_length > day.max_session_length):
            day.max_session_length = latest.session_length

        self.session.commit()
        return latest

    async def end(self, user: User = None, session_id: int = None) -> SessionAnalytics:
        """
        Ends the active session for the current user, if there
        is one available, and returns the now-inactive session.
        """
        session_analytics = await self.get(user=user, session_id=session_id)

        if not session_analytics:
            return None

        # Add the session_end column to the table, and record
        # the session length to mark this session as closed
        session_analytics.session_end = datetime.now(timezone.utc)
        session_analytics.session_length = (
            session_analytics.session_end - session_analytics.session_start
        )

        # Adjust the day's analytic stats accordingly
        day_analytics: DayAnalytics = session_analytics.day

        # Guard so we never go negative or crash on None
        day_analytics.current_active_users = max(0, (day_analytics.current_active_users) - 1)

        # No sessions have finished yet, so this is both the longest and shortest session
        if not day_analytics.min_session_length:
            day_analytics.min_session_length = session_analytics.session_length
            day_analytics.max_session_length = session_analytics.session_length
        # Minimum session length
        elif session_analytics.session_length < day_analytics.min_session_length:
            day_analytics.min_session_length = session_analytics.session_length
        # Maximum session length
        elif session_analytics.session_length > day_analytics.max_session_length:
            day_analytics.max_session_length = session_analytics.session_length

        # Session mean
        day_sessions = day_analytics.sessions
        total_session_length = timedelta()
        completed_sessions = 0
        for s in day_sessions:
            if s.session_end:
                total_session_length += s.session_length
                completed_sessions += 1

        day_analytics.mean_session_length = total_session_length / len(day_sessions)

        self.session.commit()

        return session_analytics

    async def get(self, user: User = None, session_id: int = None) -> SessionAnalytics:
        if session_id:
            # find session by session id
            stmt = select(SessionAnalytics).where(SessionAnalytics.id == session_id)
        elif user:
            # find most recent *active* session for this user
            stmt = (
                select(SessionAnalytics)
                .where(
                    SessionAnalytics.user_id == user.id,
                    SessionAnalytics._session_end.is_(None),
                )
                .order_by(SessionAnalytics._session_start.desc())
                .limit(1)
            )
        else:
            return None

        return self.session.scalar(stmt)

    async def min_session_length(self, day: date = date.today()) -> timedelta:
        if not day:
            day = date.today()

        day_obj = self.session.get(DayAnalytics, day)

        if not day_obj:
            return timedelta()

        return day_obj.min_session_length

    async def max_session_length(self, day: date = date.today()) -> timedelta:
        if not day:
            day = date.today()
        day_obj = self.session.get(DayAnalytics, day)

        if not day_obj:
            return timedelta()

        return day_obj.max_session_length

    async def mean_session_length(self, day: date = date.today()) -> timedelta:
        if not day:
            day = date.today()
        day_obj = self.session.get(DayAnalytics, day)

        if not day_obj:
            return timedelta()

        return day_obj.mean_session_length

    async def median_session_length(self, day: date = date.today()) -> timedelta:
        return await self.percentile_session_length(50, day)

    async def percentile_session_length(
        self, percentile: float, day: date = date.today()
    ) -> timedelta:
        if not day:
            day = date.today()
        day_obj = self.session.get(DayAnalytics, day)
        stmt = select(
            func.percentile_cont(percentile / 100)
            .within_group(SessionAnalytics.session_length)
            .filter(SessionAnalytics.day == day_obj)
            .filter(SessionAnalytics.session_end.is_not(None))
        )

        response = self.session.execute(stmt).scalar()

        if not response:
            return timedelta()

        return response

    async def get_current_active_users(self, day: date = date.today()) -> int:
        if not day:
            day = date.today()
        day_obj = self.session.get(DayAnalytics, day)

        if not day_obj:
            return 0

        return day_obj.current_active_users

    async def get_max_active_users(self, day: date = date.today()) -> int:
        if not day:
            day = date.today()
        day_obj = self.session.get(DayAnalytics, day)

        if not day_obj:
            return 0

        return day_obj.max_active_users


def get_session_analytics_repository(db: Session = Depends(get_db)) -> SessionAnalyticsRepository:
    return SessionAnalyticsRepository(db)
