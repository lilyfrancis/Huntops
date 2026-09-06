from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.user import User
from app.schemas.autopilot import AutopilotActionOut, AutopilotRunSummary
from app.services import autopilot

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


@router.get("/actions", response_model=list[AutopilotActionOut])
def list_actions(
    limit: int = Query(25, ge=1, le=200),
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
):
    """The receipt: everything autopilot did in this user's name, and every
    job it looked at and passed on, newest first."""
    return autopilot.recent_actions(db, current_user, limit=limit)


@router.post("/run", response_model=AutopilotRunSummary)
def run_now(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    """Run this user's autopilot immediately instead of waiting for the
    nightly pass. Subject to the same daily cap, so this can't be used to
    get around it by clicking repeatedly."""
    return autopilot.run_for_user(db, current_user)
