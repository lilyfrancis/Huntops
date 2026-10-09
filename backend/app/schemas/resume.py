import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import JobLane


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    lanes: list[str]
    is_primary: bool
    file_name: str | None
    parsed_skills: list[str]
    experience_years: int | None
    education: str | None
    summary: str | None
    achievements: list[str]
    created_at: datetime
    updated_at: datetime


class ResumeUpdate(BaseModel):
    """What the owner may change about a CV after it is uploaded.

    The parsed fields are not here on purpose: they are derived from the
    file, and letting them be edited would make the CV and its parse
    disagree with no way to tell which is right.
    """

    label: str | None = Field(default=None, min_length=1, max_length=80)
    lanes: list[JobLane] | None = None
    is_primary: bool | None = None
