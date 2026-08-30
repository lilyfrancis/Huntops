import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ApplicationStatus


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    cover_letter: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    cover_letter: str | None
    status: ApplicationStatus
    ai_match_score: float | None
    created_at: datetime


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
