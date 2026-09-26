"""Forwarded job alerts, in the two shapes forwarding actually takes.

An operator pointing an existing inbox at an alert mailbox is the obvious way
to get supply on day one, and whether it works at all depends on which kind of
forward they set up — a distinction nothing in the UI explains.
"""

from email import message_from_string

from app.services.alert_senders import detect_provider_anywhere
from app.services.imap_client import extract_sender_and_body, forward_hints

DOMAINS = ["linkedin.com", "indeed.com", "jobberman.com", "bayt.com"]


def _msg(raw: str):
    return message_from_string(raw)


AUTO_FORWARDED = """\
From: LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>
To: alerts-canada@jobquickai.site
X-Forwarded-For: lily@gmail.com alerts-canada@jobquickai.site
X-Forwarded-To: alerts-canada@jobquickai.site
Subject: 8 new jobs for "growth marketer"
Content-Type: text/plain; charset="utf-8"

Growth Marketer at Shopify - Toronto, ON
"""

MANUAL_FORWARD = """\
From: Lily Francis <lily@gmail.com>
To: alerts-canada@jobquickai.site
Subject: Fwd: 8 new jobs for "growth marketer"
Content-Type: text/plain; charset="utf-8"

Sending these over.

---------- Forwarded message ---------
From: LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>
Date: Fri, 19 Sep 2026 at 07:02
Subject: 8 new jobs for "growth marketer"
To: <lily@gmail.com>

Growth Marketer at Shopify - Toronto, ON
"""

OUTLOOK_FORWARD = """\
From: Lily Francis <lily@outlook.com>
To: alerts-uk@jobquickai.site
Subject: FW: New jobs matching your search
Content-Type: text/html; charset="utf-8"

<html><body><p>fyi</p><div id="divRplyFwdMsg">
<b>From:</b> Indeed &lt;alert@indeed.com&gt;<br>
<b>Sent:</b> 19 September 2026 07:02<br>
<b>To:</b> Lily Francis<br>
<b>Subject:</b> New jobs matching your search</div>
<p>Product Manager - London</p></body></html>
"""


def test_automatic_forwarding_is_recognised_because_From_survives():
    """A forwarding rule resends the message with From untouched — which is
    exactly why SPF breaks on forwarded mail, and why this case already
    worked."""
    sender, body = extract_sender_and_body(_msg(AUTO_FORWARDED))
    assert detect_provider_anywhere(sender, DOMAINS, body=body) == "linkedin"


def test_a_manual_forward_is_recognised_from_the_quoted_block():
    """Pressing Forward makes a new message: From is the person, and the
    original is only in the body. This is the case that was silently skipped."""
    msg = _msg(MANUAL_FORWARD)
    sender, body = extract_sender_and_body(msg)

    assert "lily@gmail.com" in sender          # From really is the forwarder
    assert detect_provider_anywhere(
        sender, DOMAINS, hints=forward_hints(msg), body=body) == "linkedin"


def test_an_outlook_style_html_forward_is_recognised_once_stripped():
    """Outlook writes the forwarded header block as HTML, so the sync strips
    the markup before looking — otherwise the address is buried in tags."""
    from app.services import aggregation

    msg = _msg(OUTLOOK_FORWARD)
    sender, body = extract_sender_and_body(msg)
    clean = aggregation.strip_html(body)

    assert detect_provider_anywhere(
        sender, DOMAINS, hints=forward_hints(msg), body=clean) == "indeed"


def test_forwarding_does_not_widen_which_senders_are_accepted():
    """Only where the sender is looked for changes. A forwarded newsletter is
    still not a job alert."""
    raw = MANUAL_FORWARD.replace("jobalerts-noreply@linkedin.com", "news@substack.com")
    msg = _msg(raw)
    sender, body = extract_sender_and_body(msg)

    assert detect_provider_anywhere(
        sender, DOMAINS, hints=forward_hints(msg), body=body) is None


def test_an_excluded_address_stays_excluded_when_forwarded():
    """Employer-side mail is the case that costs an AI call and can invent a
    vacancy. Forwarding it must not become a way around the exclude list."""
    raw = MANUAL_FORWARD.replace(
        "jobalerts-noreply@linkedin.com", "employers-noreply@indeed.com")
    msg = _msg(raw)
    sender, body = extract_sender_and_body(msg)

    assert detect_provider_anywhere(
        sender, DOMAINS, hints=forward_hints(msg), body=body) is None


def test_an_ordinary_reply_chain_is_not_mistaken_for_a_forward():
    """"From:" appears in every quoted reply. Matching one deep in a thread
    would hand the extractor a conversation and let it invent jobs from it."""
    raw = """\
From: Recruiter <person@somecompany.com>
To: alerts-uk@jobquickai.site
Subject: Re: your application
Content-Type: text/plain; charset="utf-8"

Thanks for applying.

> From: Lily Francis <lily@gmail.com>
> I saw the role on your careers page.
"""
    msg = _msg(raw)
    sender, body = extract_sender_and_body(msg)
    assert detect_provider_anywhere(
        sender, DOMAINS, hints=forward_hints(msg), body=body) is None


def test_the_scan_does_not_read_an_unbounded_body():
    """A long digest can quote dozens of headers. Only the top is read, where
    a real forwarded block sits."""
    from app.services.alert_senders import _FORWARD_SCAN_CHARS

    padding = "filler line\n" * 2000
    raw = f"""\
From: Lily Francis <lily@gmail.com>
To: alerts-uk@jobquickai.site
Subject: Fwd: something
Content-Type: text/plain; charset="utf-8"

{padding}
From: LinkedIn <jobalerts-noreply@linkedin.com>
"""
    msg = _msg(raw)
    sender, body = extract_sender_and_body(msg)
    assert len(body) > _FORWARD_SCAN_CHARS
    assert detect_provider_anywhere(
        sender, DOMAINS, hints=forward_hints(msg), body=body) is None
