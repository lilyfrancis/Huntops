import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType
from app.services.ghost_detection import classify


class JobCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=20)
    requirements: list[str] = Field(default_factory=list)
    location: str
    salary_range: str | None = None
    job_type: JobType
    experience_level: ExperienceLevel


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    requirements: list[str] | None = None
    location: str | None = None
    salary_range: str | None = None
    job_type: JobType | None = None
    experience_level: ExperienceLevel | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employer_id: uuid.UUID | None
    employer_name: str | None
    company_name: str | None
    title: str
    description: str
    requirements: list[str]
    location: str
    salary_range: str | None
    job_type: JobType
    experience_level: ExperienceLevel
    status: JobStatus
    rejection_reason: str | None
    is_featured: bool
    application_count: int
    source: str
    source_url: str | None
    lane: JobLane | None
    is_remote: bool
    restricted_to: str | None
    ghost_score: int | None
    ghost_flags: list[str]
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ghost_band(self) -> str:
        return classify(self.ghost_score)


class JobRejectRequest(BaseModel):
    reason: str = Field(min_length=3)
