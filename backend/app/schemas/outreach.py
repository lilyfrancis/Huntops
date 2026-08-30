import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import OutreachStatus


class OutreachOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    email_subject: str | None
    email_body: str | None
    linkedin_msg: str | None
    cv_bullets: list[str]
    status: OutreachStatus
    sent_at: datetime | None
    created_at: datetime


class OutreachRequest(BaseModel):
    job_id: uuid.UUID
