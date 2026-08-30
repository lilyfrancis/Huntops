import uuid

from pydantic import BaseModel

from app.schemas.job import JobOut


class JobMatchOut(BaseModel):
    job: JobOut
    fit_score: float
    skills_score: float
    experience_score: float
    geo_score: float
    geo_boost_applied: bool
    reason: str | None
