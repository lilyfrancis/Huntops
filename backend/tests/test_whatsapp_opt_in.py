"""The opt-in, and the webhook that is the only evidence of it.

Meta drops a marketing template to anyone who has never messaged the business:
the send is accepted with a 200 and `message_status: accepted`, and nothing
arrives. There is no error on the sending side at all, which is why the digest
went quiet every morning without anybody noticing. These cover the two halves
of the fix — recording that somebody messaged us, and refusing to pretend a
send succeeded when it cannot.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models.user import User
from tests.conftest import auth_headers, register_user

settings = get_settings()


def _signed(client, payload: dict, *, secret: str | None = None):
    raw = json.dumps(payload).encode()
    signature = hmac.new((secret or settings.WHATSAPP_APP_SECRET).encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/api/whatsapp/webhook",
        content=raw,
        headers={"x-hub-signature-256": f"sha256={signature}", "content-type": "application/json"},
    )


def _inbound(number: str) -> dict:
    """What Meta posts when somebody messages the business number."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": number.lstrip("+")}],
                    # Meta reports the sender without a leading +.
                    "messages": [{"from": number.lstrip("+"), "id": "wamid.X", "type": "text",
                                  "text": {"body": "START"}}],
                },
            }],
        }],
    }


def _status(number: str, state: str, *, code: int | None = None) -> dict:
    status: dict = {"id": "wamid.X", "status": state, "recipient_id": number.lstrip("+")}
    if code is not None:
        status["errors"] = [{
            "code": code,
            "title": "Message undeliverable",
            "error_data": {"details": "not delivered to maintain healthy ecosystem engagement"},
        }]
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {"statuses": [status]}}]}],
    }


def _set_number(user_id, number: str) -> None:
    session = SessionLocal()
    try:
        user = session.get(User, uuid.UUID(user_id))
        user.whatsapp_number = number
        session.commit()
    finally:
        session.close()


def _reload(user_id) -> User:
    session = SessionLocal()
    try:
        user = session.get(User, uuid.UUID(user_id))
        session.refresh(user)
        session.expunge(user)
        return user
    finally:
        session.close()


# ---------- the webhook ----------

def test_meta_verifies_the_url_by_echoing_the_challenge(client, monkeypatch):
    """Meta's handshake wants the challenge as plain text. A JSON-wrapped body
    fails the check without saying why."""
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "the-token")

    resp = client.get("/api/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "the-token", "hub.challenge": "12345",
    })

    assert resp.status_code == 200
    assert resp.text == "12345"


def test_verification_with_the_wrong_token_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "the-token")

    resp = client.get("/api/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "guessed", "hub.challenge": "12345",
    })

    assert resp.status_code == 403


def test_an_unsigned_delivery_is_refused(client, monkeypatch):
    """This endpoint marks accounts as reachable. An unsigned caller could
    mark any number they liked."""
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")

    resp = client.post("/api/whatsapp/webhook", json=_inbound("+2348031234567"))

    assert resp.status_code == 400


def test_a_forged_signature_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")

    resp = _signed(client, _inbound("+2348031234567"), secret="wrong-secret")

    assert resp.status_code == 400


def test_the_webhook_refuses_everything_when_no_secret_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "")

    resp = client.post("/api/whatsapp/webhook", json=_inbound("+2348031234567"))

    assert resp.status_code == 503


# ---------- what the webhook records ----------

def test_an_inbound_message_records_the_opt_in(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")
    data = register_user(client, email="optin@example.com")
    _set_number(data["user"]["id"], "+2348031234567")

    assert _signed(client, _inbound("+2348031234567")).status_code == 200

    assert _reload(data["user"]["id"]).whatsapp_opted_in_at is not None


def test_the_opt_in_time_is_not_moved_by_later_messages(client, monkeypatch):
    """It records when they first reached us. Overwriting it on every message
    would turn a fact about consent into a last-seen timestamp."""
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")
    data = register_user(client, email="optin-twice@example.com")
    _set_number(data["user"]["id"], "+2348031234568")

    _signed(client, _inbound("+2348031234568"))
    first = _reload(data["user"]["id"]).whatsapp_opted_in_at
    _signed(client, _inbound("+2348031234568"))

    assert _reload(data["user"]["id"]).whatsapp_opted_in_at == first


def test_a_message_from_a_stranger_is_accepted_and_ignored(client, monkeypatch):
    """Somebody messaging the business who is not a user, or who saved a
    different number than they messaged from. Answering anything but 200 makes
    Meta retry for days and eventually unsubscribe the URL."""
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")

    assert _signed(client, _inbound("+2349990000000")).status_code == 200


def test_a_delivery_failure_is_accepted_rather_than_retried(client, monkeypatch):
    """131049 is the marketing drop — the one that looks like success
    everywhere else in the system."""
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")

    resp = _signed(client, _status("+2348031234567", "failed", code=131049))

    assert resp.status_code == 200


def test_a_payload_with_nothing_recognisable_is_still_accepted(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "app-secret")

    resp = _signed(client, {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {}}]}]})

    assert resp.status_code == 200


# ---------- what the profile page is told ----------

def test_the_connection_reports_a_number_that_has_not_opted_in(client, monkeypatch):
    """The state the whole feature turns on: a number is saved, so the UI used
    to call it done, while every digest was being dropped."""
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setattr(settings, "WHATSAPP_BUSINESS_NUMBER", "+12268010899")
    data = register_user(client, email="conn@example.com")
    _set_number(data["user"]["id"], "+2348031234569")

    body = client.get("/api/whatsapp/connection", headers=auth_headers(data["access_token"])).json()

    assert body["configured"] is True
    assert body["number_on_file"] == "+2348031234569"
    assert body["opted_in"] is False
    assert body["opt_in_url"] == "https://wa.me/12268010899?text=START"


def test_the_connection_says_unconfigured_when_no_business_number_is_set(client, monkeypatch):
    """Without it there is no link to send anybody, so the UI must not offer
    a button that cannot work."""
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setattr(settings, "WHATSAPP_BUSINESS_NUMBER", "")
    data = register_user(client, email="conn-unset@example.com")

    body = client.get("/api/whatsapp/connection", headers=auth_headers(data["access_token"])).json()

    assert body["configured"] is False
    assert body["opt_in_url"] is None


# ---------- the digest itself ----------

def test_the_digest_does_not_send_to_someone_who_never_opted_in(client, monkeypatch):
    """Sending would be accepted by Meta and dropped, and the run would count
    it as delivered. Not sending reaches the same person and says so."""
    from app.services import scheduler

    data = register_user(client, email="nosend@example.com")
    _set_number(data["user"]["id"], "+2348031234570")
    user = _reload(data["user"]["id"])

    sent = []
    monkeypatch.setattr(scheduler.whatsapp, "send_template", lambda **kw: sent.append(kw) or True)

    assert scheduler._deliver_whatsapp(user, [("match", "job")]) is False
    assert sent == []


def test_the_digest_sends_once_they_have_opted_in(client, monkeypatch):
    from app.services import scheduler

    data = register_user(client, email="dosend@example.com")
    _set_number(data["user"]["id"], "+2348031234571")
    session = SessionLocal()
    try:
        u = session.get(User, uuid.UUID(data["user"]["id"]))
        u.whatsapp_opted_in_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()
    user = _reload(data["user"]["id"])

    sent = []
    monkeypatch.setattr(scheduler.whatsapp, "send_template", lambda **kw: sent.append(kw) or True)
    monkeypatch.setattr(scheduler.digest, "format_digest_whatsapp", lambda *a, **k: ["A", "1", "B"])

    assert scheduler._deliver_whatsapp(user, [("match", "job")]) is True
    assert len(sent) == 1
