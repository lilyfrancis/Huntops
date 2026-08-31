import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExperienceLevel, JobLane


class NegotiationRequest(BaseModel):
    role_title: str = Field(min_length=2, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    location: str = Field(min_length=2, max_length=255)
    currency: str = Field(min_length=3, max_length=3)
    base_salary: float = Field(gt=0)
    equity: str | None = Field(default=None, max_length=2000)
    other_terms: str | None = Field(default=None, max_length=2000)
    has_competing_offer: bool = False
    lane: JobLane | None = None
    experience_level: ExperienceLevel | None = None


class BenchmarkOut(BaseModel):
    currency: str
    sample_size: int
    lookback_days: int
    p25: int
    median: int
    p75: int
    lane: str | None
    experience_level: str | None
    cohort: str


class LeverOut(BaseModel):
    lever: str
    rationale: str


class NegotiationReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_title: str
    company_name: str | None
    location: str
    currency: str
    base_salary: float
    equity: str | None
    other_terms: str | None
    has_competing_offer: bool

    verdict: str
    confidence: str
    levers: list[LeverOut]
    counter_script: str
    if_they_say_no: str
    watch_outs: list[str]

    # Null means no benchmark was available and the advice is tactics-only.
    benchmark: BenchmarkOut | None
    created_at: datetime


class CurrencyCoverage(BaseModel):
    currency: str
    listings: int
