from datetime import datetime, timedelta, timezone

from fastapi import Depends
from joserfc import jwt
from joserfc.errors import ExpiredTokenError
from joserfc.jwk import RSAKey
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import ForeignKey, Integer, String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from shared.database import Base, get_db


class Auth(Base):
    """
    Representation of an 'authentication' for any currently authenticated users, or
    users that have previously been authenticated.
    """

    __tablename__ = "auths"
    id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    token: Mapped[str] = mapped_column(String)


class AuthRepository:
    # More hardcoded values lol

    def __init__(self, session: Session):
        self.session = session
        self.key = RSAKey.generate_key()

    async def create(self, user_id: int, expiry: datetime = None) -> str:
        """Creates a JSON web token with the given arguments, then adds
        it to the `auths` table before returning the token.

        Keyword arguments:
        user_id -- The `id` corresponding to a valid user in the `users` table.
        expiry -- The UTC time this token will expire. Must be in the future,
                  and no more than an hour ahead.
        """

        # No expiry time given; default to an hour
        if expiry is None:
            expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        # Expiry time has already passed; invalid request
        if expiry < datetime.now(timezone.utc):
            return None

        # Expiry time is longer than an hour; invalid request
        if expiry - datetime.now(timezone.utc) > timedelta(hours=1):
            return None

        # Delete any existing tokens for this user
        await self.delete(user_id)

        # Create, sign, and return a new token for this user
        header = {"alg": "RS256"}
        payload = {"sub": str(user_id), "exp": expiry}
        token = jwt.encode(header, payload, self.key)

        new_token = Auth(id=user_id, token=token)
        self.session.add(new_token)
        self.session.commit()

        return token

    async def delete(self, id: int):
        stmt = delete(Auth).where(Auth.id == id)
        self.session.execute(stmt)

        self.session.commit()

    async def delete_by_token(self, token: str):
        # Decode the token to access the user ID
        data = jwt.decode(token, self.key)

        user_id = data.claims["sub"]

        await self.delete(user_id)

    async def get_by_id(self, id: int) -> Auth:
        auth = self.session.scalar(select(Auth).where(Auth.id == id))
        return auth

    async def validate(self, token: str) -> bool:
        data = jwt.decode(token, self.key)

        user_id = data.claims["sub"]

        # Verify that we still have this token in the database
        entry = await self.get_by_id(user_id)
        if not entry:
            return False
        if entry.token != token:
            return False

        # Checks the that 'sub' field contains the correct user id
        claims_requests = JWTClaimsRegistry(
            sub={"essential": True, "value": user_id},
        )

        # Validate the claims relating the this token, including whether or not it's expired
        try:
            claims_requests.validate(data.claims)
        except ExpiredTokenError:
            await self.delete_by_token(token)
            return False

        return True


def get_auth_repository(db: Session = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)
