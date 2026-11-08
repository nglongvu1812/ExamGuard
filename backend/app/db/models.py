"""Base ORM models for system metadata and teacher profile foundation."""

from datetime import UTC, datetime

from app.db.base import Base
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class SystemMetadata(Base):
    """Stores schema metadata, install ID, and local settings flags."""

    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class TeacherProfile(Base):
    """Local teacher profile owning classrooms and exams."""

    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Giáo viên")
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
