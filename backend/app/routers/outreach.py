import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.user import User
from app.schemas.outreach import OutreachOut, OutreachRequest
from app.services import outreach as outreach_service
from app.services.ai_client import AIResponseError

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.post("", response_model=OutreachOut, status_code=201)
def create_outreach(
    payload: OutreachRequest,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Outreach:
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        return outreach_service.initiate_outreach(db, current_user, job)
    except outreach_service.TierRequiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except outreach_service.InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except outreach_service.ResumeRequiredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except outreach_service.MissingCompanyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Drafting outreach failed: {e}")


@router.get("/mine", response_model=list[OutreachOut])
def list_my_outreach(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[Outreach]:
    return (
        db.query(Outreach)
        .filter(Outreach.user_id == current_user.id)
        .order_by(desc(Outreach.created_at))
        .all()
    )


@router.get("/{outreach_id}", response_model=OutreachOut)
def get_outreach(
    outreach_id: uuid.UUID,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> Outreach:
    result = db.get(Outreach, outreach_id)
    if not result or result.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    return result
