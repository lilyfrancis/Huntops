import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class UserPreference(Base):
    """What this user asked the engine to hunt for, chosen at signup.

    The feed is a shared pool fed by admin-owned alert mailboxes, so without
    this row every user would see every market's supply. A marketer in Canada
    picks Canada + marketing here and that is the whole contract: the feed,
    the digest and autopilot all read these same fields, so there is one
    definition of "jobs for me" rather than three that drift.

    Stored as JSON string lists rather than enum columns for markets, because
    markets are operator-defined (they follow whatever mailboxes exist) and
    adding one must not need a migration.
    """

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Empty list means "no filter" in every case below, not "match nothing" —
    # a half-finished onboarding must degrade to the full feed, never a blank one.
    target_markets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    lanes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    job_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    remote_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Autopilot. Thresholds are fit scores (0-100) from JobMatch; an action only
    # fires at or above its threshold, so turning a switch on with the default
    # threshold is conservative by construction.
    autopilot_apply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    autopilot_apply_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=85)
    autopilot_outreach_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    autopilot_outreach_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=90)

    # A ceiling per run, so a bad scoring day can't fire off fifty applications
    # in someone's name before they notice.
    autopilot_daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
