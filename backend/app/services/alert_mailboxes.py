"""The supply side: admin-owned mailboxes that feed everyone's job pool.

The original design had each job seeker connect their own Gmail and mine their
own alerts. That put the hardest step of the product — subscribe to the right
alerts, in the right market, with the right filters — on the least motivated
person in the loop, and it meant a user's feed was empty until they did it.

Here the operator connects a handful of mailboxes instead, one per market, each
subscribed to that country's job alerts. Everything they receive lands in one
shared pool tagged by market, and a user's own preferences decide which slice of
it they see. A user connecting Gmail is now optional and does something else
entirely (sending outreach as themselves — see email_bridge).
"""

import logging
import urllib.parse
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.security import create_oauth_state_token, OAuthPurpose
from app.models.alert_mailbox import AlertMailbox
from app.models.email_sync_run import EmailSyncRun
from app.models.enums import JobLane
from app.models.job import Job
from app.models.user import User
from app.services import aggregation, gmail_oauth
from app.services.ai_client import AIResponseError
from app.services.email_extraction import extract_jobs_from_email
from app.services.gmail_message import detect_provider, extract_sender_and_body
from app.services.gmail_tokens import get_valid_access_token

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


# ---------- connecting ----------

def get_connect_url(admin: User, *, market: str, label: str | None, lanes: list[str]) -> str:
    """Start the consent flow, carrying the admin's choices in the signed state."""
    state = create_oauth_state_token(
        admin.id, OAuthPurpose.admin_mailbox, market=market, label=label, lanes=lanes
    )
    return gmail_oauth.build_authorization_url(state, gmail_oauth.MAILBOX_SCOPES)


def connect_from_oauth_code(
    db: Session, *, code: str, admin_id, market: str, label: str | None, lanes: list[str] | None
) -> AlertMailbox:
    """Finish the admin OAuth flow and store (or refresh) the mailbox."""
    tokens = gmail_oauth.exchange_code_for_tokens(code)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)

    email_address = gmail_oauth.get_profile_email(access_token)
    mailbox = db.query(AlertMailbox).filter(AlertMailbox.email_address == email_address).first()

    if mailbox is None:
        if not refresh_token:
            # Google only issues a refresh token on first consent (prompt=consent
            # should always force one), and without it the mailbox would work
            # today and silently stop syncing in an hour.
            raise gmail_oauth.GmailAPIError(
                "Google did not return a refresh token. Remove this app's access in the "
                "mailbox's Google Account settings and connect it again."
            )
        mailbox = AlertMailbox(
            email_address=email_address,
            label=label or email_address,
            market=market,
            lanes=lanes or [],
            access_token_encrypted=encrypt(access_token),
            refresh_token_encrypted=encrypt(refresh_token),
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            connected_by_id=admin_id,
        )
        db.add(mailbox)
    else:
        # Re-running the flow for an existing mailbox is how an admin repairs a
        # revoked grant, so it refreshes credentials rather than erroring.
        mailbox.access_token_encrypted = encrypt(access_token)
        if refresh_token:
            mailbox.refresh_token_encrypted = encrypt(refresh_token)
        mailbox.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        mailbox.market = market
        if label:
            mailbox.label = label
        if lanes is not None:
            mailbox.lanes = lanes
        mailbox.is_active = True
        mailbox.last_error = None

    mailbox.label_id = gmail_oauth.ensure_label(access_token, settings.GMAIL_LABEL_NAME)

    unfiltered = [
        domain
        for domain in settings.email_alert_sender_domains_list
        if not gmail_oauth.ensure_filter(access_token, domain, mailbox.label_id)
    ]
    if unfiltered:
        # Without filters nothing lands under the label, so the mailbox really
        # will ingest zero jobs — surfacing it as an error is correct, and the
        # message has to say what to do rather than just that something broke.
        # The usual cause is connecting without gmail.settings.basic, which is
        # a legitimate choice: it is a restricted scope, and doing this by hand
        # once per mailbox avoids having to justify it to Google.
        mailbox.last_error = (
            f"Could not create routing filters for: {', '.join(unfiltered)}. "
            f"In this mailbox's Gmail settings, add a filter for mail from each of those "
            f"domains that applies the \"{settings.GMAIL_LABEL_NAME}\" label. "
            f"Until then this mailbox will find no jobs."
        )
    else:
        mailbox.last_error = None

    db.commit()
    db.refresh(mailbox)
    return mailbox


def disconnect(db: Session, mailbox: AlertMailbox) -> None:
    """Revoke at Google, then drop the row.

    Revoking first means that if the delete somehow fails we are left with a
    dead row rather than a live grant we have lost the handle on.
    """
    try:
        gmail_oauth.revoke_token(decrypt(mailbox.refresh_token_encrypted))
    except gmail_oauth.GmailAPIError as e:
        # An already-revoked grant returns an error; that is the state we wanted.
        logger.warning("Revoking mailbox %s failed (continuing to delete): %s", mailbox.email_address, e)
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
        access_token = get_valid_access_token(db, mailbox)
        message_ids = gmail_oauth.list_message_ids(
            access_token, mailbox.label_id, settings.EMAIL_SYNC_QUERY_WINDOW
        )
        fetched = len(message_ids)

        for message_id in message_ids:
            message = gmail_oauth.get_message(access_token, message_id)
            sender, body = extract_sender_and_body(message)
            provider = detect_provider(sender) or "unknown"
            clean_text = aggregation.strip_html(body)

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

        mailbox.last_synced_at = datetime.now(timezone.utc)
        mailbox.last_error = None
    except Exception as e:
        # Scheduled runs have no caller to raise to, and one broken mailbox must
        # not stop the others, so the failure is recorded rather than propagated.
        status, error = "error", str(e)[:2000]
        mailbox.last_error = error
        logger.error("Mailbox sync failed for %s: %s", mailbox.email_address, e)

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
