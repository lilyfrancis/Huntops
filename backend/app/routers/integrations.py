import urllib.parse
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token, require_job_seeker, OAuthPurpose, TokenType
from app.db.base import get_db
from app.models.enums import UserRole
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.services import alert_mailboxes, email_bridge
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


def _admin_redirect(status_value: str, message: str | None = None) -> RedirectResponse:
    params = {"mailbox": status_value}
    if message:
        params["message"] = message
    return _frontend_redirect("/admin/mailboxes", params)


@router.get("/connect")
def connect(current_user: User = Depends(require_job_seeker)) -> dict:
    """Optional: connect your own Gmail so outreach sends from your address.

    This no longer has anything to do with the job feed — that comes from the
    operator's central alert mailboxes whether or not you connect anything.
    """
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
    recovers who started the flow and which of the two flows it was.

    Redirects back into the app with the outcome as a query param rather
    than returning JSON, since a browser lands here directly.
    """
    if error:
        return _seeker_redirect("error", f"Google returned an error: {error}")
    if not code or not state:
        return _seeker_redirect("error", "Missing code or state")

    try:
        payload = decode_token(state, TokenType.oauth_state)
    except HTTPException:
        return _seeker_redirect("error", "OAuth state is invalid or expired — please try connecting again")

    purpose = payload.get("purpose", OAuthPurpose.user_inbox.value)
    redirect = _admin_redirect if purpose == OAuthPurpose.admin_mailbox.value else _seeker_redirect

    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (ValueError, TypeError, KeyError):
        user = None
    if not user:
        return redirect("error", "User not found")

    if purpose == OAuthPurpose.admin_mailbox.value:
        # Re-checked here, not just at /connect: the state is minted before the
        # consent screen, and an admin demoted in between must not still be able
        # to attach a mailbox to everyone's feed.
        if user.role != UserRole.admin:
            return redirect("error", "Only an admin can connect an alert mailbox")
        try:
            alert_mailboxes.connect_from_oauth_code(
                db,
                code=code,
                admin_id=user.id,
                market=payload.get("market", ""),
                label=payload.get("label"),
                lanes=payload.get("lanes") or [],
            )
        except GmailAPIError as e:
            return redirect("error", str(e))
        return redirect("connected")

    try:
        email_bridge.handle_oauth_callback(db, user, code)
    except GmailAPIError as e:
        return redirect("error", str(e))
    return redirect("connected")


@router.get("/status")
def status(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == current_user.id).first()
    if not connection:
        return {"connected": False, "connected_at": None}
    return {"connected": True, "connected_at": connection.connected_at}


@router.delete("", status_code=204)
def disconnect(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> None:
    email_bridge.disconnect(db, current_user)
