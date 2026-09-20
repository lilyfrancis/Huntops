import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApplicationStatus, ConciergeStatus


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    cover_letter: str | None = None
    tailored_bullets: list[str] = Field(default_factory=list)
    # Take the saved draft for this job when the client sends no text of its
    # own. Applying should not silently drop a letter the user has already
    # written and paid for just because a button posted the bare job id.
    use_draft: bool = True


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    candidate_email: str
    cover_letter: str | None
    tailored_bullets: list[str]
    status: ApplicationStatus
    is_concierge: bool
    concierge_status: ConciergeStatus | None
    concierge_note: str | None
    submitted_at: datetime | None
    ai_match_score: float | None
    created_at: datetime


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    cover_letter: str
    bullets: list[str]
    edited: bool
    created_at: datetime
    updated_at: datetime


class ApplicationDraftEdit(BaseModel):
    cover_letter: str = Field(max_length=20000)
    bullets: list[str] = Field(default_factory=list, max_length=12)


class ConciergeAllowanceOut(BaseModel):
    """What this user may still ask for, so the UI can say so before they
    click rather than after."""

    remaining: int | None          # None = unlimited (Elite)
    allowance: int
    credit_cost: int
    # What a look costs, as opposed to an application. Sent from here so the
    # UI never hardcodes a price — a stale number in the client is a promise
    # broken at the moment somebody clicks.
    unlock_credit_cost: int
    credits: int


class ConciergeQueueItem(BaseModel):
    """One job waiting to be filed, with everything the admin needs in front
    of them — chasing the CV and the letter across three pages is how a
    queue stops getting worked."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    concierge_status: ConciergeStatus | None
    concierge_note: str | None
    submitted_at: datetime | None

    candidate_id: uuid.UUID
    candidate_name: str
    candidate_email: str
    # The address to apply under. Null until an admin has set one up.
    concierge_email: str | None
    suggested_concierge_email: str

    job_id: uuid.UUID
    job_title: str
    company_name: str | None
    job_location: str
    source: str
    source_url: str | None

    cover_letter: str | None
    tailored_bullets: list[str]


class ConciergeUpdate(BaseModel):
    concierge_status: ConciergeStatus
    note: str | None = Field(default=None, max_length=2000)
    # Recorded here because setting it is part of filing the first one.
    concierge_email: str | None = None


class ApplicationStatusAdminUpdate(BaseModel):
    """Employer-side progress, which only the admin hears about for a
    concierge application — the replies go to the address we applied under."""

    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=2000)
