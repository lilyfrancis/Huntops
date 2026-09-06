"""Acting on a user's behalf, once they've said how far they trust it.

Two switches, deliberately separate because they are not the same promise:

  * Auto-apply submits an application to *internal* listings above a score
    threshold. It only works on internal jobs, and that is not a limitation
    we can engineer away — an aggregated listing lives behind someone else's
    form on someone else's site. A button claiming to apply to those would be
    a lie, so external jobs get outreach instead.

  * Auto-outreach finds a hiring contact via Apollo, drafts a pitch, and sends
    it. That is the path for external jobs, and it costs credits and Elite tier.

Every decision writes an AutopilotAction, skips included. Something acting in
your name without asking owes you a record of what it did and why it stopped.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.autopilot_action import AutopilotAction
from app.models.enums import UserRole
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services import outreach as outreach_service
from app.services import preferences
from app.services.ai_client import AIResponseError

logger = logging.getLogger(__name__)

APPLY = "apply"
OUTREACH = "outreach"

DONE = "done"
SKIPPED = "skipped"
FAILED = "failed"


def _record(db: Session, user: User, job: Job, action: str, status: str, detail: str, score: float | None) -> None:
    db.add(AutopilotAction(
        user_id=user.id, job_id=job.id, action=action, status=status, detail=detail, fit_score=score
    ))


def _acted_job_ids(db: Session, user: User) -> set:
    """Jobs autopilot has already reached a verdict on, in either direction.

    Skips count. Re-evaluating a job we already declined every night would
    re-run the same reasoning to the same answer, and the day a threshold or a
    score moved slightly it would fire on something the user has, in effect,
    already been shown as out of scope.
    """
    return {
        job_id
        for (job_id,) in db.query(AutopilotAction.job_id).filter(AutopilotAction.user_id == user.id).all()
    }


def _used_today(db: Session, user: User) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return (
        db.query(AutopilotAction)
        .filter(
            AutopilotAction.user_id == user.id,
            AutopilotAction.status == DONE,
            AutopilotAction.created_at >= since,
        )
        .count()
    )


def _apply(db: Session, user: User, job: Job, score: float) -> bool:
    application = Application(
        job_id=job.id,
        candidate_id=user.id,
        candidate_name=user.full_name,
        candidate_email=user.email,
        cover_letter=None,
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError:
        # They applied by hand between scoring and now. Not a failure — the
        # goal (an application exists) is already met.
        db.rollback()
        _record(db, user, job, APPLY, SKIPPED, "Already applied manually", score)
        return False

    job.application_count += 1
    _record(db, user, job, APPLY, DONE, f"Applied automatically at fit {score:.0f}", score)
    return True


def _outreach(db: Session, user: User, job: Job, score: float) -> bool:
    try:
        result = outreach_service.initiate_outreach(db, user, job)
    except (
        outreach_service.TierRequiredError,
        outreach_service.InsufficientCreditsError,
        outreach_service.ResumeRequiredError,
        outreach_service.MissingCompanyError,
    ) as e:
        # Expected refusals, not breakage: the user is on the wrong plan, out
        # of credits, or the listing has nothing to search on.
        _record(db, user, job, OUTREACH, SKIPPED, str(e), score)
        return False
    except AIResponseError as e:
        logger.warning("Autopilot outreach draft failed for user=%s job=%s: %s", user.id, job.id, e)
        _record(db, user, job, OUTREACH, FAILED, f"Drafting failed: {e}", score)
        return False

    _record(db, user, job, OUTREACH, DONE, f"Outreach {result.status.value} at fit {score:.0f}", score)
    return True


def run_for_user(db: Session, user: User) -> dict:
    """One autopilot pass for one user. Never raises — returns what it did."""
    summary = {"applied": 0, "outreach": 0, "skipped": 0, "failed": 0, "capped": False}

    prefs = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if prefs is None or not (prefs.autopilot_apply_enabled or prefs.autopilot_outreach_enabled):
        return summary

    remaining = prefs.autopilot_daily_cap - _used_today(db, user)
    if remaining <= 0:
        summary["capped"] = True
        return summary

    # The lowest bar either switch could clear, so one query serves both.
    floor = min(
        prefs.autopilot_apply_threshold if prefs.autopilot_apply_enabled else 100,
        prefs.autopilot_outreach_threshold if prefs.autopilot_outreach_enabled else 100,
    )

    # Scoped through the same preference filter as the visible feed, so
    # autopilot can never act on a job the user would not have been shown.
    candidates = (
        preferences.feed_query(db, prefs)
        .join(JobMatch, (JobMatch.job_id == Job.id) & (JobMatch.user_id == user.id))
        .filter(JobMatch.fit_score >= floor)
        .order_by(desc(JobMatch.fit_score))
        .limit(remaining * 4)  # headroom: many candidates get skipped
        .all()
    )
    if not candidates:
        return summary

    scores = {
        m.job_id: m.fit_score
        for m in db.query(JobMatch)
        .filter(JobMatch.user_id == user.id, JobMatch.job_id.in_([j.id for j in candidates]))
        .all()
    }
    already = _acted_job_ids(db, user)

    for job in candidates:
        if remaining <= 0:
            summary["capped"] = True
            break
        if job.id in already:
            continue

        score = scores.get(job.id)
        if score is None:
            continue

        is_internal = job.source == "internal"
        if is_internal and prefs.autopilot_apply_enabled and score >= prefs.autopilot_apply_threshold:
            acted = _apply(db, user, job, score)
        elif not is_internal and prefs.autopilot_outreach_enabled and score >= prefs.autopilot_outreach_threshold:
            acted = _outreach(db, user, job, score)
        else:
            continue

        already.add(job.id)
        if acted:
            remaining -= 1
            summary["applied" if is_internal else "outreach"] += 1
        else:
            summary["skipped"] += 1

    db.commit()
    return summary


def run_all(db: Session) -> dict:
    """Every job seeker with autopilot on — the scheduled job's entry point."""
    users = (
        db.query(User)
        .join(UserPreference, UserPreference.user_id == User.id)
        .filter(
            User.role == UserRole.job_seeker,
            User.is_suspended.is_(False),
            (UserPreference.autopilot_apply_enabled.is_(True))
            | (UserPreference.autopilot_outreach_enabled.is_(True)),
        )
        .all()
    )

    totals = {"users": len(users), "applied": 0, "outreach": 0, "skipped": 0, "failed": 0}
    for user in users:
        try:
            result = run_for_user(db, user)
        except Exception as e:
            # One user's bad state must not stop the rest of the run.
            logger.error("Autopilot failed for user=%s: %s", user.id, e)
            db.rollback()
            totals["failed"] += 1
            continue
        for key in ("applied", "outreach", "skipped", "failed"):
            totals[key] += result[key]
    return totals


def recent_actions(db: Session, user: User, limit: int = 25) -> list[AutopilotAction]:
    return (
        db.query(AutopilotAction)
        .filter(AutopilotAction.user_id == user.id)
        .order_by(desc(AutopilotAction.created_at))
        .limit(limit)
        .all()
    )
