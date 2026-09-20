import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApplicationStatus


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
