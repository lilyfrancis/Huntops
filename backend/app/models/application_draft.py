import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class ApplicationDraft(Base):
    """A cover letter and résumé bullets written for one job, before applying.

    Separate from Application because it exists *before* one — the whole
    point is reading and editing what will be sent. It also survives an
    application being withdrawn, and one exists for jobs the user never
    applies to at all.

    One per (user, job), like Outreach: the draft is a paid model call, so
    re-opening a job must not re-charge for it.
    """

    __tablename__ = "application_drafts"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_draft_user_job"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    cover_letter: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bullets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Whether the person changed it. Regenerating silently over someone's own
    # writing is the one thing this must never do without asking.
    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc),
    )
