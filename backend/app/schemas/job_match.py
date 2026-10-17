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
    # Every stored match above the bar, not just this page of them. Without
    # it the page cannot say "20 of 143", and a list that is identical every
    # visit reads as nothing having happened rather than as the top of a
    # stable ranking.
    total: int = 0
    # Jobs that match this user's filters and have never been scored. The
    # number behind "why is it only showing one" — a page reading "1 of 1"
    # while three hundred eligible jobs wait is telling the truth about the
    # wrong thing.
    unscored_remaining: int = 0
    # Scored, and did not clear the bar. Distinguishes "we have not looked at
    # these yet" from "we looked and they were not for you", which have
    # opposite fixes: press Refresh, or widen the filters.
    below_threshold: int = 0
