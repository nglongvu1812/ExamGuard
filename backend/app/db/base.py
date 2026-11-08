"""SQLAlchemy declarative base and shared model metadata."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ExamGuard ORM models."""

    pass
