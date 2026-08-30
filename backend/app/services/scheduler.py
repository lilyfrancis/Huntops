import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.services.aggregation import ingest_all

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def _run_daily_aggregation() -> None:
    db = SessionLocal()
    try:
        summary = ingest_all(db)
        logger.info("Scheduled aggregation complete: %s", summary)
    except Exception as e:  # the job runner has no caller to raise to
        logger.error("Scheduled aggregation failed: %s", e)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.ENABLE_SCHEDULED_AGGREGATION or settings.ENVIRONMENT == "test":
        return None
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_run_daily_aggregation, "cron", hour=7, minute=0, id="daily_aggregation")
    _scheduler.start()
    logger.info("Scheduler started — daily aggregation runs at 07:00 UTC")
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
