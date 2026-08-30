import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class RecruiterContact(Base):
    """One Apollo-discovered recruiter per job, shared across every user who
    targets that job — not per-user. Recruiter identity is a property of the
    job/company, so caching it here means the second, third, and Nth user to
    reach out to the same job never spends another Apollo reveal credit."""

    __tablename__ = "recruiter_contacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    apollo_person_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
