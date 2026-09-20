import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    # Shown so the page can say who it will go to, and ask for an address
    # when Apollo found none. The draft is useless without somewhere to send
    # it, and that was invisible before.
    recipient_email: str | None = None
    sent_to_email: str | None = None


class OutreachRequest(BaseModel):
    job_id: uuid.UUID


class OutreachSendRequest(BaseModel):
    """Everything optional. Sending an untouched draft to the contact Apollo
    found is the common case and should need no fields at all."""

    to_email: EmailStr | None = None
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=20000)
