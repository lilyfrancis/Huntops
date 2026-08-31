from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.user import User
from app.services import digest as digest_service

router = APIRouter(prefix="/api/digest", tags=["digest"])


@router.get("/preview")
def preview_digest(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    """Renders the digest from whatever's already scored — call
    GET /api/ai/match-jobs first if this looks empty. The scheduled daily
    job scores fresh matches before sending, so this stays cheap (no AI call)."""
    matches = digest_service.get_top_matches(db, current_user)
    subject, body = digest_service.format_digest_email(matches)
    return {
        "subject": subject,
        "body": body,
        "entries": [
            {
                "job_id": str(job.id),
                "title": job.title,
                "company_name": job.company_name,
                "location": job.location,
                "fit_score": match.fit_score,
                "geo_boost_applied": match.geo_boost_applied,
                "source_url": job.source_url,
            }
            for match, job in matches
        ],
    }
