import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str | None
    parsed_skills: list[str]
    experience_years: int | None
    education: str | None
    summary: str | None
    achievements: list[str]
    created_at: datetime
    updated_at: datetime
