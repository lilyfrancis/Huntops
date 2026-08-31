from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeOut
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

    resume = db.query(Resume).filter(Resume.user_id == current_user.id).first()
    if resume is None:
        resume = Resume(user_id=current_user.id, raw_text=resume_text)
        db.add(resume)

    resume.file_name = file.filename
    resume.raw_text = resume_text
    resume.parsed_skills = parsed.skills
    resume.experience_years = parsed.experience_years
    resume.education = parsed.education
    resume.summary = parsed.summary
    resume.achievements = parsed.achievements

    db.commit()
    db.refresh(resume)
    return resume


@router.get("/me", response_model=ResumeOut)
def get_my_resume(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Resume:
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="No résumé uploaded yet")
    return resume
