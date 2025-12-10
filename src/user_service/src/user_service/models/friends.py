from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    and_,
    delete,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from shared.database import Base, get_db

from .user import User


class FriendRequest(Base):
    """
    Represents a friend request between two users
    """

    __tablename__ = "friend_requests"
    __table_args__ = (UniqueConstraint("requestor_id", "requestee_id", name="unique_requests"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requestor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    requestee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String, default="pending")
    sent_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class FriendshipRepository:
    """
    Handles friend requests and friendship logic.
    """

    def __init__(self, session: Session):
        self.session = session

    async def send_request(self, requestor_id: int, requestee_id: int):
        """Creates a new friend request."""
        request = FriendRequest(requestor_id=requestor_id, requestee_id=requestee_id)
        self.session.add(request)
        try:
            self.session.commit()
            return request
        except IntegrityError:
            self.session.rollback()
            return None

    async def accept_request(self, request_id: int):
        """Accepts a friend request."""
        stmt = update(FriendRequest).where(FriendRequest.id == request_id).values(status="accepted")
        self.session.execute(stmt)
        self.session.commit()

    async def get_friendship_status(self, id: int, id2: int, status: str = None) -> FriendRequest:
        """Gets the friendship status between two users"""

        pair_cond = or_(
            and_(
                FriendRequest.requestor_id == id,
                FriendRequest.requestee_id == id2,
            ),
            and_(
                FriendRequest.requestor_id == id2,
                FriendRequest.requestee_id == id,
            ),
        )

        stmt = select(FriendRequest).where(pair_cond)
        if status:
            stmt = stmt.where(FriendRequest.status == status)

        found = self.session.execute(stmt).scalar()
        return found

    async def get_requests(self, id: int) -> list[FriendRequest]:
        """Gets all friend requests sent to a user."""
        stmt = (
            select(FriendRequest)
            .where(FriendRequest.requestee_id == id)
            .where(FriendRequest.status == "pending")
        )
        results = self.session.execute(stmt).scalars().all()
        return results

    async def get_unanswered_requests(self, id: int) -> list[FriendRequest]:
        "Gets friend requests that are unanswered"
        stmt = (
            select(FriendRequest)
            .where(FriendRequest.requestor_id == id)
            .where(FriendRequest.status == "pending")
        )
        results = self.session.execute(stmt).scalars().all()
        return results

    async def get_all_requests(self):
        """Returns all friend requests."""
        return self.session.scalars(select(FriendRequest)).all()

    async def list_friends(self, user_id: int):
        """Return User models that are friends with user_id"""
        pair_cond = or_(
            and_(FriendRequest.requestor_id == user_id, FriendRequest.requestee_id == User.id),
            and_(FriendRequest.requestee_id == user_id, FriendRequest.requestor_id == User.id),
        )
        stmt = select(User).join(FriendRequest, pair_cond).where(FriendRequest.status == "accepted")
        return self.session.execute(stmt).scalars().all()

    async def get_friend_by_id(self, user_id: int, friend_id: int):
        pair_cond = or_(
            and_(FriendRequest.requestor_id == user_id, FriendRequest.requestee_id == friend_id),
            and_(FriendRequest.requestee_id == user_id, FriendRequest.requestor_id == friend_id),
        )
        stmt = (
            select(User)
            .where(User.id == friend_id)
            .join(FriendRequest, pair_cond)
            .where(FriendRequest.status == "accepted")
        )
        return self.session.execute(stmt).scalars().first()

    async def get_friend_by_name(self, user_id: int, friend_name: str):
        pair_cond = or_(
            and_(FriendRequest.requestor_id == user_id, FriendRequest.requestee_id == User.id),
            and_(FriendRequest.requestee_id == user_id, FriendRequest.requestor_id == User.id),
        )
        stmt = (
            select(User)
            .where(User.name == friend_name)
            .join(FriendRequest, pair_cond)
            .where(FriendRequest.status == "accepted")
        )
        return self.session.execute(stmt).scalars().first()

    async def delete_friendship(self, user_id: int, friend_id: int) -> bool:
        pair_cond = or_(
            and_(FriendRequest.requestor_id == user_id, FriendRequest.requestee_id == friend_id),
            and_(FriendRequest.requestee_id == user_id, FriendRequest.requestor_id == friend_id),
        )
        stmt = delete(FriendRequest).where(pair_cond)
        res = self.session.execute(stmt)
        self.session.commit()
        return res.rowcount and res.rowcount > 0


def get_friendship_repository(
    db: Session = Depends(get_db),
) -> FriendshipRepository:
    return FriendshipRepository(db)
