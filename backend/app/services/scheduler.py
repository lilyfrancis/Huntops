import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import desc

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.services import digest, ghost_detection, matching, notifications
from app.services.aggregation import ingest_all
from app.services.ai_client import AIResponseError
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
        notifications.alert_admin("Daily aggregation job crashed", str(e))
    finally:
        db.close()


def _run_ghost_rescan() -> None:
    db = SessionLocal()
    try:
        summary = ghost_detection.rescan_all(db)
        logger.info("Scheduled ghost rescan complete: %s", summary)
    except Exception as e:
        logger.error("Scheduled ghost rescan failed: %s", e)
        notifications.alert_admin("Daily ghost rescan job crashed", str(e))
    finally:
        db.close()


def _run_email_sync() -> None:
    db = SessionLocal()
    try:
        summary = sync_all_connected_users(db)
        logger.info("Scheduled email sync complete for %d users", len(summary))
    except Exception as e:
        logger.error("Scheduled email sync failed: %s", e)
        notifications.alert_admin("Daily email sync job crashed", str(e))
    finally:
        db.close()


def _run_daily_digest() -> None:
    from app.models.enums import JobStatus, UserRole
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.user import User

    db = SessionLocal()
    sent_count = 0
    try:
        seekers = (
            db.query(User)
            .join(Resume, Resume.user_id == User.id)
            .filter(User.role == UserRole.job_seeker, User.is_suspended.is_(False))
            .all()
        )
        candidate_jobs = (
            db.query(Job)
            .filter(Job.status == JobStatus.active)
            .order_by(desc(Job.created_at))
            .limit(settings.MAX_MATCH_CANDIDATES)
            .all()
        )

        for user in seekers:
            resume = db.query(Resume).filter(Resume.user_id == user.id).first()
            try:
                scored = matching.score_jobs(resume, candidate_jobs, user.home_market)
                matching.persist_matches(db, user, scored)
                db.commit()
            except AIResponseError as e:
                logger.warning("Digest scoring failed for user=%s: %s", user.id, e)
                db.rollback()
                continue

            matches = digest.get_top_matches(db, user)
            subject, body = digest.format_digest_email(matches)
            if notifications.send_email(user.email, subject, body):
                sent_count += 1

        logger.info("Daily digest sent to %d/%d job seekers", sent_count, len(seekers))
    except Exception as e:
        logger.error("Scheduled digest failed: %s", e)
        notifications.alert_admin("Daily digest job crashed", str(e))
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
    if settings.ENABLE_SCHEDULED_AGGREGATION:
        # Between ingest and digest: staleness signals accrue daily, so scores
        # have to be refreshed before the digest picks what to send.
        _scheduler.add_job(_run_ghost_rescan, "cron", hour=7, minute=20, id="daily_ghost_rescan")
    if settings.ENABLE_SCHEDULED_DIGEST:
        # After both — the digest scores against jobs aggregation/email-sync just refreshed.
        _scheduler.add_job(_run_daily_digest, "cron", hour=7, minute=30, id="daily_digest")

    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info("Scheduler started with %d job(s)", len(_scheduler.get_jobs()))
    return _scheduler


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None
