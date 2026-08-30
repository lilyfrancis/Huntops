from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.services import email_bridge
from app.services.ai_client import AIResponseError
from app.services.gmail_oauth import GmailAPIError

router = APIRouter(prefix="/api/integrations/gmail", tags=["integrations"])


@router.get("/connect")
def connect(current_user: User = Depends(require_job_seeker)) -> dict:
    return {"authorization_url": email_bridge.get_connect_url(current_user)}


@router.get("/callback")
def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Hit directly by the browser after the Google consent screen — no
    Authorization header available, so the signed `state` param (minted by
    /connect) is how this recovers which user initiated the flow.

    Returns JSON for now since there's no frontend yet; once one exists this
    should redirect to it instead, carrying success/error as query params.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Google returned an error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        user_id = email_bridge.resolve_user_id_from_state(state)
    except HTTPException:
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired — please try connecting again")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        connection = email_bridge.handle_oauth_callback(db, user, code)
    except GmailAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"connected": True, "label": "HuntOps", "connected_at": connection.connected_at}


@router.get("/status")
def status(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == current_user.id).first()
    if not connection:
        return {"connected": False, "last_synced_at": None}
    return {"connected": True, "last_synced_at": connection.last_synced_at}


@router.delete("", status_code=204)
def disconnect(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> None:
    email_bridge.disconnect(db, current_user)


@router.post("/sync")
def sync_now(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return email_bridge.sync_user(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
