"""Live checks for the third-party integrations.

The health endpoint could only report whether a key was a non-empty string,
which is not the question anyone is asking. A wrong Anthropic key, an Apollo
key without master scope, SMTP credentials that were rotated — all look
identical to a working setup until a user hits the feature and it fails
quietly in a log nobody reads.

Each check here makes a real call, as cheap as the provider allows, and
returns something an operator can act on rather than a stack trace.
"""

import logging
import smtplib
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

HTTP_TIMEOUT = 20.0


@dataclass
class CheckResult:
    name: str
    configured: bool
    ok: bool | None  # None when there is nothing configured to test
    detail: str


def _unconfigured(name: str, what: str) -> CheckResult:
    return CheckResult(name=name, configured=False, ok=None, detail=f"Not configured — {what}")


def check_anthropic() -> CheckResult:
    """One-token completion on the cheap model. Fractions of a cent."""
    if not settings.ANTHROPIC_API_KEY:
        return _unconfigured("anthropic", "fit scoring, job extraction, interviews and drafting are all off")

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        client.messages.create(
            model=settings.ANTHROPIC_SCORING_MODEL,
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
    except Exception as e:
        return CheckResult("anthropic", True, False, _readable(e))
    return CheckResult("anthropic", True, True, f"Key valid; {settings.ANTHROPIC_SCORING_MODEL} responded")


def check_apollo() -> CheckResult:
    """A people search against a company that certainly exists.

    Uses search, not enrichment: search costs an ordinary API call while
    revealing an email spends a credit, and this only needs to prove the key
    is accepted and has the right scope.
    """
    if not settings.APOLLO_API_KEY:
        return _unconfigured("apollo", "outreach still drafts, but finds no hiring contact to send it to")

    try:
        resp = httpx.post(
            "https://api.apollo.io/api/v1/mixed_people/api_search",
            headers={"X-Api-Key": settings.APOLLO_API_KEY, "Content-Type": "application/json"},
            json={"q_organization_name": "Shopify", "person_titles": ["Recruiter"], "page": 1, "per_page": 1},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return CheckResult("apollo", True, False, f"Could not reach Apollo: {e}")

    if resp.status_code == 401:
        return CheckResult("apollo", True, False, "Key rejected (401). Check it was copied in full.")
    if resp.status_code == 403:
        # The specific trap: people search needs a master key, and a normal one
        # fails here while working fine elsewhere.
        return CheckResult(
            "apollo", True, False,
            "Forbidden (403) — people search needs a **master** API key. "
            "Create one under Settings → Integrations → API in Apollo.",
        )
    if resp.status_code >= 400:
        return CheckResult("apollo", True, False, f"Apollo returned {resp.status_code}: {resp.text[:200]}")

    found = len(resp.json().get("people", []))
    return CheckResult("apollo", True, True, f"Key valid; search returned {found} result(s)")


def check_smtp() -> CheckResult:
    """Connect and log in. Deliberately does not send: proving the credentials
    work is the question, and a test email to a real inbox on every click is
    a nuisance."""
    if not settings.SMTP_HOST:
        return _unconfigured("smtp", "the daily digest and outreach fall back to nothing and fail silently")

    from app.services.notifications import open_smtp

    try:
        with open_smtp():
            pass
    except smtplib.SMTPAuthenticationError:
        return CheckResult("smtp", True, False, "Server reachable but the username or password was rejected")
    except (smtplib.SMTPException, OSError) as e:
        detail = f"Could not connect to {settings.SMTP_HOST}:{settings.SMTP_PORT} — {e}"
        if settings.SMTP_PORT not in (465, 587, 25) and settings.SMTP_USE_SSL is None:
            # The two standard submission ports behave differently and a third
            # number is usually a typo or a port meant for something else.
            detail += ". Submission is normally 587 (STARTTLS) or 465 (TLS)."
        return CheckResult("smtp", True, False, detail)
    return CheckResult("smtp", True, True, f"Connected and authenticated to {settings.SMTP_HOST}")


def check_paystack() -> CheckResult:
    """Lists plans, which proves the key *and* that the configured plan codes
    exist — a typo there takes payment for a plan nobody can buy."""
    if not settings.PAYSTACK_SECRET_KEY:
        return _unconfigured("paystack", "nobody can subscribe to a paid tier")

    try:
        resp = httpx.get(
            "https://api.paystack.co/plan",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            params={"perPage": 100},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return CheckResult("paystack", True, False, f"Could not reach Paystack: {e}")

    if resp.status_code == 401:
        return CheckResult("paystack", True, False, "Key rejected (401). Check it is the secret key, not the public one.")
    if resp.status_code >= 400:
        return CheckResult("paystack", True, False, f"Paystack returned {resp.status_code}: {resp.text[:200]}")

    plans = resp.json().get("data", [])
    codes = {p.get("plan_code") for p in plans}

    # BILLING_CURRENCY only drives what the page *displays*; the card is
    # charged whatever the plan says. Set differently, the site advertises
    # $7,500 and Paystack bills ₦7,500 — and nothing else anywhere notices.
    configured = {settings.PAYSTACK_PLAN_PRO, settings.PAYSTACK_PLAN_ELITE}
    plan_currencies = {
        p.get("currency") for p in plans if p.get("plan_code") in configured and p.get("currency")
    }
    mismatched = plan_currencies - {settings.BILLING_CURRENCY.upper()}

    missing = [
        f"{tier} ({code})"
        for tier, code in (("Pro", settings.PAYSTACK_PLAN_PRO), ("Elite", settings.PAYSTACK_PLAN_ELITE))
        if code and code not in codes
    ]
    if missing:
        return CheckResult(
            "paystack", True, False,
            f"Key valid, but no plan matches: {', '.join(missing)}. Check the codes against the Paystack dashboard.",
        )
    if not (settings.PAYSTACK_PLAN_PRO and settings.PAYSTACK_PLAN_ELITE):
        return CheckResult("paystack", True, False, "Key valid, but PAYSTACK_PLAN_PRO / _ELITE are not set")
    if mismatched:
        return CheckResult(
            "paystack", True, False,
            f"Plans are priced in {', '.join(sorted(mismatched))} but BILLING_CURRENCY is "
            f"{settings.BILLING_CURRENCY}. The site would advertise one currency and charge another.",
        )
    return CheckResult("paystack", True, True, f"Key valid; both plan codes found among {len(codes)} plan(s)")


def _readable(error: Exception) -> str:
    """Provider SDK errors are long and mostly noise; keep the useful part."""
    text = str(error)
    if "authentication_error" in text or "401" in text:
        return "Key rejected. Generate a new one and update ANTHROPIC_API_KEY."
    if "credit balance" in text.lower() or "insufficient" in text.lower():
        return "Key valid but the account has no credit."
    return text[:300]


def check_whatsapp() -> CheckResult:
    """Reads the phone number's own profile — the cheapest authenticated call
    Meta offers, and it sends nothing."""
    from app.services import whatsapp

    if not whatsapp.is_configured():
        return _unconfigured("whatsapp", "the digest goes by email only")

    # Reported on failure. Every WhatsApp misconfiguration so far has been the
    # URL rather than the credentials, and the provider's own errors describe
    # the path they received without saying what was sent — which is how a
    # wrong host reads as a wrong phone number ID.
    url = f"{whatsapp._base()}/{whatsapp.GRAPH_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}"

    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return CheckResult("whatsapp", True, False, f"Could not reach {url}: {e}")

    if resp.status_code == 401:
        return CheckResult("whatsapp", True, False, f"Token rejected by {url}. {_whatsapp_auth_reason(resp)}")
    if resp.status_code >= 400:
        detail = f"Called {url} — got {resp.status_code}: {resp.text[:200]}"
        if "Unknown path components" in resp.text:
            # This one is badly misleading: it names the phone number ID, so
            # it reads as though the ID is wrong, when the actual cause is
            # almost always the host — a version left on WHATSAPP_API_BASE,
            # or an ID issued by a reseller being sent to Meta directly.
            detail += (
                ". The path in that error is the one we sent, so compare it with the URL "
                "above: WHATSAPP_API_BASE must be the host alone, with no /vNN.N and no "
                "path, pointing at whoever issued the phone number ID."
            )
        return CheckResult("whatsapp", True, False, detail)

    data = resp.json()
    number = data.get("display_phone_number", "?")
    quality = data.get("quality_rating")
    detail = f"Connected as {data.get('verified_name', 'unnamed')} ({number})"
    if quality and quality.upper() not in ("GREEN", "UNKNOWN"):
        # A number that gets blocked enough drops to RED and stops delivering
        # entirely, with no error on send.
        detail += f" — quality rating is {quality}, deliverability is at risk"
        return CheckResult("whatsapp", True, False, detail)
    return CheckResult("whatsapp", True, True, f"{detail}. {_check_whatsapp_template()}")


def _whatsapp_auth_reason(resp: httpx.Response) -> str:
    """Meta's own words for why, plus what to do about that specific code.

    A 401 has several quite different causes whose fixes have nothing in
    common: an expired token, a token belonging to another app, and a token
    missing a permission are indistinguishable from the status alone. Naming
    one of them as though it had been diagnosed sends people off to redo work
    that was already correct, so the response body does the talking.
    """
    try:
        error = resp.json().get("error", {})
    except ValueError:
        error = {}

    message = error.get("message") or resp.text[:200] or "no reason given"
    code = error.get("code")

    advice = {
        104: "No token reached Meta at all — WHATSAPP_ACCESS_TOKEN is empty in the running container.",
        190: "The token is expired or invalid. One copied from the API Setup page lasts 24 hours; a System User token with no expiry does not.",
        200: "The token is valid but lacks a permission — it needs whatsapp_business_messaging and whatsapp_business_management.",
        803: "That ID is not visible to this token, which usually means the token belongs to a different app.",
    }.get(code)

    detail = f"Meta says: {message}"
    if advice:
        detail += f" — {advice}"
    elif code is not None:
        detail += f" (code {code})"
    return detail


def _check_whatsapp_template() -> str:
    """Whether the configured template exists, is approved, and is in the
    configured language.

    Worth a second request because all three fail the same way and none of
    them fails now: the send is rejected at 07:30 with a 132001 nobody is
    awake to read, and the number simply goes quiet. The language is the
    likeliest of the three to be wrong — Meta's console offers en_US far more
    prominently than en, and they are different templates as far as the API
    is concerned.
    """
    from app.services import whatsapp

    name = settings.WHATSAPP_TEMPLATE_NAME
    want_language = settings.WHATSAPP_TEMPLATE_LANGUAGE

    if not settings.WHATSAPP_WABA_ID:
        return (
            f"Template '{name}' unverified — set WHATSAPP_WABA_ID (Meta shows it as "
            "'WhatsApp Business account ID') to have it checked here."
        )

    try:
        resp = httpx.get(
            f"{whatsapp._base()}/{whatsapp.GRAPH_VERSION}/{settings.WHATSAPP_WABA_ID}/message_templates",
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            params={"fields": "name,status,language", "limit": 200},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return f"Template '{name}' unverified — could not list templates: {e}"

    if resp.status_code >= 400:
        return f"Template '{name}' unverified — listing them returned {resp.status_code}."

    matching = [t for t in resp.json().get("data", []) if t.get("name") == name]
    if not matching:
        return f"No template named '{name}' exists on this account — the digest will not send."

    approved = [t for t in matching if (t.get("status") or "").upper() == "APPROVED"]
    if not approved:
        states = ", ".join(sorted({(t.get("status") or "?").upper() for t in matching}))
        return f"Template '{name}' exists but is {states}, not APPROVED — the digest will not send."

    languages = {t.get("language") for t in approved}
    if want_language not in languages:
        offered = ", ".join(sorted(lang for lang in languages if lang))
        return (
            f"Template '{name}' is approved in {offered}, but WHATSAPP_TEMPLATE_LANGUAGE "
            f"is '{want_language}' — set it to the exact code or the send is rejected."
        )

    return f"Template '{name}' is approved in {want_language}."


CHECKS = {
    "anthropic": check_anthropic,
    "whatsapp": check_whatsapp,
    "apollo": check_apollo,
    "smtp": check_smtp,
    "paystack": check_paystack,
}


def run_all() -> list[CheckResult]:
    results = []
    for name, check in CHECKS.items():
        try:
            results.append(check())
        except Exception as e:
            # A check that crashes must not take the page down with it.
            logger.exception("Integration check %s crashed", name)
            results.append(CheckResult(name, True, False, f"Check failed: {str(e)[:200]}"))
    return results
