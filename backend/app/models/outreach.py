import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import OutreachStatus


class Outreach(Base):
    """One outreach attempt per (user, job) — cached like JobQuick's
    boost/message features, so re-opening the same job never re-drafts (and
    never re-charges credits for) the same pitch."""

    __tablename__ = "outreach"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_outreach_user_job"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("recruiter_contacts.id", ondelete="SET NULL"), nullable=True
    )

    email_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_bullets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[OutreachStatus] = mapped_column(Enum(OutreachStatus, name="outreach_status"), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
