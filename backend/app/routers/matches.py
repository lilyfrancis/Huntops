from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.job import Job
from app.models.application import Application
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job import JobOut, job_out_for
from app.schemas.job_match import JobMatchOut, MatchRunOut
from app.services import matching, preferences
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
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Please upload your résumé first")

    # Through the user's own filters, like the feed, the digest and autopilot.
    # This endpoint queried every active job instead, which meant scoring —
    # and charging for — roles the user had explicitly excluded, while a
    # market or lane they did want could be crowded out of the candidate cap
    # by jobs they would never see.
    prefs = preferences.get_or_create(db, current_user)
    jobs = (
        preferences.feed_query(db, prefs)
        .order_by(desc(Job.created_at))
        .limit(settings.MAX_MATCH_CANDIDATES)
        .all()
    )
    if not jobs:
        return MatchRunOut(matches=[], candidates_scored=0, threshold=matching.MIN_SCORE_THRESHOLD)

    try:
        scored = matching.score_jobs(resume, jobs, current_user.home_market)
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Job matching failed: {e}")

    persisted = matching.persist_matches(db, current_user, scored)
    db.commit()

    # Applied-to jobs are unlocked: the user committed, so it is theirs to see.
    applied_job_ids = {
        job_id
        for (job_id,) in db.query(Application.job_id).filter(
            Application.candidate_id == current_user.id
        )
    }

    results = [
        JobMatchOut(
            job=job_out_for(job, current_user, applied_job_ids),
            fit_score=match.fit_score,
            skills_score=match.skills_score,
            experience_score=match.experience_score,
            geo_score=match.geo_score,
            geo_boost_applied=match.geo_boost_applied,
            reason=match.reason,
        )
        for match, job in persisted
    ]
    results.sort(key=lambda r: r.fit_score, reverse=True)
    return MatchRunOut(
        matches=results[:limit],
        candidates_scored=len(jobs),
        threshold=matching.MIN_SCORE_THRESHOLD,
    )
