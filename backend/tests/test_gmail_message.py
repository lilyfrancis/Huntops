import base64

from app.services.gmail_message import detect_provider, extract_sender_and_body


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_detect_provider_matches_known_domains():
    assert detect_provider("LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>") == "linkedin"
    assert detect_provider("Indeed <alert@indeed.com>") == "indeed"
    assert detect_provider("Someone <person@random-company.com>") is None


def test_detect_provider_matches_subdomains():
    assert detect_provider("noreply@mail.linkedin.com") == "linkedin"


def test_extract_sender_and_body_simple_text_message():
    message = {
        "payload": {
            "headers": [{"name": "From", "value": "LinkedIn <jobalerts-noreply@linkedin.com>"}],
            "mimeType": "text/plain",
            "body": {"data": _b64("Senior Engineer role at Acme")},
        }
    }
    sender, body = extract_sender_and_body(message)
    assert "linkedin.com" in sender
    assert body == "Senior Engineer role at Acme"


def test_extract_sender_and_body_multipart_prefers_plain_text():
    message = {
        "payload": {
            "headers": [{"name": "From", "value": "Indeed <alert@indeed.com>"}],
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>HTML version</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("Plain text version")}},
            ],
        }
    }
    sender, body = extract_sender_and_body(message)
    assert body == "Plain text version"


def test_extract_sender_and_body_falls_back_to_html_when_no_plain_text():
    message = {
        "payload": {
            "headers": [{"name": "From", "value": "Glassdoor <no-reply@glassdoor.com>"}],
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>Only HTML here</p>")}},
            ],
        }
    }
    _, body = extract_sender_and_body(message)
    assert "Only HTML here" in body
