import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AutopilotActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    action: str
    status: str
    detail: str | None
    fit_score: float | None
    created_at: datetime


class AutopilotRunSummary(BaseModel):
    applied: int
    outreach: int
    skipped: int
    failed: int
    capped: bool
