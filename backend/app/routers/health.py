from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.base import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:  # pragma: no cover - defensive
        db_status = f"unhealthy: {e}"

    return {"status": "healthy" if db_status == "healthy" else "degraded", "database": db_status}


@router.get("/api/health/detailed", dependencies=[Depends(require_admin)])
def detailed_health_check(db: Session = Depends(get_db)) -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    checks = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:  # pragma: no cover
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    checks["stripe"] = {"configured": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)}
    return checks
