import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

engine = None


class Base(DeclarativeBase):
    pass


def get_db():
    global engine

    if not engine:
        DATABASE_URL = os.environ["DATABASE_URL"]

        engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
