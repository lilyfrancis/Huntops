import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index, JSON, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import ApplicationStatus, ConciergeStatus


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),
        # Declared here as well as in the migration so autogenerate does not
        # propose dropping it. Partial, because the queue only ever reads
        # concierge rows and they are a small slice of the table.
        Index(
            "ix_applications_concierge_queue",
            "concierge_status",
            postgresql_where=text("is_concierge"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized at apply-time, same pattern as Job.employer_name/company_name —
    # an employer reviewing applicants needs a name, not a bare candidate_id.
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_email: Mapped[str] = mapped_column(String(255), nullable=False)

    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What went with this submission, not what the draft says now: a draft
    # can be edited afterwards, and the record of what was sent must not
    # change retroactively.
    tailored_bullets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), nullable=False, default=ApplicationStatus.pending
    )

    # Concierge: the user asked us to file this one for them on a site we
    # cannot submit to programmatically. Null on a direct application, which
    # is how the admin queue tells the two apart.
    is_concierge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concierge_status: Mapped[ConciergeStatus | None] = mapped_column(
        Enum(ConciergeStatus, name="concierge_status"), nullable=True
    )
    # Shown to the user, so it is written for them: "listing was taken down",
    # not an internal shorthand.
    concierge_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Populated starting Phase 2 (AI screening); nullable for now.
    ai_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
