from shared.database import Base
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    friend_id: Mapped[int] = mapped_column(Integer, nullable=False)
