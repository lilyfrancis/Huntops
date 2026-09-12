from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import JobLane, JobType


def _known(values: list[str], enum_cls, kind: str) -> list[str]:
    for value in values:
        try:
            enum_cls(value)
        except ValueError:
            raise ValueError(f"Unknown {kind}: {value}")
    return values


class PreferenceUpdate(BaseModel):
    """Every field optional: onboarding sets markets and lanes, the settings
    page later flips an autopilot switch, and neither should have to resend
    the other's values and risk clobbering them."""

    target_markets: list[str] | None = None
    locations: list[str] | None = None
    lanes: list[str] | None = None
    job_types: list[str] | None = None
    remote_only: bool | None = None

    autopilot_apply_enabled: bool | None = None
    autopilot_apply_threshold: int | None = Field(default=None, ge=50, le=100)
    autopilot_outreach_enabled: bool | None = None
    autopilot_outreach_threshold: int | None = Field(default=None, ge=50, le=100)
    autopilot_daily_cap: int | None = Field(default=None, ge=1, le=25)

    @field_validator("locations")
    @classmethod
    def locations_are_sane(cls, v: list[str] | None) -> list[str] | None:
        """Trimmed, deduplicated, and bounded. Each entry becomes a LIKE
        clause, so an unbounded list is an unbounded query."""
        if v is None:
            return None
        cleaned: list[str] = []
        for name in v:
            name = name.strip()
            if not name:
                continue
            if len(name) > 100:
                raise ValueError("Location names must be 100 characters or fewer")
            if name.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(name)
        if len(cleaned) > 20:
            raise ValueError("At most 20 locations")
        return cleaned

    @field_validator("lanes")
    @classmethod
    def lanes_are_known(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _known(v, JobLane, "lane")

    @field_validator("job_types")
    @classmethod
    def job_types_are_known(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _known(v, JobType, "job type")


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_markets: list[str]
    locations: list[str]
    lanes: list[str]
    job_types: list[str]
    remote_only: bool

    autopilot_apply_enabled: bool
    autopilot_apply_threshold: int
    autopilot_outreach_enabled: bool
    autopilot_outreach_threshold: int
    autopilot_daily_cap: int

    onboarded_at: datetime | None


class PreferenceOptions(BaseModel):
    """What the onboarding screen is allowed to offer.

    `markets` comes from the mailboxes that actually exist, so the form can
    never promise a country with no supply behind it.
    """

    markets: list[str]
    lanes: list[str]
    job_types: list[str]
