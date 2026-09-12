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


def test_the_regional_boards_for_every_live_market_are_recognised():
    """A board missing from the allowlist is silently ignored — the mailbox
    syncs "successfully" and the market's feed stays empty with no error
    anywhere. Each market we open needs its own boards added."""
    cases = {
        # UK
        "Reed <jobalerts@reed.co.uk>": "reed",
        "Totaljobs <alerts@totaljobs.com>": "totaljobs",
        # Canada
        "Job Bank <noreply@jobbank.gc.ca>": "jobbank",
        "Workopolis <alerts@workopolis.com>": "workopolis",
        # Gulf / UAE
        "Bayt.com <alerts@bayt.com>": "bayt",
        "GulfTalent <jobs@gulftalent.com>": "gulftalent",
        "Naukrigulf <alerts@naukrigulf.com>": "naukrigulf",
        # Nigeria
        "Jobberman <alerts@jobberman.com>": "jobberman",
    }
    for sender, expected in cases.items():
        assert detect_provider(sender) == expected, sender


def test_employer_side_mail_on_an_allowed_domain_is_excluded():
    """Boards use the same domain to tell an *employer* that someone applied
    to their posting, or that a sponsored listing renewed. That mail matches
    the allowlist, costs an AI call, and reads enough like a job description
    that the extractor can invent a vacancy from it.

    Found by looking at a real alert mailbox: "New application for Remote
    Sales Executive" and "You sponsored your job" were both arriving from
    indeed.com alongside the genuine alerts.
    """
    assert detect_provider("Indeed <employers-noreply@indeed.com>") is None
    assert detect_provider("Indeed <no-reply@indeed.com>") is None
    # The real alert sender, on a subdomain, still works.
    assert detect_provider("Indeed <donotreply@jobalert.indeed.com>") == "indeed"


def test_the_exclusion_is_case_insensitive():
    assert detect_provider("Indeed <Employers-NoReply@Indeed.com>") is None
