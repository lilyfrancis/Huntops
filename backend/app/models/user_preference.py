import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
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

    # Cities or regions within those markets, free text — "Toronto", "Greater
    # Manchester", "Abu Dhabi". Free text rather than a fixed list because the
    # location on a listing is itself free text from whatever board sent it,
    # and no enum survives contact with "Downtown Toronto, ON (Hybrid)".
    locations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    lanes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    job_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    remote_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Countries whose residents this user counts as — "where can I apply
    # from", not "where did the listing come from". `target_markets` above is
    # the second question: it filters on which alert mailbox a job arrived
    # through, which is a fact about our supply chain and says nothing about
    # whether this person is allowed to take the job.
    #
    # Picking Nigeria here means roles open to applicants in Nigeria: onsite
    # roles in Nigeria, remote roles with no stated restriction, and remote
    # roles advertised for a region Nigeria sits inside. It does not mean
    # roles that happen to have a Nigerian office and hire only Americans.
    eligibility: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Subset of {"remote", "hybrid", "onsite"}. Separate from `remote_only`,
    # which this supersedes but cannot replace: the boolean is still what the
    # feed's per-visit toggle writes, and thousands of rows already have it set.
    work_modes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # A salary floor, annualised, with the currency it was named in. Both or
    # neither: "80000" is meaningless without knowing whether that is dollars
    # or naira, and comparing across the two without an FX rate would be a
    # worse answer than no filter at all.
    salary_min_annual: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # "posted in the last N days". Null means no limit — the pool is capped at
    # a few hundred a day, so most people want the lot.
    posted_within_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # "alerts" | "boards". Which supply pipeline to draw from.
    #
    # The two are not interchangeable. The global boards are remote-first and
    # mostly hire out of the US and Europe; the alert mailboxes carry Indeed,
    # LinkedIn, Jobberman and MyJobMag mail for one country. On a pool of
    # 9,204 jobs where 7 came from email, a Nigerian user's own market is
    # statistically invisible however well the other filters work, and no
    # amount of eligibility filtering surfaces supply that is outnumbered
    # 1,300 to one.
    #
    # Empty means both, like every other list here.
    sources: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # entry | mid | senior | lead | executive, inferred from each listing's
    # title at ingest. Its own filter rather than something to read off the
    # title keywords, because "Engineer" and "Senior Engineer" are the same
    # role at two levels and somebody who wants one does not want the other.
    experience_levels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # The exact role, in the user's own words: "backend engineer", "product
    # designer". Lanes are deliberately broad — `engineering` covers QA and
    # SRE and mobile — and somebody who wants one specific title had no way to
    # say so, which is why a feed of "senior backend manager" looked broken.
    title_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

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

    # "email" | "whatsapp" | "both" | "none". Default email, because it is the
    # one channel every user has by definition — WhatsApp needs a number they
    # may never give us.
    digest_channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")

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
