"""The supply side: admin-owned mailboxes feeding everyone's job pool.

The original design had each job seeker connect their own Gmail and mine their
own alerts. That put the hardest step of the product — subscribe to the right
alerts, in the right market, with the right filters — on the least motivated
person in the loop, and meant a user's feed was empty until they did it.

Here the operator points HuntOps at a handful of mailboxes instead, one per
market, each subscribed to that country's job alerts. Everything they receive
lands in one shared pool tagged by market, and a user's own preferences decide
which slice they see.
"""

import logging
import urllib.parse
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.models.alert_mailbox import AlertMailbox
from app.models.email_sync_run import EmailSyncRun
from app.models.enums import JobLane
from app.models.job import Job
from app.services import aggregation, imap_client
from app.services.ai_client import AIResponseError
from app.services.email_extraction import extract_jobs_from_email
from app.services.gmail_message import detect_provider
from app.services.imap_client import Credentials, ImapError

logger = logging.getLogger(__name__)
settings = get_settings()

_FALLBACK_SEARCH_TEMPLATES = {
    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={q}",
    "indeed": "https://www.indeed.com/jobs?q={q}",
    "glassdoor": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}",
}


def fallback_url(provider: str, title: str, company: str) -> str:
    """A search URL for alert emails that gave us no direct link.

    Doubles as the dedupe key, so it has to be stable for the same posting:
    same title and company must always produce the same URL, or one job
    re-inserts itself on every sync.
    """
    query = urllib.parse.quote(f"{title} {company}".strip())
    template = _FALLBACK_SEARCH_TEMPLATES.get(provider, _FALLBACK_SEARCH_TEMPLATES["linkedin"])
    return template.format(q=query)


def credentials_for(mailbox: AlertMailbox) -> Credentials:
    return Credentials(
        host=mailbox.imap_host,
        port=mailbox.imap_port,
        username=mailbox.imap_username,
        password=decrypt(mailbox.imap_password_encrypted),
        use_ssl=mailbox.imap_use_ssl,
        folder=mailbox.imap_folder,
    )


# ---------- configuring ----------

def upsert_mailbox(
    db: Session,
    *,
    admin_id: uuid.UUID | None,
    email_address: str,
    market: str,
    imap_host: str,
    imap_username: str | None,
    imap_password: str | None,
    imap_port: int = 993,
    imap_use_ssl: bool = True,
    imap_folder: str = "INBOX",
    label: str | None = None,
    lanes: list[str] | None = None,
) -> AlertMailbox:
    """Add a mailbox, or update the one already on that address.

    Re-submitting an existing address is how an operator rotates a password or
    moves a mailbox to a new host, so it updates in place rather than erroring
    or creating a second row that would double every job it reads.
    """
    mailbox = db.query(AlertMailbox).filter(AlertMailbox.email_address == email_address).first()
    is_new = mailbox is None

    if is_new:
        if not imap_password:
            raise ValueError("A password is required to add a mailbox")
        mailbox = AlertMailbox(email_address=email_address, added_by_id=admin_id)
        db.add(mailbox)

    mailbox.market = market
    mailbox.label = label or email_address
    mailbox.lanes = lanes or []
    mailbox.imap_host = imap_host
    mailbox.imap_port = imap_port
    mailbox.imap_username = imap_username or email_address
    mailbox.imap_use_ssl = imap_use_ssl
    mailbox.imap_folder = imap_folder
    mailbox.is_active = True

    # Only overwrite the stored secret when a new one was actually supplied —
    # an edit that changes only the market must not blank the password.
    if imap_password:
        mailbox.imap_password_encrypted = encrypt(imap_password)

    if not is_new:
        # Whatever went wrong before, the operator has just changed something;
        # let the next sync decide whether it is still broken.
        mailbox.last_error = None

    db.commit()
    db.refresh(mailbox)
    return mailbox


def test_connection(mailbox: AlertMailbox) -> None:
    """Raises ImapError with a readable reason, or returns cleanly."""
    imap_client.test_connection(credentials_for(mailbox))


def delete_mailbox(db: Session, mailbox: AlertMailbox) -> None:
    db.delete(mailbox)
    db.commit()


# ---------- syncing ----------

def _lane_for(mailbox: AlertMailbox, title: str, description: str) -> JobLane:
    """Infer the lane, falling back to the mailbox's own when inference gives up.

    A mailbox subscribed to exactly one lane is a real signal about everything
    in it, and it is better than `other` for a job whose title didn't match any
    pattern. It is only a fallback: when inference does match, the listing's own
    words beat the mailbox's label, because a marketing alert digest routinely
    carries one sales role.
    """
    inferred = aggregation.infer_lane(title, description)
    if inferred is JobLane.other and len(mailbox.lanes) == 1:
        try:
            return JobLane(mailbox.lanes[0])
        except ValueError:
            return inferred
    return inferred


def sync_mailbox(db: Session, mailbox: AlertMailbox) -> dict:
    started_at = datetime.now(timezone.utc)
    status, error = "success", None
    fetched = extracted_total = inserted_total = 0

    try:
        messages, current_validity = imap_client.fetch_messages(
            credentials_for(mailbox),
            since_uid=mailbox.last_seen_uid,
            uid_validity=mailbox.uid_validity,
            lookback_days=settings.EMAIL_SYNC_LOOKBACK_DAYS,
        )
        fetched = len(messages)

        for message in messages:
            provider = detect_provider(message.sender)
            if provider is None:
                # Not from a configured job-alert sender. The mailbox is the
                # operator's, so it carries ordinary mail too — spending an AI
                # call on a receipt would be waste, and might invent a "job".
                continue

            clean_text = aggregation.strip_html(message.body)
            try:
                postings = extract_jobs_from_email(clean_text)
            except AIResponseError as e:
                # One unparseable email must not abandon the rest of the mailbox.
                logger.warning("Extraction failed for a message in %s: %s", mailbox.email_address, e)
                continue

            for posting in postings:
                extracted_total += 1
                url = posting.url or fallback_url(provider, posting.title, posting.company)
                normalized = aggregation.normalize_common(
                    title=posting.title,
                    company=posting.company,
                    url=url,
                    location=posting.location or mailbox.market,
                    description=f"Sourced from a {provider} job-alert email for the {mailbox.market} market.",
                    requirements=[],
                    salary_range=None,
                    source=f"email-{provider}",
                )
                if not normalized:
                    continue
                if db.query(Job.id).filter(Job.source_url == normalized["source_url"]).first():
                    continue

                normalized["market"] = mailbox.market
                normalized["lane"] = _lane_for(mailbox, posting.title, normalized["description"])
                db.add(Job(**normalized))
                inserted_total += 1

        # Advanced only after every message was processed. Moving it earlier
        # would mean a crash mid-loop permanently skipped the rest of the batch.
        if messages:
            mailbox.last_seen_uid = max(m.uid for m in messages)
        mailbox.uid_validity = current_validity
        mailbox.last_synced_at = datetime.now(timezone.utc)
        mailbox.last_error = None
    except ImapError as e:
        status, error = "error", str(e)[:2000]
        mailbox.last_error = error
        logger.error("IMAP sync failed for %s: %s", mailbox.email_address, e)
    except Exception as e:
        # Scheduled runs have no caller to raise to, and one broken mailbox must
        # not stop the others, so the failure is recorded rather than propagated.
        status, error = "error", str(e)[:2000]
        mailbox.last_error = error
        logger.exception("Sync failed for %s", mailbox.email_address)

    db.add(EmailSyncRun(
        mailbox_id=mailbox.id, status=status, fetched_count=fetched, extracted_count=extracted_total,
        inserted_count=inserted_total, error=error, started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    ))
    db.commit()

    return {
        "mailbox": mailbox.email_address,
        "market": mailbox.market,
        "status": status,
        "fetched": fetched,
        "extracted": extracted_total,
        "inserted": inserted_total,
        "error": error,
    }


def sync_all_mailboxes(db: Session) -> list[dict]:
    """Every active mailbox — the scheduled job's entry point."""
    mailboxes = db.query(AlertMailbox).filter(AlertMailbox.is_active.is_(True)).all()
    return [sync_mailbox(db, mailbox) for mailbox in mailboxes]


def known_markets(db: Session) -> list[str]:
    """The markets a user can actually pick, i.e. ones with a live mailbox.

    Offering a country with no mailbox behind it would be a promise of supply
    that does not exist — the user would select it and get an empty feed.
    """
    rows = (
        db.query(AlertMailbox.market)
        .filter(AlertMailbox.is_active.is_(True))
        .distinct()
        .all()
    )
    return sorted(market for (market,) in rows)
