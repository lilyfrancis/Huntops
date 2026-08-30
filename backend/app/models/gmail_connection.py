import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class GmailConnection(Base):
    """One user's Gmail OAuth grant, tokens encrypted at rest.

    Job Engine ran against a single hand-configured mailbox. Every field here
    exists because that assumption breaks for a real multi-tenant product:
    each user brings their own account, their own consent, their own tokens.
    """

    __tablename__ = "gmail_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    access_token_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # The Gmail-assigned id for the label we created (e.g. "Label_17"), used
    # to scope message queries to only what the user's alert filters routed.
    label_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
