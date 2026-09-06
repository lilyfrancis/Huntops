"""A user's optional Gmail grant, used to send outreach as them.

This module used to be the job supply: each user connected Gmail and we mined
their own alert emails. Supply now comes from admin-owned mailboxes instead
(services/alert_mailboxes.py), because making every user set up their own alert
subscriptions meant an empty product until they did.

What survives is the one thing that genuinely has to be the user's own account:
sending outreach from their address rather than a platform one. It stays
optional — outreach falls back to platform SMTP with the user's address as
Reply-To when there is no connection.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.security import create_oauth_state_token, decode_token, OAuthPurpose, TokenType
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.services import gmail_oauth
from app.services.gmail_tokens import get_valid_access_token  # re-exported for callers

logger = logging.getLogger(__name__)
settings = get_settings()

__all__ = [
    "get_connect_url",
    "resolve_user_id_from_state",
    "handle_oauth_callback",
    "disconnect",
    "get_valid_access_token",
]


def get_connect_url(user: User) -> str:
    state = create_oauth_state_token(user.id, OAuthPurpose.user_inbox)
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
