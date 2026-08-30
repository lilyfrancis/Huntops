import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import SubscriptionTier, UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Free-text home market for geo-eligibility boosting (e.g. "Nigeria",
    # "Philippines"). Null means no boost is applied — scoring degrades
    # gracefully to skills/experience fit only.
    home_market: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Optional free-text steer for outreach drafting, e.g. "pivoting from
    # sales into RevOps" — never fabricated content, just tone/emphasis.
    positioning_statement: Mapped[str | None] = mapped_column(String(500), nullable=True)

    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier"), nullable=False, default=SubscriptionTier.free
    )
    ai_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
