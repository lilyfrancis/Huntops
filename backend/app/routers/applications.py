import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import get_current_user, require_job_seeker
from app.db.base import get_db
from app.models.application import Application
from app.models.application_draft import ApplicationDraft
from app.models.job import Job
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate,
    ConciergeAllowanceOut,
    ApplicationDraftEdit,
    ApplicationDraftOut,
    ApplicationOut,
    ApplicationStatusUpdate,
)
from app.services import concierge, tailoring
from app.services.ai_client import AIResponseError

router = APIRouter(prefix="/api/applications", tags=["applications"])
settings = get_settings()


@router.post("", response_model=ApplicationOut, status_code=201)
def apply_to_job(
    payload: ApplicationCreate,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Application:
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # An external listing cannot be submitted from here — it lives behind
    # someone else's form. Rather than handing the work back to the user,
    # it goes into the queue for a person to file.
    if job.source != "internal":
        try:
            return concierge.request(db, current_user, job)
        except concierge.AllowanceExhausted as e:
            raise HTTPException(status_code=403, detail=str(e))
        except concierge.InsufficientCredits as e:
            raise HTTPException(status_code=402, detail=str(e))
        except concierge.ConciergeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    cover_letter = payload.cover_letter
    bullets = payload.tailored_bullets
    if payload.use_draft and not cover_letter:
        # A letter the user already wrote and paid for should not be dropped
        # because the button posted only a job id.
        draft = (
            db.query(ApplicationDraft)
            .filter(
                ApplicationDraft.user_id == current_user.id,
                ApplicationDraft.job_id == payload.job_id,
            )
            .first()
        )
        if draft is not None:
            cover_letter = draft.cover_letter or None
            bullets = bullets or draft.bullets

    application = Application(
        job_id=payload.job_id,
        candidate_id=current_user.id,
        candidate_name=current_user.full_name,
        candidate_email=current_user.email,
        cover_letter=cover_letter,
        tailored_bullets=bullets,
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


# ---------- tailoring: what actually goes with the application ----------

@router.post("/draft/{job_id}", response_model=ApplicationDraftOut)
@limiter.limit("30/hour")
def create_or_get_draft(
    request: Request,
    job_id: uuid.UUID,
    regenerate: bool = False,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> ApplicationDraft:
    """The tailored letter and bullets for this job, generating them once.

    A POST rather than a GET because the first call spends credits and
    creates a row. Subsequent calls return the cached draft and cost
    nothing, so the client can open it freely.
    """
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = (
        db.query(ApplicationDraft)
        .filter(ApplicationDraft.user_id == current_user.id, ApplicationDraft.job_id == job_id)
        .first()
    )
    if regenerate and existing is not None and existing.edited:
        # Their words, not ours. Overwriting them on an ambiguous button
        # press is the one mistake here that cannot be undone.
        raise HTTPException(
            status_code=409,
            detail="This draft has your edits in it. Clear them first if you want a fresh one.",
        )

    if existing is None or regenerate:
        if current_user.ai_credits < settings.TAILOR_CREDIT_COST:
            raise HTTPException(
                status_code=402,
                detail=f"Tailoring costs {settings.TAILOR_CREDIT_COST} credits and you have {current_user.ai_credits}.",
            )

    try:
        return tailoring.generate(db, current_user, job, force=regenerate)
    except tailoring.NoResumeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Could not write the draft: {e}")


@router.put("/draft/{job_id}", response_model=ApplicationDraftOut)
def edit_draft(
    job_id: uuid.UUID,
    payload: ApplicationDraftEdit,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> ApplicationDraft:
    """Editing is free — it is the user's own writing."""
    draft = (
        db.query(ApplicationDraft)
        .filter(ApplicationDraft.user_id == current_user.id, ApplicationDraft.job_id == job_id)
        .first()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="No draft for this job yet")
    return tailoring.save_edits(
        db, draft, cover_letter=payload.cover_letter, bullets=payload.bullets
    )


@router.get("/concierge/allowance", response_model=ConciergeAllowanceOut)
def concierge_allowance(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> ConciergeAllowanceOut:
    """Said before the click, not after. A button that takes credits and
    then refuses is worse than one that says what it will cost."""
    return ConciergeAllowanceOut(
        remaining=concierge.allowance_remaining(db, current_user),
        allowance=settings.CONCIERGE_FREE_ALLOWANCE,
        credit_cost=settings.CONCIERGE_CREDIT_COST,
        unlock_credit_cost=settings.UNLOCK_CREDIT_COST,
        credits=current_user.ai_credits,
    )
