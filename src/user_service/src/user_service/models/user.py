import bcrypt
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import Integer, String, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from shared.database import Base, get_db


class User(Base):
    """
    User model used by SQLAlchemy to interact with the database. When you look
    up a user in the database, you will get an instance of this class back.
    This is the database's view of users.
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)  # stores hashed password
    


class UserRepository:
    """
    How the code talks to the database, initialization of this class gives us
    an SQLAlchemy Session that exposes CRUD
    methods (create, read, update, delete) for the users table.
    These methods are called in the front-end main.py file
    """

    """
    Controls manipulation of the users table.
    """

    def __init__(self, session: Session):
        self.session = session

    # Create user and add user to users table
    async def create(self, name: str, email: str, password: str) -> User | None:
        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        new_user = User(name=name, email=email, password=hashed_pw)
        self.session.add(new_user)

        # Attempts to commit changes to the database, catching an error if it
        # fails to make sure that this isn't a duplicate user.
        try:
            self.session.commit()
            self.session.refresh(new_user)
            return new_user
        except IntegrityError:
            self.session.rollback()
            return None

    async def delete(self, name: str) -> None:
        stmt = delete(User).where(User.name == name)
        result = self.session.execute(stmt)
        self.session.commit()
        return result

    async def delete_by_id(self, id: int) -> bool:
        stmt = delete(User).where(User.id == id)
        result = self.session.execute(stmt)
        self.session.commit()

        return result.rowcount > 0

    async def get_all(self) -> list[User]:
        """Get all users"""
        users = self.session.scalars(select(User)).all()
        return users

    async def get_by_name(self, name: str) -> User:
        """Get user by name"""
        user = self.session.scalar(select(User).where(User.name == name))
        return user

    async def get_by_id(self, id: int) -> User:
        """Get user by Id"""
        user = self.session.scalar(select(User).where(User.id == id))
        return user

    async def change_password(self, id: int, curr_password: str, new_password: str) -> bool:
        user = await self.get_by_id(id)

        # Verifying that the user inputted correct password
        if not bcrypt.checkpw(curr_password.encode(), user.password):
            return False

        user.password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        self.session.commit()
        return True

    async def update_user(self, id: int, **fields) -> User:
        if not fields:
            return self.session.scalar(select(User).where(User.id == id))
        try:
            self.session.execute(update(User).where(User.id == id).values(**fields))
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return None

        return self.session.scalar(select(User).where(User.id == id))


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


class UserSchema(BaseModel):
    """
    The application's view of users. This is how the API represents users (as
    opposed to how the database represents them).
    """

    id: int | None = None
    name: str
    email: str
    password: str

    @classmethod
    def from_db_model(cls, user: User) -> "UserSchema":
        """Create a UserSchema from a User"""
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            password="********",  
        )
