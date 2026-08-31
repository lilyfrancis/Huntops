import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user, require_employer
from app.db.base import get_db
from app.models.enums import JobStatus, UserRole
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreate, JobOut, JobUpdate
from app.services.ghost_detection import GHOST_THRESHOLD
from app.services.salary_parsing import parse_salary

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
settings = get_settings()


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreate,
    current_user: User = Depends(require_employer),
    db: Session = Depends(get_db),
) -> Job:
    if not current_user.is_approved:
        raise HTTPException(status_code=403, detail="Your employer account is pending approval")

    parsed_salary = parse_salary(payload.salary_range)
    job = Job(
        **payload.model_dump(),
        salary_annual_min=parsed_salary["annual_min"] if parsed_salary else None,
        salary_annual_max=parsed_salary["annual_max"] if parsed_salary else None,
        salary_currency=parsed_salary["currency"] if parsed_salary else None,
        employer_id=current_user.id,
        employer_name=current_user.full_name,
        company_name=current_user.company_name,
        status=JobStatus.active if settings.AUTO_APPROVE_JOBS else JobStatus.pending,
        source="internal",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    location: str | None = None,
    job_type: str | None = None,
    featured_only: bool = False,
    hide_ghosts: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Job]:
    query = db.query(Job).filter(Job.status == JobStatus.active)

    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if featured_only:
        query = query.filter(Job.is_featured.is_(True))
    if hide_ghosts:
        # Unscanned jobs stay visible — absence of a score isn't evidence of a ghost.
        query = query.filter((Job.ghost_score.is_(None)) | (Job.ghost_score < GHOST_THRESHOLD))

    query = query.order_by(desc(Job.is_featured), desc(Job.created_at))
    return query.offset(skip).limit(limit).all()


@router.get("/employer/mine", response_model=list[JobOut])
def list_my_jobs(
    current_user: User = Depends(require_employer),
    db: Session = Depends(get_db),
) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.employer_id == current_user.id)
        .order_by(desc(Job.created_at))
        .all()
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_owned_job(job_id: uuid.UUID, current_user: User, db: Session) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != UserRole.admin and job.employer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this job")
    return job


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    job = _get_owned_job(job_id, current_user, db)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(job, field, value)

    # Editing an active listing sends it back for re-approval unless auto-approve is on.
    if updates and not settings.AUTO_APPROVE_JOBS:
        job.status = JobStatus.pending

    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    job = _get_owned_job(job_id, current_user, db)
    db.delete(job)
    db.commit()
