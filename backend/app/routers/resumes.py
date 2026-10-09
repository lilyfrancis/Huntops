from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import require_job_seeker
from app.db.base import get_db
import uuid as uuid_mod

from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeOut, ResumeUpdate
from app.services import resume_selection
from app.services import resumes as resumes_service
from app.services.ai_client import AIResponseError
from app.services.resume_files import UnsupportedFileError, extract_text

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
settings = get_settings()


@router.post("/upload", response_model=ResumeOut, status_code=201)
@limiter.limit("10/hour")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    label: str | None = Form(default=None),
    replaces: str | None = Form(default=None),
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Resume:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in settings.allowed_resume_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File must be one of: {', '.join(settings.allowed_resume_extensions_list)}",
        )

    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB")

    try:
        resume_text = extract_text(file_bytes, file.filename or "")
    except UnsupportedFileError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resume_text or len(resume_text.strip()) < 100:
        raise HTTPException(
            status_code=400,
            detail="Résumé appears to be empty or too short. Please upload a complete résumé.",
        )

    try:
        parsed = resumes_service.parse_resume(resume_text)
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Résumé parsing failed: {e}")

    # Uploading adds a CV. It used to replace the only one, which is the
    # wrong default now that a person can keep one per career track —
    # re-uploading the sales CV would have silently destroyed the
    # engineering one. Replacing is still possible, by naming the CV.
    resume = None
    if replaces:
        try:
            target_id = uuid_mod.UUID(replaces)
        except ValueError:
            raise HTTPException(status_code=422, detail="Not a valid résumé id")
        resume = (
            db.query(Resume)
            .filter(Resume.id == target_id, Resume.user_id == current_user.id)
            .first()
        )
        if resume is None:
            raise HTTPException(status_code=404, detail="No such résumé on this account")

    if resume is None:
        resume = Resume(
            user_id=current_user.id,
            raw_text=resume_text,
            label=(label or Path(file.filename or "").stem or "My CV")[:80],
        )
        db.add(resume)
    elif label:
        resume.label = label[:80]

    resume.file_name = file.filename
    resume.raw_text = resume_text
    resume.parsed_skills = parsed.skills
    resume.experience_years = parsed.experience_years
    resume.education = parsed.education
    resume.summary = parsed.summary
    resume.achievements = parsed.achievements

    db.flush()
    # The first CV uploaded is the fallback; later ones leave it alone.
    resume_selection.ensure_one_primary(db, current_user)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[Resume]:
    """Every CV on the account, primary first."""
    return resume_selection.all_for(db, current_user)


@router.patch("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: uuid_mod.UUID,
    payload: ResumeUpdate,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Resume:
    """Rename a CV, change which job families it covers, or make it the fallback."""
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="No such résumé on this account")

    if payload.label is not None:
        resume.label = payload.label[:80]
    if payload.lanes is not None:
        resume.lanes = [lane.value for lane in payload.lanes]

    # Promoting is a request; demoting the only CV is not, because it would
    # leave the account with no fallback at all.
    if payload.is_primary:
        resume_selection.ensure_one_primary(db, current_user, prefer=resume)
    else:
        resume_selection.ensure_one_primary(db, current_user)

    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(
    resume_id: uuid_mod.UUID,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> None:
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="No such résumé on this account")

    db.delete(resume)
    db.flush()
    # Deleting the fallback promotes the next one rather than leaving the
    # account with none, which would strand scoring and tailoring alike.
    resume_selection.ensure_one_primary(db, current_user)
    db.commit()


@router.get("/me", response_model=ResumeOut)
def get_my_resume(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Resume:
    resume = resume_selection.primary(db, current_user)
    if not resume:
        raise HTTPException(status_code=404, detail="No résumé uploaded yet")
    return resume
