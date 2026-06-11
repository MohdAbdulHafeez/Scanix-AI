from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from core.config import settings


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    """
    pass


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DATABASE_ECHO,
    future=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency.

    Usage:
        db: Session = Depends(get_db)
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def create_tables() -> None:
    """
    Create all registered tables.

    Used during local development.
    Alembic migrations should be used
    in staging and production.
    """

    Base.metadata.create_all(bind=engine)