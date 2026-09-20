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


class MatchRunOut(BaseModel):
    """The result of a scoring run, not just its survivors.

    An empty list has three quite different causes — no jobs matched the
    user's filters, jobs were scored and none cleared the threshold, or the
    run never happened — and the page showed one sentence for all of them.
    The counts are what let it say which.
    """

    matches: list[JobMatchOut]
    # Jobs that passed the user's own filters and were sent for scoring.
    candidates_scored: int
    # The bar they had to clear, so the page can name the number.
    threshold: float
