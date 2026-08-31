import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source_url", name="uq_jobs_source_url"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Nullable so a future aggregation/email-bridge worker (Phase 2) can insert
    # jobs with no internal employer — those are distinguished by `source`.
    employer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    salary_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType, name="job_type"), nullable=False)
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(ExperienceLevel, name="experience_level"), nullable=False
    )

    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    application_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # "internal" for employer-posted jobs; Phase 2 adds "remotive", "remoteok", etc.
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="internal")
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    lane: Mapped[JobLane | None] = mapped_column(Enum(JobLane, name="job_lane"), nullable=True, index=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Heuristic geographic restriction extracted at ingest time, e.g. "US", "UK".
    # Null means no restriction detected (open to apply from anywhere).
    restricted_to: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Ghost-job detection (Phase 8). Null score means "not yet scanned" — the
    # scanner backfills on a schedule, since staleness signals accrue over time.
    ghost_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ghost_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ghost_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
