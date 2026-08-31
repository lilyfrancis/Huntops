import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import InterviewStatus


class InterviewSession(Base):
    """One mock-interview run for a user, optionally tailored to a specific job.

    Unlike Outreach there is deliberately no unique (user, job) constraint —
    practising the same role repeatedly is the entire point, and each attempt
    should keep its own transcript and scores so progress is visible.
    """

    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Denormalized at start time so the transcript still reads correctly after
    # an aggregated job ages out of the feed (same pattern as Job.employer_name).
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status"), nullable=False, default=InterviewStatus.in_progress
    )
    average_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    turns: Mapped[list["InterviewTurn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewTurn.position"
    )


class InterviewTurn(Base):
    """One question in a session, plus the candidate's answer and its grading.

    All questions are generated up front so the session has a fixed, known
    length — the user is charged once at the start and can never be stranded
    mid-interview by a later AI failure or an empty credit balance.
    """

    __tablename__ = "interview_turns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    improvements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[InterviewSession] = relationship(back_populates="turns")
