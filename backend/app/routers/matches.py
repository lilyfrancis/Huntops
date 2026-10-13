from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.application import Application
from app.models.user import User
from app.schemas.job import JobOut, job_out_for
from app.schemas.job_match import JobMatchOut, MatchRunOut
from app.services import matching, preferences, resume_selection, unlocking
from app.services.ai_client import AIResponseError

router = APIRouter(prefix="/api/ai", tags=["matching"])
settings = get_settings()


@router.get("/match-jobs", response_model=MatchRunOut)
@limiter.limit("20/hour")
def match_jobs(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[JobMatchOut]:
    if not resume_selection.all_for(db, current_user):
        raise HTTPException(status_code=404, detail="Please upload your résumé first")

    # Through the user's own filters, like the feed, the digest and autopilot.
    # This endpoint queried every active job instead, which meant scoring —
    # and charging for — roles the user had explicitly excluded, while a
    # market or lane they did want could be crowded out of the candidate cap
    # by jobs they would never see.
    prefs = preferences.get_or_create(db, current_user)
    # Only the jobs this user has no score for yet. Pressing Refresh twice in
    # a row used to re-score and re-charge for the identical forty jobs.
    jobs = matching.unscored_for(
        db, current_user, preferences.feed_query(db, prefs), settings.MAX_MATCH_CANDIDATES
    )
    # Each job scored against the CV it calls for, so an engineering role is
    # never rated on a sales CV — and then applied for with a third one.
    if jobs:
        try:
            for resume, group in resume_selection.group_by_resume(db, current_user, jobs):
                scored = matching.score_jobs(resume, group, current_user.home_market)
                matching.persist_matches(db, current_user, scored)
        except AIResponseError as e:
            raise HTTPException(status_code=502, detail=f"Job matching failed: {e}")
        db.commit()

    # Everything this user has, not only what was scored a moment ago. Now
    # that a job is scored once and remembered, a quiet day scores nothing —
    # and returning just this run's work would empty a page that is full.
    stored = (
        db.query(JobMatch, Job)
        .join(Job, JobMatch.job_id == Job.id)
        .filter(
            JobMatch.user_id == current_user.id,
            Job.status == JobStatus.active,
            JobMatch.fit_score >= matching.MIN_SCORE_THRESHOLD,
        )
        .order_by(desc(JobMatch.fit_score))
        .limit(limit)
        .all()
    )

    # Paid-for unlocks and applications alike: both are commitments that
    # earn the full listing. Same helper as the feed, so the two can never
    # disagree about what this user may see.
    applied_job_ids = unlocking.unlocked_ids(db, current_user, [job.id for _m, job in stored])

    return MatchRunOut(
        matches=[
            JobMatchOut(
                job=job_out_for(job, current_user, applied_job_ids),
                fit_score=match.fit_score,
                skills_score=match.skills_score,
                experience_score=match.experience_score,
                geo_score=match.geo_score,
                geo_boost_applied=match.geo_boost_applied,
                reason=match.reason,
            )
            for match, job in stored
        ],
        candidates_scored=len(jobs),
        threshold=matching.MIN_SCORE_THRESHOLD,
    )
