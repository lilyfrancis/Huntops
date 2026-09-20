"""Paying to see one listing in full.

The company name is what lets somebody go around us and apply themselves,
so it is the thing worth charging for. What is bought is the fact, not a
session: unlocking is permanent, because charging again to re-read a job
someone already paid for would make them afraid to click.

Applying through the concierge unlocks it too — they committed, and it is
theirs to see.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.application import Application
from app.models.job import Job
from app.models.job_unlock import JobUnlock
from app.models.user import User
from app.services.credits import adjust_credits

settings = get_settings()


class InsufficientCredits(Exception):
    pass


def unlocked_ids(db: Session, user: User | None, job_ids: list | None = None) -> set:
    """Every job this user may see in full.

    Both sources in one query each rather than per job: the feed asks this
    once for forty listings, and a lookup per row would be eighty queries to
    render one page.
    """
    if user is None:
        return set()

    unlocks = select(JobUnlock.job_id).where(JobUnlock.user_id == user.id)
    applied = select(Application.job_id).where(Application.candidate_id == user.id)
    if job_ids is not None:
        unlocks = unlocks.where(JobUnlock.job_id.in_(job_ids))
        applied = applied.where(Application.job_id.in_(job_ids))

    return {row[0] for row in db.execute(unlocks)} | {row[0] for row in db.execute(applied)}


def unlock(db: Session, user: User, job: Job) -> bool:
    """Reveal one job. Returns whether credits were actually spent.

    Charging for something already unlocked is the mistake this guards
    against — a double-clicked button, a retried request, a job they applied
    to last week.
    """
    if job.source == "internal":
        return False
    if job.id in unlocked_ids(db, user, [job.id]):
        return False

    if user.ai_credits < settings.UNLOCK_CREDIT_COST:
        raise InsufficientCredits(
            f"Seeing this job costs {settings.UNLOCK_CREDIT_COST} credits and you have {user.ai_credits}."
        )

    db.add(JobUnlock(user_id=user.id, job_id=job.id))
    try:
        db.flush()
    except IntegrityError:
        # Two clicks racing. The unlock exists either way, so nothing is owed.
        db.rollback()
        return False

    adjust_credits(db, user, action="unlock_job", amount=-settings.UNLOCK_CREDIT_COST)
    db.commit()
    return True
