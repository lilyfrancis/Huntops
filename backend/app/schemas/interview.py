import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InterviewStatus


class InterviewStartRequest(BaseModel):
    job_id: uuid.UUID | None = None
    role_title: str | None = Field(default=None, max_length=255)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


class InterviewTurnOut(BaseModel):
    # `model_answer` is the ideal answer, not a Pydantic attribute — opt out
    # of the protected `model_` namespace.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    position: int
    question: str
    answer: str | None
    score: float | None
    strengths: list[str]
    improvements: list[str]
    model_answer: str | None
    answered_at: datetime | None


class InterviewSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID | None
    role_title: str
    company_name: str | None
    status: InterviewStatus
    average_score: float | None
    summary: str | None
    next_steps: list[str]
    created_at: datetime
    completed_at: datetime | None
    turns: list[InterviewTurnOut]


class InterviewSessionSummary(BaseModel):
    """List view — omits the transcript so the index stays cheap."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_title: str
    company_name: str | None
    status: InterviewStatus
    average_score: float | None
    created_at: datetime
    completed_at: datetime | None
