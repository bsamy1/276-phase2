from pydantic import BaseModel
from sqlalchemy import Float, Integer, Sequence, select
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column

Base = declarative_base()

class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entry"

    entry_id: Mapped[int] = mapped_column(Integer, Sequence('entry_id_seq'), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False) # ForeignKey(user_id). once users table is linked

    daily_streak: Mapped[int] = mapped_column(
        Integer, default=0)  # current streak of dailies completed
    longest_daily_streak:  Mapped[int] = mapped_column(
        Integer)  # highest daily streak ever recorded
    average_daily_guesses:  Mapped[int] = mapped_column(Integer)
    average_daily_time: Mapped[float] = mapped_column(
        Float)  # average time to complete the daily in seconds
    longest_survival_streak: Mapped[int] = mapped_column(Integer)


class Leaderboard:

    def __init__(self, session: Session):
        self.session = session

    async def create_user_entry(user_id: int):
        """
        Creates a new LeaderboardEntry for the given user,
        if one doesn't already exit
        """
        pass

    async def update_user_entry(user_id: int):
        """
        Updates a user's leaderboard stats based on their statistics
        from StatisticsRepository
        """
        pass

    async def get_entry(user_id: int) -> LeaderboardEntry:
        """
        Get a leaderboard entry by user id
        """
        pass

    async def get_all(self) -> list[LeaderboardEntry]:
        """Get all users"""
        users = self.session.scalars(select(LeaderboardEntry)).all()
        return users


    async def get_top_10_entry(position: int) -> LeaderboardEntry:
        """
        Gets top 10 leaderboard entries
        """

    async def get_250_entries(position: int) -> list[LeaderboardEntry]:
        """
        Get 250 leaderboard entries from the given position (from the top)
        """
        pass

    async def get_friend_entries(user_id: int) -> list[LeaderboardEntry]:
        """
        Get all leaderboard entries for the given user's friends only
        (including the given user)
        """
        pass

class LeaderboardEntrySchema(BaseModel):
    id: int
    user_id: int
    daily_streak: int
    longest_daily_streak: int
    average_daily_guesses: int
    average_daily_time: float
    longest_survival_streak: int
