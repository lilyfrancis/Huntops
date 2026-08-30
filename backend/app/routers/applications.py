import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_job_seeker
from app.db.base import get_db
from app.models.application import Application
from app.models.job import Job
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationOut, ApplicationStatusUpdate

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut, status_code=201)
def apply_to_job(
    payload: ApplicationCreate,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Application:
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    application = Application(
        job_id=payload.job_id,
        candidate_id=current_user.id,
        cover_letter=payload.cover_letter,
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="You already applied to this job")

    job.application_count += 1
    db.commit()
    db.refresh(application)
    return application


@router.get("/mine", response_model=list[ApplicationOut])
def list_my_applications(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[Application]:
    return (
        db.query(Application)
        .filter(Application.candidate_id == current_user.id)
        .order_by(desc(Application.created_at))
        .all()
    )


@router.get("/job/{job_id}", response_model=list[ApplicationOut])
def list_applications_for_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Application]:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.employer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(desc(Application.created_at))
        .all()
    )


@router.put("/{application_id}/status", response_model=ApplicationOut)
def update_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Application:
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.get(Job, application.job_id)
    if not job or job.employer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    application.status = payload.status
    db.commit()
    db.refresh(application)
    return application
