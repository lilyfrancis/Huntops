import urllib.parse
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token, require_job_seeker, TokenType
from app.db.base import get_db
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.services import email_bridge
from app.services.gmail_oauth import GmailAPIError

router = APIRouter(prefix="/api/integrations/gmail", tags=["integrations"])
settings = get_settings()


def _frontend_redirect(path: str, params: dict) -> RedirectResponse:
    return RedirectResponse(f"{settings.FRONTEND_URL}{path}?{urllib.parse.urlencode(params)}")


def _seeker_redirect(status_value: str, message: str | None = None) -> RedirectResponse:
    params = {"gmail": status_value}
    if message:
        params["message"] = message
    return _frontend_redirect("/app/integrations", params)


@router.get("/connect")
def connect(current_user: User = Depends(require_job_seeker)) -> dict:
    """Optional: connect your own Gmail so outreach sends from your address.

    This has nothing to do with the job feed — that comes from the operator's
    central alert mailboxes whether or not you connect anything.
    """
    if not settings.ENABLE_USER_GMAIL_CONNECT:
        # Refused rather than attempted: with an Internal OAuth client, Google
        # blocks consent for anyone outside our Workspace, so starting the flow
        # would only hand the user an access-denied screen with no explanation.
        raise HTTPException(
            status_code=404,
            detail="Connecting your own Gmail isn't available. Outreach is sent on your behalf "
                   "with your address as the reply-to, so replies still reach you.",
        )
    return {"authorization_url": email_bridge.get_connect_url(current_user)}


@router.get("/callback")
def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Hit directly by the browser after the Google consent screen — no
    Authorization header available, so the signed `state` param is how this
    recovers who started the flow.

    Only serves the optional send-as-your-Gmail flow. Alert mailboxes are read
    over IMAP and never touch OAuth.
    """
    if error:
        return _seeker_redirect("error", f"Google returned an error: {error}")
    if not code or not state:
        return _seeker_redirect("error", "Missing code or state")

    try:
        payload = decode_token(state, TokenType.oauth_state)
    except HTTPException:
        return _seeker_redirect("error", "OAuth state is invalid or expired — please try connecting again")

    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (ValueError, TypeError, KeyError):
        user = None
    if not user:
        return _seeker_redirect("error", "User not found")

    try:
        email_bridge.handle_oauth_callback(db, user, code)
    except GmailAPIError as e:
        return _seeker_redirect("error", str(e))
    return _seeker_redirect("connected")


@router.get("/status")
def status(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == current_user.id).first()
    # `available` is separate from `connected` so the UI can explain an absent
    # feature instead of rendering a button that 404s. A user who connected
    # before the feature was switched off still sees their connection, and can
    # still disconnect it.
    return {
        "available": settings.ENABLE_USER_GMAIL_CONNECT,
        "connected": connection is not None,
        "connected_at": connection.connected_at if connection else None,
    }


@router.delete("", status_code=204)
def disconnect(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> None:
    email_bridge.disconnect(db, current_user)
