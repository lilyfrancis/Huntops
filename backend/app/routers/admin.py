import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_admin
from app.db.base import get_db
from app.models.alert_mailbox import AlertMailbox
from app.models.alert_sender import AlertSender
from app.models.application import Application
from app.models.email_sync_run import EmailSyncRun
from app.models.enums import JobStatus, OutreachStatus, SubscriptionTier, UserRole
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.user import User
from app.schemas.job import JobOut, JobRejectRequest
from app.schemas.mailbox import (
    AlertSenderCreate,
    AlertSenderOut,
    MailboxOut,
    MailboxSyncResult,
    MailboxTestResult,
    MailboxUpdate,
    MailboxUpsert,
)
from app.schemas.user import UserOut
from app.services import alert_mailboxes, ghost_detection, integration_checks
from app.services.imap_client import ImapError
from app.services.aggregation import ingest_all

settings = get_settings()

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(desc(User.created_at)).offset(skip).limit(limit).all()


@router.put("/users/{user_id}/approve", response_model=UserOut)
def approve_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/suspend", response_model=UserOut)
def suspend_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_suspended = True
    db.commit()
    db.refresh(user)
    return user


@router.get("/jobs/pending", response_model=list[JobOut])
def list_pending_jobs(db: Session = Depends(get_db)) -> list[Job]:
    return db.query(Job).filter(Job.status == JobStatus.pending).order_by(desc(Job.created_at)).all()


@router.put("/jobs/{job_id}/approve", response_model=JobOut)
def approve_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.active
    job.rejection_reason = None
    db.commit()
    db.refresh(job)
    return job


@router.put("/jobs/{job_id}/reject", response_model=JobOut)
def reject_job(job_id: uuid.UUID, payload: JobRejectRequest, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.rejected
    job.rejection_reason = payload.reason
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/aggregate")
def trigger_aggregation(db: Session = Depends(get_db)) -> dict:
    """Manually run the aggregation pipeline on demand (also runs daily via the scheduler)."""
    return ingest_all(db)


@router.post("/jobs/rescan-ghosts")
def trigger_ghost_rescan(db: Session = Depends(get_db)) -> dict:
    """Re-score every job for ghost signals (also runs daily via the scheduler)."""
    return ghost_detection.rescan_all(db)


@router.get("/jobs/aggregation-runs")
def list_aggregation_runs(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    runs = db.query(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "status": r.status,
            "fetched_count": r.fetched_count,
            "inserted_count": r.inserted_count,
            "error": r.error,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
        }
        for r in runs
    ]


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)) -> dict:
    """Consolidated business + ops health — the equivalent of JobQuick's
    analytics endpoint, extended with the ingestion/outreach visibility
    that endpoint never had because its supply and outreach were fake."""
    total_users = db.query(User).count()
    job_seekers = db.query(User).filter(User.role == UserRole.job_seeker).count()
    employers = db.query(User).filter(User.role == UserRole.employer).count()
    pro_count = db.query(User).filter(User.subscription_tier == SubscriptionTier.pro).count()
    elite_count = db.query(User).filter(User.subscription_tier == SubscriptionTier.elite).count()

    total_jobs = db.query(Job).count()
    active_jobs = db.query(Job).filter(Job.status == JobStatus.active).count()
    featured_jobs = db.query(Job).filter(Job.is_featured.is_(True)).count()
    aggregated_jobs = db.query(Job).filter(Job.source != "internal").count()

    total_applications = db.query(Application).count()

    total_outreach = db.query(Outreach).count()
    sent_outreach = db.query(Outreach).filter(Outreach.status == OutreachStatus.sent).count()

    recent_runs = db.query(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(30).all()
    ingestion_success_rate = (
        sum(1 for r in recent_runs if r.status == "success") / len(recent_runs) if recent_runs else None
    )

    return {
        "users": {
            "total": total_users, "job_seekers": job_seekers, "employers": employers,
            "pro": pro_count, "elite": elite_count,
        },
        "jobs": {
            "total": total_jobs, "active": active_jobs, "featured": featured_jobs, "aggregated": aggregated_jobs,
        },
        "applications": {"total": total_applications},
        "outreach": {
            "total": total_outreach, "sent": sent_outreach,
            "success_rate": (sent_outreach / total_outreach) if total_outreach else None,
        },
        "ingestion_health": {
            "recent_runs_checked": len(recent_runs), "success_rate": ingestion_success_rate,
        },
        "revenue": {
            "monthly_recurring_estimate": round(pro_count * settings.PRO_PRICE + elite_count * settings.ELITE_PRICE, 2),
            "currency": settings.BILLING_CURRENCY,
            "pro_subs": pro_count, "elite_subs": elite_count,
        },
    }


@router.get("/email-sync-runs")
def list_email_sync_runs(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Health of every alert-mailbox sync, newest first.

    Mailbox rows are named, because these are the operator's own inboxes and
    naming them is the point. Legacy rows from when users mined their own
    inboxes are still listed but carry only a user id, never an address.
    """
    runs = db.query(EmailSyncRun).order_by(desc(EmailSyncRun.started_at)).limit(limit).all()
    mailbox_labels = {m.id: m.label for m in db.query(AlertMailbox).all()}
    return [
        {
            "id": str(r.id),
            "mailbox_id": str(r.mailbox_id) if r.mailbox_id else None,
            "mailbox": mailbox_labels.get(r.mailbox_id),
            "user_id": str(r.user_id) if r.user_id else None,
            "status": r.status,
            "fetched_count": r.fetched_count,
            "extracted_count": r.extracted_count,
            "inserted_count": r.inserted_count,
            "error": r.error,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
        }
        for r in runs
    ]


# ---------- alert mailboxes: the shared supply every user's feed is drawn from ----------

@router.get("/mailboxes", response_model=list[MailboxOut])
def list_mailboxes(db: Session = Depends(get_db)) -> list[AlertMailbox]:
    return db.query(AlertMailbox).order_by(AlertMailbox.market, AlertMailbox.label).all()


@router.put("/mailboxes", response_model=MailboxOut)
def upsert_mailbox(
    payload: MailboxUpsert,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertMailbox:
    """Add a mailbox, or update the one already on that address.

    PUT rather than POST because it is idempotent on the email address:
    re-submitting is how an operator rotates a password or moves hosts.
    """
    try:
        return alert_mailboxes.upsert_mailbox(
            db,
            admin_id=current_user.id,
            email_address=payload.email_address,
            market=payload.market,
            imap_host=payload.imap_host,
            imap_port=payload.imap_port,
            imap_username=payload.imap_username,
            imap_password=payload.imap_password,
            imap_use_ssl=payload.imap_use_ssl,
            imap_folder=payload.imap_folder,
            label=payload.label,
            lanes=payload.lanes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _get_mailbox(mailbox_id: uuid.UUID, db: Session) -> AlertMailbox:
    mailbox = db.get(AlertMailbox, mailbox_id)
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mailbox


@router.post("/mailboxes/{mailbox_id}/test", response_model=MailboxTestResult)
def test_mailbox(mailbox_id: uuid.UUID, db: Session = Depends(get_db)) -> MailboxTestResult:
    """Log in and open the folder, nothing more.

    Exists so an operator finds out a password is wrong while they are looking
    at the form, rather than from an empty feed the next morning.
    """
    try:
        alert_mailboxes.test_connection(_get_mailbox(mailbox_id, db))
    except ImapError as e:
        return MailboxTestResult(ok=False, detail=str(e))
    return MailboxTestResult(ok=True, detail="Connected and opened the folder successfully")


@router.patch("/mailboxes/{mailbox_id}", response_model=MailboxOut)
def update_mailbox(
    mailbox_id: uuid.UUID,
    payload: MailboxUpdate,
    db: Session = Depends(get_db),
) -> AlertMailbox:
    mailbox = _get_mailbox(mailbox_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(mailbox, field, value)
    db.commit()
    db.refresh(mailbox)
    return mailbox


@router.delete("/mailboxes/{mailbox_id}", status_code=204)
def delete_mailbox(mailbox_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Removes the mailbox and its stored credentials.

    Jobs it already ingested stay — they are real listings, and deleting a
    mailbox shouldn't empty the feed of everyone matched to them.
    """
    alert_mailboxes.delete_mailbox(db, _get_mailbox(mailbox_id, db))


@router.post("/mailboxes/{mailbox_id}/sync", response_model=MailboxSyncResult)
def sync_mailbox(mailbox_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return alert_mailboxes.sync_mailbox(db, _get_mailbox(mailbox_id, db))


@router.post("/mailboxes/sync", response_model=list[MailboxSyncResult])
def sync_all_mailboxes(db: Session = Depends(get_db)) -> list[dict]:
    return alert_mailboxes.sync_all_mailboxes(db)


# ---------- alert senders: which domains count as job alerts ----------

@router.get("/alert-senders", response_model=list[AlertSenderOut])
def list_alert_senders(db: Session = Depends(get_db)) -> list[AlertSender]:
    return db.query(AlertSender).order_by(AlertSender.note, AlertSender.domain).all()


@router.post("/alert-senders", response_model=AlertSenderOut, status_code=201)
def add_alert_sender(
    payload: AlertSenderCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertSender:
    """Adding a board takes effect on the next sync — no redeploy.

    Re-adding an existing domain returns it rather than erroring: the natural
    way to reach this is from a mailbox reporting an unrecognised sender, and
    clicking twice should not be a failure.
    """
    existing = db.query(AlertSender).filter(AlertSender.domain == payload.domain).first()
    if existing:
        return existing

    sender = AlertSender(domain=payload.domain, note=payload.note, added_by_id=current_user.id)
    db.add(sender)
    db.commit()
    db.refresh(sender)
    return sender


@router.delete("/alert-senders/{sender_id}", status_code=204)
def delete_alert_sender(sender_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Removing a domain stops future mail from it being read. Jobs already
    ingested stay — they are real listings."""
    sender = db.get(AlertSender, sender_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.delete(sender)
    db.commit()


# ---------- integrations: does each key actually work ----------

@router.get("/integrations")
def integration_status() -> list[dict]:
    """Runs every check for real.

    Slower than reading config, deliberately: "the string is non-empty" was
    never the question, and a rotated key looks identical to a working one
    until a user hits the feature.
    """
    return [
        {"name": r.name, "configured": r.configured, "ok": r.ok, "detail": r.detail}
        for r in integration_checks.run_all()
    ]


@router.post("/integrations/{name}/test")
def test_integration(name: str) -> dict:
    check = integration_checks.CHECKS.get(name)
    if check is None:
        raise HTTPException(status_code=404, detail=f"No such integration: {name}")
    result = check()
    return {"name": result.name, "configured": result.configured, "ok": result.ok, "detail": result.detail}
