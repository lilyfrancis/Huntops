"""Meta's webhook, and the connection state the profile page shows.

Two things were invisible before this existed, and both of them failed
silently every morning:

1. Whether a user has ever messaged the business number. Meta drops marketing
   templates to people who have not, accepting the send with a 200 and
   delivering nothing. Without this, a digest to somebody who never opted in
   vanishes and the product reports success.

2. Whether a message that Meta accepted was actually delivered. `accepted`
   means queued. The real outcome — delivered, read, or failed with a reason
   — arrives only here.
"""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.whatsapp import WhatsAppConnectionOut
from app.services import whatsapp

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/connection", response_model=WhatsAppConnectionOut)
def connection(current_user: User = Depends(get_current_user)) -> WhatsAppConnectionOut:
    """What the profile page needs to explain the state of this user's WhatsApp.

    `opted_in` is the load-bearing one: with a number saved but no opt-in, the
    digest is sent, accepted, and silently dropped — which from the user's
    side is indistinguishable from the feature not existing.
    """
    return WhatsAppConnectionOut(
        configured=whatsapp.is_configured() and whatsapp.business_number() is not None,
        business_number=whatsapp.business_number(),
        opt_in_url=whatsapp.opt_in_url(),
        number_on_file=current_user.whatsapp_number,
        opted_in=current_user.whatsapp_opted_in_at is not None,
        opted_in_at=current_user.whatsapp_opted_in_at,
    )


@router.get("/webhook")
def verify_webhook(request: Request) -> Response:
    """Meta's one-time handshake when the URL is saved in its console.

    It sends the token that was typed in alongside the URL and expects
    `hub.challenge` echoed back as plain text — a JSON-wrapped body fails the
    check with no explanation of why.
    """
    params = request.query_params
    if not settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        logger.error("WhatsApp webhook verification attempted but WHATSAPP_WEBHOOK_VERIFY_TOKEN is unset")
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured")

    if params.get("hub.mode") != "subscribe" or not hmac.compare_digest(
        params.get("hub.verify_token", ""), settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    ):
        raise HTTPException(status_code=403, detail="Verification failed")

    return Response(content=params.get("hub.challenge", ""), media_type="text/plain")


@router.post("/webhook", status_code=200)
async def receive_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Inbound messages and delivery statuses.

    Always answers 200 once the signature checks out, including for payloads
    this does not understand. Meta retries anything else for days and, after
    enough failures, unsubscribes the URL — losing every future opt-in to
    punish one malformed event.
    """
    raw = await request.body()

    if not settings.WHATSAPP_APP_SECRET:
        # Nothing can be verified, so nothing may be trusted: this endpoint
        # marks accounts as reachable, and an unsigned caller could mark any
        # number they liked.
        logger.error("WhatsApp webhook received but WHATSAPP_APP_SECRET is unset — rejecting")
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured")

    signature = request.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(settings.WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    # compare_digest, not ==: a short-circuiting comparison leaks how much of a
    # forged signature was right, one byte at a time.
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            _record_opt_ins(db, value.get("messages") or [])
            _log_statuses(value.get("statuses") or [])

    db.commit()
    return {"received": True}


def _record_opt_ins(db: Session, messages: list) -> None:
    """An inbound message is the opt-in — the only evidence that holds.

    Matched on the sender's number rather than on anything in the message, so
    it works whether they tapped the prefilled link or simply typed "hi".
    """
    from datetime import datetime, timezone

    for message in messages:
        sender = message.get("from")
        if not sender:
            continue
        # Meta reports wa_id without a leading +; ours are stored E.164.
        number = whatsapp.normalise_number(sender if sender.startswith("+") else f"+{sender}")
        if number is None:
            continue

        user = db.query(User).filter(User.whatsapp_number == number).first()
        if user is None:
            # Somebody messaging the business who is not a user, or who saved a
            # different number than they messaged from. Worth a line: "I did
            # message you" with nothing recorded is otherwise unexplainable.
            logger.info("WhatsApp message from %s matches no user", number)
            continue
        if user.whatsapp_opted_in_at is None:
            user.whatsapp_opted_in_at = datetime.now(timezone.utc)
            logger.info("WhatsApp opt-in recorded for user=%s", user.id)


def _log_statuses(statuses: list) -> None:
    """Delivery outcomes, which exist nowhere else.

    A failure here is the difference between "Meta accepted it" and "it
    arrived", and 131049 in particular — the marketing drop — is the one that
    looks like success everywhere else in the system.
    """
    for status in statuses:
        state = status.get("status")
        recipient = status.get("recipient_id")
        if state == "failed":
            errors = status.get("errors") or [{}]
            first = errors[0]
            logger.error(
                "WhatsApp delivery failed to %s: %s %s — %s",
                recipient,
                first.get("code"),
                first.get("title"),
                (first.get("error_data") or {}).get("details", ""),
            )
        else:
            logger.info("WhatsApp %s to %s", state, recipient)
