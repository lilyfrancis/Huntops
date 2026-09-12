import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AlertSender(Base):
    """A domain whose mail counts as a job alert.

    Lives in the database rather than an environment variable because opening a
    market means meeting boards nobody anticipated — Bayt for the UAE, Reed for
    the UK, Jobberman for Nigeria. As config this was a redeploy every time,
    which put a developer in the loop for what is really an operations task.

    Mail from anything not listed here is skipped without an AI call, so a
    missing entry is a board whose alerts are silently discarded. The mailbox
    reports which domains it passed over precisely so this list can be fixed
    from the same screen.
    """

    __tablename__ = "alert_senders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Bare domain, e.g. "linkedin.com". Subdomains match automatically, so
    # jobalerts.linkedin.com is covered without its own row.
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Free text, e.g. "UK" or "Gulf" — purely to keep the list readable once it
    # runs to thirty entries across six markets.
    note: Mapped[str | None] = mapped_column(String(100), nullable=True)

    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
