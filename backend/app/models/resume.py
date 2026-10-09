import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class Resume(Base):
    """One of a user's CVs.

    Several per person, because one CV cannot do two jobs. Somebody applying
    for engineering roles and sales roles has two different stories to tell,
    and sending the sales CV to a backend role wastes the application — which
    is the one thing this product exists to stop wasting. Which CV a given
    job uses is decided by `lanes`, in `services/resume_selection.py`.
    """

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Not unique: a user may hold several. The old one-per-user constraint is
    # what this model outgrew.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # What the person calls it — "Engineering", "Sales". Shown wherever a CV
    # has to be chosen, so it is theirs to write rather than derived.
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="My CV")

    # The job families this CV is for, as JobLane values. A job whose lane is
    # in here uses this CV. Empty means it is not claimed by any lane and is
    # only reached as the fallback.
    lanes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # The fallback, for a job whose lane no CV claims. Exactly one per user:
    # enforced in the service rather than the schema, because the window
    # where a user has none — between deleting one and promoting another —
    # has to be survivable rather than a 500.
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    parsed_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    achievements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
