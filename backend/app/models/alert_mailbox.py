import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AlertMailbox(Base):
    """An admin-owned mailbox that receives job-alert email for one market.

    This is the supply side of the product. Job seekers never connect an inbox;
    the operator points HuntOps at a handful of mailboxes — one subscribed to
    Canadian alerts, one to UK, one to Nigerian — and every user's feed is drawn
    from that shared pool, filtered by what they asked for at signup.

    Read over IMAP rather than a provider API. These are the operator's own
    mailboxes, so there is nobody to ask for consent, and IMAP keeps the whole
    thing off any single provider's review process and off their per-seat
    pricing. Any host that speaks IMAP works.

    Deliberately not the same table as GmailConnection. That one is a user's own
    OAuth grant used to send outreach as them; this is operator infrastructure
    used to receive supply. Different owners, different lifetimes, different
    blast radii — collapsing them would mean a user deleting their account could
    take a market's whole feed with it.
    """

    __tablename__ = "alert_mailboxes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Unique so re-adding an already-configured mailbox updates it rather than
    # creating a duplicate that would double every job it ingests.
    email_address: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    # The market this mailbox's alerts are for, e.g. "Canada". Every job
    # ingested through it inherits this, which is what lets a user in Canada
    # ask for Canadian supply without us having to geo-parse each listing.
    market: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Optional narrowing: a mailbox subscribed only to marketing alerts can say
    # so. Empty means "any lane" — the lane is then inferred per job from its
    # title, as it always was.
    lanes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # ---- IMAP connection ----
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    # Usually the same as email_address, but plenty of hosts use a separate
    # login (a bare local part, or an entirely different account name).
    imap_username: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_password_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False)
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    imap_folder: Mapped[str] = mapped_column(String(255), nullable=False, default="INBOX")

    # ---- incremental sync bookkeeping ----
    # Extraction costs an AI call per message, so re-reading mail already seen
    # is money spent for an answer we have. UIDVALIDITY is stored alongside
    # because a server that renumbers a folder invalidates every stored UID,
    # and resuming from a stale one would silently skip real mail.
    # BigInteger: UIDs are 32-bit unsigned and long-lived mailboxes climb.
    last_seen_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uid_validity: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Nullable and SET NULL: which admin added it is provenance, not ownership.
    # Deleting a departed admin's account must not delete the mailbox every
    # user's feed depends on.
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
