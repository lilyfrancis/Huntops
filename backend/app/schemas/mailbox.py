import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import JobLane


def _validate_lanes(v: list[str]) -> list[str]:
    for lane in v:
        try:
            JobLane(lane)
        except ValueError:
            raise ValueError(f"Unknown lane: {lane}")
    return v


class MailboxUpsert(BaseModel):
    """Add a mailbox, or update the one already on that address."""

    email_address: EmailStr
    market: str
    imap_host: str
    imap_port: int = Field(default=993, ge=1, le=65535)
    # Defaults to the email address, which is what most hosts expect.
    imap_username: str | None = None
    # Optional on update: editing the market must not require retyping (or
    # worse, blanking) the password.
    imap_password: str | None = None
    imap_use_ssl: bool = True
    imap_folder: str = "INBOX"
    label: str | None = None
    lanes: list[str] = []

    @field_validator("market", "imap_host")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field is required")
        return v

    @field_validator("lanes")
    @classmethod
    def lanes_are_known(cls, v: list[str]) -> list[str]:
        return _validate_lanes(v)


class MailboxUpdate(BaseModel):
    label: str | None = None
    market: str | None = None
    lanes: list[str] | None = None
    is_active: bool | None = None

    @field_validator("lanes")
    @classmethod
    def lanes_are_known(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _validate_lanes(v)


class MailboxOut(BaseModel):
    """Note the absence of the password. There is no read path for it — a
    secret that can be fetched back out of the API is a secret one XSS away
    from being someone else's."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email_address: EmailStr
    label: str
    market: str
    lanes: list[str]
    imap_host: str
    imap_port: int
    imap_username: str
    imap_use_ssl: bool
    imap_folder: str
    is_active: bool
    created_at: datetime
    last_synced_at: datetime | None
    last_error: str | None


class MailboxSyncResult(BaseModel):
    mailbox: str
    market: str
    status: str
    fetched: int
    extracted: int
    inserted: int
    # Sender domain -> how many messages from it were passed over. Shown so an
    # operator can see why a mailbox produced nothing, instead of reading
    # "success, 0 inserted" and guessing.
    skipped_senders: dict[str, int] = {}
    error: str | None = None


class MailboxTestResult(BaseModel):
    ok: bool
    detail: str
