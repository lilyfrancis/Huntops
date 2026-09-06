"""Access-token refresh shared by both kinds of Gmail grant.

A user's own inbox connection and an admin-owned alert mailbox store the same
three fields and need the same refresh-if-nearly-expired logic. This is
duck-typed on those field names rather than tied to either model, so the two
can't drift into two subtly different refresh rules.
"""

from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.services import gmail_oauth

# Refresh this far ahead of expiry, so a token can't lapse mid-sync between
# the check and the call that uses it.
REFRESH_MARGIN = timedelta(minutes=2)


class TokenHolder(Protocol):
    access_token_encrypted: str
    refresh_token_encrypted: str
    token_expires_at: datetime


def as_aware_utc(dt: datetime) -> datetime:
    """SQLite doesn't round-trip tz-aware datetimes — a value that was stored
    aware can come back naive after a flush/refresh. Postgres doesn't have
    this problem, but comparing against `datetime.now(timezone.utc)` isn't
    safe unless both sides are guaranteed aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def get_valid_access_token(db: Session, holder: TokenHolder) -> str:
    if as_aware_utc(holder.token_expires_at) > datetime.now(timezone.utc) + REFRESH_MARGIN:
        return decrypt(holder.access_token_encrypted)

    tokens = gmail_oauth.refresh_access_token(decrypt(holder.refresh_token_encrypted))
    access_token = tokens["access_token"]
    holder.access_token_encrypted = encrypt(access_token)
    holder.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
    db.commit()
    return access_token
