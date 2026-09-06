import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AlertMailbox(Base):
    """An admin-owned Gmail account that receives job-alert email for one market.

    This is the supply side of the product. Job seekers never connect an inbox;
    the operator connects a handful of mailboxes — one subscribed to Canadian
    alerts, one to UK, one to Nigerian — and every user's feed is drawn from
    that shared pool, filtered by what they said they wanted at signup.

    Deliberately *not* the same table as GmailConnection. That one is a user's
    own grant used to send outreach as them; this one is operator infrastructure
    used to receive supply. They have different owners, different lifetimes and
    different blast radii, and collapsing them would mean a user deleting their
    account could take a market's whole feed with it.
    """

    __tablename__ = "alert_mailboxes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The Google account this grant belongs to, resolved from the userinfo
    # endpoint at connect time. Unique so re-running the OAuth flow for an
    # already-connected mailbox refreshes it instead of creating a duplicate
    # that would double every job it ingests.
    email_address: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    # The market this mailbox's alerts are for, e.g. "Canada". Every job
    # ingested through it inherits this, which is what lets a user in Canada
    # ask for Canadian supply without us having to geo-parse each listing.
    market: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Optional narrowing: a mailbox subscribed only to marketing alerts can say
    # so, and jobs from it are tagged with those lanes. Empty means "any lane" —
    # the lane is then inferred per job from its title, as it always was.
    lanes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    access_token_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Nullable and SET NULL: which admin connected it is provenance, not
    # ownership. Deleting a departed admin's account must not delete the
    # mailbox every user's feed depends on.
    connected_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
