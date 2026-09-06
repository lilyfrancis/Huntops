import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class EmailSyncRun(Base):
    """Audit row for one email-bridge sync attempt.

    Kept separate from IngestionRun (which is per global source) because this
    is scoped to a single mailbox rather than a whole API feed.

    Exactly one of `mailbox_id` and `user_id` is set. New rows are written by
    the central admin-owned mailbox sync and carry `mailbox_id`; rows written
    before mailboxes existed carry `user_id` and are kept as history rather
    than deleted, so the ops page doesn't lose its past.
    """

    __tablename__ = "email_sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("alert_mailboxes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "success" | "error"
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
