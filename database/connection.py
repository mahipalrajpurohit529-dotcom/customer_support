"""
database/connection.py
------------------------
Owns the SQLAlchemy engine, session factory, and declarative Base for
the MySQL database.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError(
        "Missing database configuration. Ensure DB_USER, DB_PASSWORD, "
        "and DB_NAME are set in your .env file."
    )

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# pool_pre_ping avoids "MySQL server has gone away" errors on stale
# connections by testing them before use.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI-style dependency: yields a session and always closes it,
    even if the caller raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context-manager version of get_db(), for use outside of FastAPI's
    dependency injection (e.g. inside the Database Agent / LangChain
    tool, which aren't request handlers).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()