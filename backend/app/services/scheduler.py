import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.services.aggregation import ingest_all
from app.services.email_bridge import sync_all_connected_users

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


def _run_email_sync() -> None:
    db = SessionLocal()
    try:
        summary = sync_all_connected_users(db)
        logger.info("Scheduled email sync complete for %d users", len(summary))
    except Exception as e:
        logger.error("Scheduled email sync failed: %s", e)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if settings.ENVIRONMENT == "test":
        return None
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    if settings.ENABLE_SCHEDULED_AGGREGATION:
        _scheduler.add_job(_run_daily_aggregation, "cron", hour=7, minute=0, id="daily_aggregation")
    if settings.ENABLE_SCHEDULED_EMAIL_SYNC:
        # 10 minutes after aggregation, matching Job Engine's original stagger
        # (Phase 1 at 7:00, Phase 2 email bridge at 7:10) so both don't hit the DB at once.
        _scheduler.add_job(_run_email_sync, "cron", hour=7, minute=10, id="daily_email_sync")

    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info("Scheduler started with %d job(s)", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None
