import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_admin
from app.db.base import get_db
from app.models.application import Application
from app.models.email_sync_run import EmailSyncRun
from app.models.enums import JobStatus, OutreachStatus, SubscriptionTier, UserRole
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.user import User
from app.schemas.job import JobOut, JobRejectRequest
from app.schemas.user import UserOut
from app.services.aggregation import ingest_all

settings = get_settings()

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(desc(User.created_at)).offset(skip).limit(limit).all()


@router.put("/users/{user_id}/approve", response_model=UserOut)
def approve_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/suspend", response_model=UserOut)
def suspend_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_suspended = True
    db.commit()
    db.refresh(user)
    return user


@router.get("/jobs/pending", response_model=list[JobOut])
def list_pending_jobs(db: Session = Depends(get_db)) -> list[Job]:
    return db.query(Job).filter(Job.status == JobStatus.pending).order_by(desc(Job.created_at)).all()


@router.put("/jobs/{job_id}/approve", response_model=JobOut)
def approve_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.active
    job.rejection_reason = None
    db.commit()
    db.refresh(job)
    return job


@router.put("/jobs/{job_id}/reject", response_model=JobOut)
def reject_job(job_id: uuid.UUID, payload: JobRejectRequest, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.rejected
    job.rejection_reason = payload.reason
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/aggregate")
def trigger_aggregation(db: Session = Depends(get_db)) -> dict:
    """Manually run the aggregation pipeline on demand (also runs daily via the scheduler)."""
    return ingest_all(db)


@router.get("/jobs/aggregation-runs")
def list_aggregation_runs(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    runs = db.query(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "status": r.status,
            "fetched_count": r.fetched_count,
            "inserted_count": r.inserted_count,
            "error": r.error,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
        }
        for r in runs
    ]


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)) -> dict:
    """Consolidated business + ops health — the equivalent of JobQuick's
    analytics endpoint, extended with the ingestion/outreach visibility
    that endpoint never had because its supply and outreach were fake."""
    total_users = db.query(User).count()
    job_seekers = db.query(User).filter(User.role == UserRole.job_seeker).count()
    employers = db.query(User).filter(User.role == UserRole.employer).count()
    pro_count = db.query(User).filter(User.subscription_tier == SubscriptionTier.pro).count()
    elite_count = db.query(User).filter(User.subscription_tier == SubscriptionTier.elite).count()

    total_jobs = db.query(Job).count()
    active_jobs = db.query(Job).filter(Job.status == JobStatus.active).count()
    featured_jobs = db.query(Job).filter(Job.is_featured.is_(True)).count()
    aggregated_jobs = db.query(Job).filter(Job.source != "internal").count()

    total_applications = db.query(Application).count()

    total_outreach = db.query(Outreach).count()
    sent_outreach = db.query(Outreach).filter(Outreach.status == OutreachStatus.sent).count()

    recent_runs = db.query(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(30).all()
    ingestion_success_rate = (
        sum(1 for r in recent_runs if r.status == "success") / len(recent_runs) if recent_runs else None
    )

    return {
        "users": {
            "total": total_users, "job_seekers": job_seekers, "employers": employers,
            "pro": pro_count, "elite": elite_count,
        },
        "jobs": {
            "total": total_jobs, "active": active_jobs, "featured": featured_jobs, "aggregated": aggregated_jobs,
        },
        "applications": {"total": total_applications},
        "outreach": {
            "total": total_outreach, "sent": sent_outreach,
            "success_rate": (sent_outreach / total_outreach) if total_outreach else None,
        },
        "ingestion_health": {
            "recent_runs_checked": len(recent_runs), "success_rate": ingestion_success_rate,
        },
        "revenue": {
            "monthly_recurring_estimate_usd": round(pro_count * settings.PRO_PRICE_USD + elite_count * settings.ELITE_PRICE_USD, 2),
            "pro_subs": pro_count, "elite_subs": elite_count,
        },
    }


@router.get("/email-sync-runs")
def list_email_sync_runs(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Aggregate email-bridge health across all users — never exposes which
    user's inbox a run belongs to beyond the id, since this is admin ops
    visibility, not a way to browse individual mailboxes."""
    runs = db.query(EmailSyncRun).order_by(desc(EmailSyncRun.started_at)).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "status": r.status,
            "fetched_count": r.fetched_count,
            "extracted_count": r.extracted_count,
            "inserted_count": r.inserted_count,
            "error": r.error,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
        }
        for r in runs
    ]
