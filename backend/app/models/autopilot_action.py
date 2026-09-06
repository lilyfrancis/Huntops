import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AutopilotAction(Base):
    """One thing autopilot did (or refused to do) on a user's behalf.

    Autopilot acts without asking, so it owes the user a receipt. Skips are
    recorded as well as successes: "why didn't it apply to this?" is the
    question people actually ask, and it is unanswerable from a table that
    only stores wins. It is also the dedupe key — a job that already has a
    row for this user is never acted on twice.
    """

    __tablename__ = "autopilot_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    action: Mapped[str] = mapped_column(String(20), nullable=False)  # "apply" | "outreach"
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "done" | "skipped" | "failed"
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
