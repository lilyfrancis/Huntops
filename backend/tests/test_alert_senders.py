import base64

from app.services.alert_senders import detect_provider


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_detect_provider_matches_known_domains():
    assert detect_provider("LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>") == "linkedin"
    assert detect_provider("Indeed <alert@indeed.com>") == "indeed"
    assert detect_provider("Someone <person@random-company.com>") is None


def test_detect_provider_matches_subdomains():
    assert detect_provider("noreply@mail.linkedin.com") == "linkedin"


def test_an_unrelated_sender_is_not_a_provider():
    """This is the check that keeps ordinary mail in the operator's mailbox
    from costing an AI call — or being turned into a "job"."""
    assert detect_provider("AWS Billing <billing@aws.amazon.com>") is None
    assert detect_provider("") is None
    assert detect_provider("not an email at all") is None


def test_a_lookalike_domain_is_not_matched():
    """endswith on a bare domain would match notlinkedin.com. The dot matters."""
    assert detect_provider("phish <jobs@notlinkedin.com>") is None
    assert detect_provider("phish <jobs@linkedin.com.evil.example>") is None
