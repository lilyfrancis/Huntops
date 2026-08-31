import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class NegotiationReview(Base):
    """One coached offer, kept so the candidate can re-read the script mid-negotiation.

    The benchmark used is stored alongside the advice rather than recomputed on
    read: the corpus moves as new listings land, and advice that silently
    re-anchors to different numbers than the ones it was written against would
    be worse than useless during a live negotiation.
    """

    __tablename__ = "negotiation_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    base_salary: Mapped[float] = mapped_column(Float, nullable=False)
    equity: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_competing_offer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    levers: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    counter_script: Mapped[str] = mapped_column(Text, nullable=False)
    if_they_say_no: Mapped[str] = mapped_column(Text, nullable=False)
    watch_outs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Null means we had no benchmark and the advice is tactics-only. The UI must
    # say so rather than implying a market rate we never had.
    benchmark: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
