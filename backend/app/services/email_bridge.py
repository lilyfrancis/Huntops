"""Per-user Gmail sync — the multi-tenant version of Job Engine's Phase 2.

Job Engine ran this against one hand-configured mailbox with manually-created
Gmail filters. Here, connecting an account programmatically creates the label
and filters via the Gmail API (no manual setup step), and every step below is
scoped to one user's tokens instead of a single shared inbox.
"""

import logging
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.security import create_oauth_state_token, decode_token, TokenType
from app.models.email_sync_run import EmailSyncRun
from app.models.gmail_connection import GmailConnection
from app.models.job import Job
from app.models.user import User
from app.services import aggregation, gmail_oauth
from app.services.ai_client import AIResponseError
from app.services.email_extraction import extract_jobs_from_email
from app.services.gmail_message import detect_provider, extract_sender_and_body

logger = logging.getLogger(__name__)
settings = get_settings()

_FALLBACK_SEARCH_TEMPLATES = {
    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={q}",
    "indeed": "https://www.indeed.com/jobs?q={q}",
    "glassdoor": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}",
}


def _fallback_url(provider: str, title: str, company: str) -> str:
    query = urllib.parse.quote(f"{title} {company}".strip())
    template = _FALLBACK_SEARCH_TEMPLATES.get(provider, _FALLBACK_SEARCH_TEMPLATES["linkedin"])
    return template.format(q=query)


def get_connect_url(user: User) -> str:
    state = create_oauth_state_token(user.id)
    return gmail_oauth.build_authorization_url(state)


def resolve_user_id_from_state(state: str) -> uuid.UUID:
    payload = decode_token(state, TokenType.oauth_state)
    return uuid.UUID(payload["sub"])


def handle_oauth_callback(db: Session, user: User, code: str) -> GmailConnection:
    tokens = gmail_oauth.exchange_code_for_tokens(code)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)

    connection = db.query(GmailConnection).filter(GmailConnection.user_id == user.id).first()
    if connection is None:
        if not refresh_token:
            # Google only issues a refresh_token on first consent (with prompt=consent
            # this should always happen), but guard against the edge case anyway.
            raise gmail_oauth.GmailAPIError(
                "Google did not return a refresh token. Disconnect any prior grant for "
                "this app in your Google Account and try connecting again."
            )
        connection = GmailConnection(
            user_id=user.id,
            access_token_encrypted=encrypt(access_token),
            refresh_token_encrypted=encrypt(refresh_token),
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )
        db.add(connection)
    else:
        connection.access_token_encrypted = encrypt(access_token)
        if refresh_token:
            connection.refresh_token_encrypted = encrypt(refresh_token)
        connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    label_id = gmail_oauth.ensure_label(access_token, settings.GMAIL_LABEL_NAME)
    connection.label_id = label_id
    for domain in settings.email_alert_sender_domains_list:
        gmail_oauth.ensure_filter(access_token, domain, label_id)

    db.commit()
    db.refresh(connection)
    return connection


def disconnect(db: Session, user: User) -> None:
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == user.id).first()
    if connection is None:
        return
    gmail_oauth.revoke_token(decrypt(connection.refresh_token_encrypted))
    db.delete(connection)
    db.commit()


def _as_aware_utc(dt: datetime) -> datetime:
    """SQLite doesn't round-trip tz-aware datetimes — a value that was stored
    aware can come back naive after a flush/refresh. Postgres doesn't have
    this problem, but comparing against `datetime.now(timezone.utc)` isn't
    safe unless both sides are guaranteed aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _get_valid_access_token(db: Session, connection: GmailConnection) -> str:
    if _as_aware_utc(connection.token_expires_at) > datetime.now(timezone.utc) + timedelta(minutes=2):
        return decrypt(connection.access_token_encrypted)

    refresh_token = decrypt(connection.refresh_token_encrypted)
    tokens = gmail_oauth.refresh_access_token(refresh_token)
    access_token = tokens["access_token"]
    expires_in = tokens.get("expires_in", 3600)

    connection.access_token_encrypted = encrypt(access_token)
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    db.commit()
    return access_token


def sync_user(db: Session, user: User) -> dict:
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == user.id).first()
    if connection is None:
        raise ValueError("Gmail is not connected for this user")

    started_at = datetime.now(timezone.utc)
    status, error = "success", None
    fetched = extracted_total = inserted_total = 0

    try:
        access_token = _get_valid_access_token(db, connection)
        message_ids = gmail_oauth.list_message_ids(
            access_token, connection.label_id, settings.EMAIL_SYNC_QUERY_WINDOW
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
                logger.warning("Email extraction failed for one message (user=%s): %s", user.id, e)
                continue

            for posting in postings:
                extracted_total += 1
                url = posting.url or _fallback_url(provider, posting.title, posting.company)
                normalized = aggregation.normalize_common(
                    title=posting.title,
                    company=posting.company,
                    url=url,
                    location=posting.location or "Not specified",
                    description=f"Sourced from a {provider} job-alert email.",
                    requirements=[],
                    salary_range=None,
                    source=f"email-{provider}",
                )
                if not normalized:
                    continue
                if db.query(Job.id).filter(Job.source_url == normalized["source_url"]).first():
                    continue
                db.add(Job(**normalized))
                inserted_total += 1

        connection.last_synced_at = datetime.now(timezone.utc)
    except Exception as e:
        status, error = "error", str(e)[:2000]
        logger.error("Email sync failed for user=%s: %s", user.id, e)

    db.add(EmailSyncRun(
        user_id=user.id, status=status, fetched_count=fetched, extracted_count=extracted_total,
        inserted_count=inserted_total, error=error, started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    ))
    db.commit()

    return {"status": status, "fetched": fetched, "extracted": extracted_total, "inserted": inserted_total, "error": error}


def sync_all_connected_users(db: Session) -> dict:
    """Iterate every user with a Gmail connection — the scheduled job's entry point."""
    connections = db.query(GmailConnection).all()
    summary = {}
    for connection in connections:
        user = db.get(User, connection.user_id)
        if user is None or user.is_suspended:
            continue
        summary[str(user.id)] = sync_user(db, user)
    return summary
