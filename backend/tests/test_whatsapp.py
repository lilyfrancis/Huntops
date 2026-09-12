"""WhatsApp digest delivery."""

from unittest.mock import MagicMock, patch

from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.services import digest, whatsapp
from tests.conftest import auth_headers, register_user


# ---------- phone numbers ----------

def test_numbers_people_actually_type_are_normalised():
    assert whatsapp.normalise_number("+234 803-123-4567") == "+2348031234567"
    assert whatsapp.normalise_number("+234 (803) 123 4567") == "+2348031234567"
    assert whatsapp.normalise_number("002348031234567") == "+2348031234567"


def test_a_number_without_a_country_code_is_refused():
    """The API silently fails on these, so a stored one is found broken at
    07:30 rather than at entry."""
    assert whatsapp.normalise_number("08031234567") is None
    assert whatsapp.normalise_number("803 123 4567") is None
    assert whatsapp.normalise_number("not a number") is None
    assert whatsapp.normalise_number("") is None
    assert whatsapp.normalise_number(None) is None


def test_saving_a_bad_number_is_rejected_with_a_useful_message(client):
    data = register_user(client, email="badnum@example.com")
    resp = client.put(
        "/api/users/profile", json={"whatsapp_number": "08031234567"},
        headers=auth_headers(data["access_token"]),
    )
    assert resp.status_code == 422
    assert "country code" in resp.json()["detail"]


def test_saving_a_good_number_stores_it_normalised(client):
    data = register_user(client, email="goodnum@example.com")
    resp = client.put(
        "/api/users/profile", json={"whatsapp_number": "+234 803 123 4567"},
        headers=auth_headers(data["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["whatsapp_number"] == "+2348031234567"


def test_clearing_the_number_is_allowed(client):
    data = register_user(client, email="clearnum@example.com")
    headers = auth_headers(data["access_token"])
    client.put("/api/users/profile", json={"whatsapp_number": "+2348031234567"}, headers=headers)

    resp = client.put("/api/users/profile", json={"whatsapp_number": ""}, headers=headers)
    assert resp.json()["whatsapp_number"] is None


# ---------- the message ----------

def _match(title="Growth Lead", company="Shopify", score=91):
    job = Job(
        title=title, description="d", requirements=[], location="Toronto",
        job_type="full_time", experience_level="mid", source="internal",
        source_url=f"https://example.com/{title}", company_name=company,
    )
    return (JobMatch(user_id=None, job_id=None, fit_score=score), job)


def test_no_matches_sends_nothing_at_all():
    """A daily "nothing today" email is ignorable. The same on WhatsApp gets
    the number blocked, and a block is permanent."""
    user = User(email="x@example.com", password_hash="x", full_name="Amara Obi", role="job_seeker")
    assert digest.format_digest_whatsapp(user, []) is None


def test_the_template_parameters_are_in_order():
    user = User(email="x@example.com", password_hash="x", full_name="Amara Obi", role="job_seeker")
    params = digest.format_digest_whatsapp(user, [_match(), _match("Ops Lead")])

    assert params[0] == "Amara"       # first name
    assert params[1] == "2"           # count
    assert "Growth Lead at Shopify" in params[2]


def test_newlines_and_double_spaces_are_stripped_from_parameters():
    """Meta rejects a parameter containing either, and job titles arrive from
    job boards with both."""
    user = User(email="x@example.com", password_hash="x", full_name="Amara", role="job_seeker")
    params = digest.format_digest_whatsapp(user, [_match(title="Growth\n  Lead")])

    assert "\n" not in params[2]
    assert "  " not in params[2]


def test_a_user_with_no_name_still_gets_a_greeting():
    user = User(email="x@example.com", password_hash="x", full_name="   ", role="job_seeker")
    assert digest.format_digest_whatsapp(user, [_match()])[0] == "there"


# ---------- sending ----------

def test_nothing_is_sent_when_whatsapp_is_not_configured(monkeypatch):
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    with patch("app.services.whatsapp.httpx.post") as mock_post:
        assert whatsapp.send_template(to="+2348031234567", params=["a"]) is False
    mock_post.assert_not_called()


def test_a_rejected_message_returns_false_rather_than_raising(monkeypatch):
    """One unreachable number must not abandon everyone else's digest."""
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_ACCESS_TOKEN", "t")
    with patch("app.services.whatsapp.httpx.post",
               return_value=MagicMock(status_code=400, text='{"error":{"message":"template not found"}}')):
        assert whatsapp.send_template(to="+2348031234567", params=["a"]) is False


def test_a_successful_send_posts_a_template_not_free_text(monkeypatch):
    """Business-initiated messages can only be templates — free text is
    rejected outside a 24-hour user-initiated window."""
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_ACCESS_TOKEN", "t")
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_TEMPLATE_NAME", "huntops_daily_digest")

    with patch("app.services.whatsapp.httpx.post", return_value=MagicMock(status_code=200)) as mock_post:
        assert whatsapp.send_template(to="+234 803 123 4567", params=["Amara", "3", "Growth Lead"]) is True

    body = mock_post.call_args.kwargs["json"]
    assert body["type"] == "template"
    assert body["template"]["name"] == "huntops_daily_digest"
    assert body["to"] == "2348031234567"  # no leading +
    assert [p["text"] for p in body["template"]["components"][0]["parameters"]] == ["Amara", "3", "Growth Lead"]
