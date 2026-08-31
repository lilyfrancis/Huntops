from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.user import User
from app.schemas.stats import HuntStats
from app.services import stats as stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/me", response_model=HuntStats)
def my_stats(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    return stats_service.build_stats(db, current_user)
