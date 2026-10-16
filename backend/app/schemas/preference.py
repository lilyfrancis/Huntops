from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import JobLane, JobType
from app.services import geo
from app.services.preferences import RECENCY_CHOICES, WORK_MODES


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
    digest_channel: Literal["email", "whatsapp", "both", "none"] | None = None

    eligibility: list[str] | None = None
    work_modes: list[str] | None = None
    title_keywords: list[str] | None = None
    # No upper bound on the floor: a number too high simply returns nothing,
    # and it is the user's own ceiling to set. Negative is refused because it
    # cannot mean anything.
    salary_min_annual: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    posted_within_days: int | None = None

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

    @field_validator("eligibility")
    @classmethod
    def eligibility_is_recognised(cls, v: list[str] | None) -> list[str] | None:
        """Canonicalised on the way in, so "Lagos" and "nigeria" both become
        "Nigeria" and the stored value is the one the query understands.

        Refused rather than silently dropped when unrecognised: a country we
        cannot resolve would widen the feed back to everything, which looks
        like the filter being ignored rather than rejected.
        """
        if v is None:
            return None
        cleaned: list[str] = []
        for value in v:
            place = geo.canonical(value)
            if place is None:
                raise ValueError(f"Unknown place: {value}")
            if place not in cleaned:
                cleaned.append(place)
        if len(cleaned) > 10:
            raise ValueError("At most 10 places")
        return cleaned

    @field_validator("work_modes")
    @classmethod
    def work_modes_are_known(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        for value in v:
            if value not in WORK_MODES:
                raise ValueError(f"Unknown work mode: {value}")
        return list(dict.fromkeys(v))

    @field_validator("posted_within_days")
    @classmethod
    def recency_is_offered(cls, v: int | None) -> int | None:
        if v is not None and v not in RECENCY_CHOICES:
            raise ValueError(f"Choose one of {', '.join(str(c) for c in RECENCY_CHOICES)} days")
        return v

    @field_validator("salary_currency")
    @classmethod
    def currency_is_a_code(cls, v: str | None) -> str | None:
        """Upper-cased, because it is compared to `Job.salary_currency`
        character for character and "ngn" would quietly match nothing."""
        if v is None:
            return None
        code = v.strip().upper()
        if not code.isalpha():
            raise ValueError("Currency must be a 3-letter code, e.g. NGN")
        return code

    @field_validator("title_keywords")
    @classmethod
    def keywords_are_sane(cls, v: list[str] | None) -> list[str] | None:
        """Same shape as locations: each becomes a LIKE clause, so the list
        has to be bounded and each entry long enough to mean something. A
        single letter would match every job in the pool."""
        if v is None:
            return None
        cleaned: list[str] = []
        for word in v:
            word = word.strip()
            if len(word) < 2:
                continue
            if len(word) > 60:
                raise ValueError("Role titles must be 60 characters or fewer")
            if word.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(word)
        if len(cleaned) > 10:
            raise ValueError("At most 10 role titles")
        return cleaned


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_markets: list[str]
    locations: list[str]
    lanes: list[str]
    job_types: list[str]
    remote_only: bool
    digest_channel: str

    eligibility: list[str]
    work_modes: list[str]
    title_keywords: list[str]
    salary_min_annual: float | None
    salary_currency: str | None
    posted_within_days: int | None

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
    # Eligibility is a fact about the person, not about our stock, so this is
    # a curated list rather than a query against supply — unlike `markets`,
    # which must never offer a country with no mailbox behind it.
    eligibility: list[str]
    work_modes: list[str]
    recency_choices: list[int]
