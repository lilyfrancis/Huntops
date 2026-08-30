from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job import JobOut
from app.schemas.job_match import JobMatchOut
from app.services import matching
from app.services.ai_client import AIResponseError

router = APIRouter(prefix="/api/ai", tags=["matching"])
settings = get_settings()

MIN_SCORE_THRESHOLD = 50


@router.get("/match-jobs", response_model=list[JobMatchOut])
def match_jobs(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[JobMatchOut]:
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Please upload your résumé first")

    jobs = (
        db.query(Job)
        .filter(Job.status == JobStatus.active)
        .order_by(desc(Job.created_at))
        .limit(settings.MAX_MATCH_CANDIDATES)
        .all()
    )
    if not jobs:
        return []

    try:
        scored = matching.score_jobs(resume, jobs, current_user.home_market)
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Job matching failed: {e}")

    results: list[JobMatchOut] = []
    for job, score, geo_boost_applied in scored:
        if score.overall_score < MIN_SCORE_THRESHOLD:
            continue

        match = db.query(JobMatch).filter(JobMatch.user_id == current_user.id, JobMatch.job_id == job.id).first()
        if match is None:
            match = JobMatch(user_id=current_user.id, job_id=job.id, fit_score=0)
            db.add(match)

        match.fit_score = score.overall_score
        match.skills_score = score.skills_score
        match.experience_score = score.experience_score
        match.geo_score = score.location_score
        match.geo_boost_applied = geo_boost_applied
        match.reason = score.reason

        results.append(
            JobMatchOut(
                job=JobOut.model_validate(job),
                fit_score=match.fit_score,
                skills_score=match.skills_score,
                experience_score=match.experience_score,
                geo_score=match.geo_score,
                geo_boost_applied=match.geo_boost_applied,
                reason=match.reason,
            )
        )

        if len(results) >= limit:
            break

    db.commit()
    return results
