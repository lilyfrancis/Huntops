from datetime import datetime, timedelta, timezone
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import desc, func

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.services import (
    autopilot,
    concierge,
    digest,
    ghost_detection,
    matching,
    notifications,
    preferences,
    resume_selection,
    unlocking,
    whatsapp,
)
from app.services.aggregation import ingest_all
from app.services.ai_client import AIResponseError
from app.models.email_sync_run import EmailSyncRun
from app.models.ingestion_run import IngestionRun
from app.services.alert_mailboxes import sync_all_mailboxes

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
        results = sync_all_mailboxes(db)
        failed = [r for r in results if r["status"] != "success"]
        logger.info("Scheduled mailbox sync complete: %d mailbox(es), %d failed", len(results), len(failed))
        if failed:
            # A silently dead mailbox is a market whose feed quietly stops
            # filling, which nobody notices until users complain.
            notifications.alert_admin(
                "Alert mailbox sync errors",
                "\n".join(f"{r['mailbox']} ({r['market']}): {r['error']}" for r in failed),
            )
    except Exception as e:
        logger.error("Scheduled email sync failed: %s", e)
        notifications.alert_admin("Daily email sync job crashed", str(e))
    finally:
        db.close()


def _is_dormant(user) -> bool:
    """Whether to leave this account alone this morning.

    A null `last_seen_at` counts as active: the column arrived after some
    accounts did, and skipping somebody because of when a migration ran would
    be the wrong kind of saving.
    """
    days = settings.DIGEST_DORMANT_AFTER_DAYS
    if days <= 0 or user.last_seen_at is None:
        return False
    last = user.last_seen_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last) > timedelta(days=days)


def _deliver_email(user, matches, unlocked=None) -> bool:
    subject, body = digest.format_digest_email(matches, unlocked)
    return notifications.send_email(user.email, subject, body)


def _deliver_whatsapp(user, matches, unlocked=None) -> bool:
    """False whenever the message did not go out, for any reason: no number
    on file, no provider configured, or Meta rejecting it."""
    if not user.whatsapp_number:
        return False
    if user.whatsapp_opted_in_at is None:
        # Meta drops a marketing template to anyone who has never messaged the
        # business, accepting the send with a 200 and delivering nothing. Not
        # sending is the same outcome and says so out loud, instead of
        # reporting a success that never reached anybody.
        logger.info(
            "Skipping WhatsApp digest for user=%s: not opted in — Meta would drop it silently",
            user.id,
        )
        return False
    params = digest.format_digest_whatsapp(user, matches, unlocked)
    # None means no matches. A daily "nothing today" email is ignorable; the
    # same on WhatsApp gets the number blocked, and a block is permanent.
    if params is None:
        return False
    return whatsapp.send_template(to=user.whatsapp_number, params=params)


def _run_daily_digest() -> None:
    from app.models.enums import UserRole
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.user import User

    db = SessionLocal()
    sent_count = 0
    skipped_dormant = 0
    try:
        seekers = (
            db.query(User)
            .join(Resume, Resume.user_id == User.id)
            .filter(User.role == UserRole.job_seeker, User.is_suspended.is_(False))
            .all()
        )

        for user in seekers:
            if _is_dormant(user):
                # Not reading the digest, and the morning run spends real
                # money telling them so. Signing in resumes it next morning —
                # nothing is deleted and no setting of theirs changes.
                skipped_dormant += 1
                continue

            # Candidates are drawn per user now, not once for everyone: supply
            # is a single pool spanning every market, so a shared candidate set
            # would spend a Canadian marketer's scoring budget on UK engineering
            # roles they asked not to see.
            prefs = preferences.get_or_create(db, user)
            # Only what this user has never been scored against. A job sits in
            # the newest-forty window for days, so the old query paid to score
            # — and to reject — the same jobs every morning.
            candidate_jobs = matching.unscored_for(
                db, user, preferences.feed_query(db, prefs), settings.MAX_MATCH_CANDIDATES
            )
            if not candidate_jobs:
                # Nothing new today. The digest still goes out from what was
                # already scored, so a quiet supply day is not a silent one.
                candidate_jobs = []

            try:
                # Grouped by the CV each job calls for. One CV is one group
                # and one call, exactly as before; a user who keeps an
                # engineering CV and a sales CV gets two, which is the trade
                # they made by uploading two.
                for resume, group in resume_selection.group_by_resume(db, user, candidate_jobs):
                    scored = matching.score_jobs(resume, group, user.home_market)
                    matching.persist_matches(db, user, scored)
                db.commit()
            except AIResponseError as e:
                logger.warning("Digest scoring failed for user=%s: %s", user.id, e)
                db.rollback()
                continue

            matches = digest.get_top_matches(db, user)
            channel = prefs.digest_channel
            delivered = False

            # The digest is redacted the same way the feed is. Mailing the
            # company name every morning would be a more convenient leak
            # than the website ever was.
            unlocked = unlocking.unlocked_ids(db, user, [job.id for _m, job in matches])

            if channel in ("email", "both"):
                delivered = _deliver_email(user, matches, unlocked)

            if channel in ("whatsapp", "both"):
                delivered = _deliver_whatsapp(user, matches, unlocked) or delivered

            if channel == "whatsapp" and not delivered and matches:
                # Choosing WhatsApp is a preference about where to be reached,
                # not a request to be told nothing. A missing number, a
                # provider that was never configured, an expired token — none
                # of those are visible to the person waiting on their matches,
                # and all of them would otherwise mean silence. Email carries
                # the digest instead. Guarded on `matches` so a genuinely empty
                # day still sends nothing.
                delivered = _deliver_email(user, matches, unlocked)

            if delivered:
                sent_count += 1

        logger.info(
            "Daily digest sent to %d/%d job seekers (%d skipped as dormant)",
            sent_count, len(seekers), skipped_dormant,
        )
    except Exception as e:
        logger.error("Scheduled digest failed: %s", e)
        notifications.alert_admin("Daily digest job crashed", str(e))
    finally:
        db.close()


def _run_concierge_backlog() -> None:
    """Chase anything still waiting to be filed.

    The per-request email can be missed — read on a phone, buried, sent
    while nobody was working. This one keeps arriving until the queue is
    worked, and says nothing at all when it is current.
    """
    db = SessionLocal()
    try:
        waiting = concierge.alert_on_backlog(db)
        if waiting:
            logger.info("Concierge backlog: %d application(s) past the SLA", waiting)
    except Exception as e:
        logger.error("Concierge backlog check failed: %s", e)
    finally:
        db.close()


def _run_autopilot() -> None:
    db = SessionLocal()
    try:
        summary = autopilot.run_all(db)
        logger.info("Scheduled autopilot complete: %s", summary)
    except Exception as e:
        logger.error("Scheduled autopilot failed: %s", e)
        notifications.alert_admin("Daily autopilot job crashed", str(e))
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if settings.ENVIRONMENT == "test":
        return None

    # This scheduler lives inside the API process, so every uvicorn worker would
    # otherwise start its own copy and fire each cron job once per worker —
    # four workers would send every user four digests and run aggregation four
    # times. In production the API runs with RUN_SCHEDULER=false and a single
    # dedicated scheduler container owns the jobs.
    if not settings.RUN_SCHEDULER:
        logger.info("Scheduler disabled in this process (RUN_SCHEDULER=false)")
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
    if settings.ENABLE_SCHEDULED_AUTOPILOT:
        # Last, and only after the digest: autopilot acts on fit scores, and the
        # digest run is what refreshes them. Firing first would have it applying
        # on yesterday's scores against today's jobs.
        _scheduler.add_job(_run_autopilot, "cron", hour=8, minute=0, id="daily_autopilot")

    # Twice a day rather than once: a request that arrives just after the
    # morning run would otherwise wait a full day before anyone is chased,
    # which is most of the SLA spent before the first reminder.
    _scheduler.add_job(_run_concierge_backlog, "cron", hour="9,16", minute=0, id="concierge_backlog")

    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info("Scheduler started with %d job(s)", len(_scheduler.get_jobs()))
        # Queued rather than called inline: this runs during application
        # startup, and a slow mailbox would hold the container in "starting"
        # long enough for an orchestrator to decide it had failed.
        _scheduler.add_job(catch_up, id="startup_catch_up")
    return _scheduler


def _hours_since_last(model, column) -> float | None:
    """Hours since the newest row, or None if there has never been one."""
    db = SessionLocal()
    try:
        newest = db.query(func.max(column)).scalar()
    finally:
        db.close()
    if newest is None:
        return None
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - newest).total_seconds() / 3600


def catch_up(run_now=None) -> list[str]:
    """Run the daily jobs immediately if they have not run in too long.

    APScheduler holds its jobs in memory, so a restart does not carry a
    missed run with it: the cron slot simply passes unobserved and the next
    one is tomorrow. That is fine for a container that restarts at noon and
    harmless for one that restarts at midnight — and catastrophic for one
    that was down for a fortnight, which is what happened here. Thirteen days
    with no aggregation and no mailbox sync, every surface reporting success,
    because the failure was an absence and nothing was watching for one.

    So on boot: if the last run is older than the threshold, do it now rather
    than waiting for 07:00. A restart inside the normal daily rhythm triggers
    nothing, because the last run is only hours old.

    Deliberately not the digest or autopilot. Those send mail and act in
    somebody's name, and a container that restarts six times during a deploy
    must not mail everyone six times. Aggregation and mailbox sync are
    idempotent — both dedupe on source_url, and the mailbox resumes from a
    stored UID — so the worst case of running them twice is two wasted HTTP
    calls.
    """
    threshold = settings.CATCH_UP_AFTER_HOURS
    if threshold <= 0:
        return []

    due = []
    if settings.ENABLE_SCHEDULED_AGGREGATION:
        age = _hours_since_last(IngestionRun, IngestionRun.started_at)
        if age is None or age >= threshold:
            due.append(("aggregation", _run_daily_aggregation, age))
    if settings.ENABLE_SCHEDULED_EMAIL_SYNC:
        age = _hours_since_last(EmailSyncRun, EmailSyncRun.started_at)
        if age is None or age >= threshold:
            due.append(("email sync", _run_email_sync, age))

    ran = []
    for name, job, age in due:
        logger.warning(
            "Catch-up: %s last ran %s — running now rather than waiting for the next cron slot",
            name, f"{age:.0f}h ago" if age is not None else "never",
        )
        (run_now or (lambda fn: fn()))(job)
        ran.append(name)

    if ran:
        notifications.alert_admin(
            "Scheduled jobs had stopped",
            "On startup, these had not run in "
            f"{threshold} hours and were run immediately: {', '.join(ran)}.\n\n"
            "Nothing reports an absence on its own, so if this message is a surprise, "
            "the scheduler container was down and the job pool stopped filling.",
        )
    return ran


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None
