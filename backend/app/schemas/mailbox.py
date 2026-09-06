import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import JobLane


def _validate_lanes(v: list[str]) -> list[str]:
    for lane in v:
        try:
            JobLane(lane)
        except ValueError:
            raise ValueError(f"Unknown lane: {lane}")
    return v


class MailboxConnectRequest(BaseModel):
    """Market and labelling are chosen *before* the consent screen.

    Google's redirect gives us back only a code and our own signed state, so
    anything the admin picked has to survive the round trip inside that state
    rather than being asked for afterwards.
    """

    market: str
    label: str | None = None
    lanes: list[str] = []

    @field_validator("market")
    @classmethod
    def market_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Market is required — it is what users filter their feed by")
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
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email_address: EmailStr
    label: str
    market: str
    lanes: list[str]
    is_active: bool
    connected_at: datetime
    last_synced_at: datetime | None
    last_error: str | None


class MailboxSyncResult(BaseModel):
    mailbox: str
    market: str
    status: str
    fetched: int
    extracted: int
    inserted: int
    error: str | None = None
