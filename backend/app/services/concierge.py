"""Filing an application on a site we cannot submit to.

An aggregated listing lives behind someone else's form. Until now the only
honest thing to offer was a link out — which hands the user back the exact
work the product exists to remove: opening thirty tabs and retyping the
same details into thirty different forms.

So the user says "apply", and a person at JobQuick AI files it for them, under
an address created for that user. From the user's side it is one click and
a status that moves. From ours it is a queue.

Nothing here pretends to be automatic. The application is `queued` until
somebody has actually submitted it, and the user sees that word.
"""

import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.application import Application
from app.models.application_draft import ApplicationDraft
from app.models.enums import ConciergeStatus, SubscriptionTier
from app.models.job import Job
from app.models.user import User
from app.services import notifications
from app.services.credits import adjust_credits

logger = logging.getLogger(__name__)
settings = get_settings()


class ConciergeError(Exception):
    """A refusal the user can act on, not a breakage."""


class AllowanceExhausted(ConciergeError):
    pass


class InsufficientCredits(ConciergeError):
    pass


def used_allowance(db: Session, user: User) -> int:
    """How many the user has ever asked for. Lifetime, not monthly: the free
    allowance is a taste of the feature, and resetting it monthly would make
    it a plan rather than a sample."""
    return (
        db.query(func.count(Application.id))
        .filter(Application.candidate_id == user.id, Application.is_concierge.is_(True))
        .scalar()
        or 0
    )


def allowance_remaining(db: Session, user: User) -> int | None:
    """None means unlimited — Elite is bounded by credits alone."""
    if user.subscription_tier == SubscriptionTier.elite:
        return None
    return max(0, settings.CONCIERGE_FREE_ALLOWANCE - used_allowance(db, user))


def check_can_request(db: Session, user: User) -> None:
    """Raises the specific refusal, so the UI can say which wall was hit.

    Checked before anything is written or charged: a user told "you have no
    credits" after being charged would be right to be angry.
    """
    remaining = allowance_remaining(db, user)
    if remaining is not None and remaining <= 0:
        raise AllowanceExhausted(
            f"You have used all {settings.CONCIERGE_FREE_ALLOWANCE} of your concierge applications. "
            f"Elite removes the limit."
        )
    if user.ai_credits < settings.CONCIERGE_CREDIT_COST:
        raise InsufficientCredits(
            f"Applying for you costs {settings.CONCIERGE_CREDIT_COST} credits "
            f"and you have {user.ai_credits}."
        )


def request(db: Session, user: User, job: Job) -> Application:
    """Queue an application for someone to file. Charges on success only."""
    check_can_request(db, user)

    draft = (
        db.query(ApplicationDraft)
        .filter(ApplicationDraft.user_id == user.id, ApplicationDraft.job_id == job.id)
        .first()
    )

    application = Application(
        job_id=job.id,
        candidate_id=user.id,
        candidate_name=user.full_name,
        candidate_email=user.email,
        cover_letter=draft.cover_letter if draft else None,
        tailored_bullets=list(draft.bullets) if draft else [],
        is_concierge=True,
        concierge_status=ConciergeStatus.queued,
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConciergeError("You have already applied to this job.")

    job.application_count += 1
    adjust_credits(db, user, action="concierge_apply", amount=-settings.CONCIERGE_CREDIT_COST)
    db.commit()
    db.refresh(application)

    _notify_admin(user, job)
    return application


def _notify_admin(user: User, job: Job) -> None:
    """Best-effort, and deliberately after the commit.

    The request is the user's; a mail server being down is ours. Letting a
    failed notification roll back a paid-for request would be charging
    someone for our outage.
    """
    if not settings.NOTIFY_ADMIN_ON_CONCIERGE:
        return
    try:
        notifications.alert_admin(
            f"Apply for {user.full_name}: {job.title}",
            f"{user.full_name} <{user.email}> asked us to apply.\n\n"
            f"{job.title} at {job.company_name or 'a company'} — {job.location}\n"
            f"{job.source_url or 'no link on the listing'}\n\n"
            f"Apply under: {user.concierge_email or suggest_concierge_email(user) + ' (not created yet)'}\n\n"
            f"Queue: {settings.FRONTEND_URL}/admin/concierge",
        )
    except Exception:
        # Never surfaced to the user — they did their part and were charged
        # for it; whether we managed to email ourselves is not their problem.
        logger.exception("Could not notify an admin about a concierge request")


def overdue(db: Session, *, hours: int | None = None) -> list[Application]:
    """Requests that have sat too long. The per-request email can be missed;
    this one keeps arriving until the queue is worked."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours or settings.CONCIERGE_SLA_HOURS)
    return (
        db.query(Application)
        .filter(
            Application.is_concierge.is_(True),
            Application.concierge_status == ConciergeStatus.queued,
            Application.created_at < cutoff,
        )
        .order_by(Application.created_at)
        .all()
    )


def alert_on_backlog(db: Session) -> int:
    """Alert if anything has been waiting past the SLA. Returns how many.

    Silent when the queue is current: a daily "nothing to do" mail is how a
    daily alert stops being read, and this one has to be read.
    """
    waiting = overdue(db)
    if not waiting:
        return 0

    oldest = waiting[0].created_at
    notifications.alert_admin(
        f"{len(waiting)} application(s) still waiting to be filed",
        f"The oldest has been queued since {oldest:%Y-%m-%d %H:%M} UTC.\n\n"
        + "\n".join(f"- {a.candidate_name}: {a.job_id}" for a in waiting[:20])
        + f"\n\n{settings.FRONTEND_URL}/admin/concierge",
    )
    return len(waiting)


def queue(db: Session, *, status: ConciergeStatus | None = ConciergeStatus.queued) -> list[Application]:
    """What is waiting to be filed, oldest first — it is a work queue, so the
    person who has been waiting longest goes next."""
    q = db.query(Application).filter(Application.is_concierge.is_(True))
    if status is not None:
        q = q.filter(Application.concierge_status == status)
    return q.order_by(Application.created_at).all()


def mark(
    db: Session,
    application: Application,
    admin: User,
    *,
    concierge_status: ConciergeStatus,
    note: str | None = None,
) -> Application:
    """Record what the admin did, and who did it."""
    from datetime import datetime, timezone

    application.concierge_status = concierge_status
    application.handled_by_id = admin.id
    if note is not None:
        application.concierge_note = note.strip() or None
    if concierge_status is ConciergeStatus.submitted and application.submitted_at is None:
        application.submitted_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(application)
    return application


def suggest_concierge_email(user: User) -> str:
    """A starting point for the mailbox an admin creates, not an identity.

    First name, lowercased, non-letters stripped. Collisions are real — two
    Jennifers — so this is only ever a suggestion the admin edits, and the
    address actually used is what gets stored.
    """
    first = (user.full_name or "").strip().split(" ")[0]
    cleaned = "".join(ch for ch in first.lower() if ch.isalpha()) or "candidate"
    return f"{cleaned}@jobquickai.site"
