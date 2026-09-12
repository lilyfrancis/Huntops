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

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    except smtplib.SMTPAuthenticationError:
        return CheckResult("smtp", True, False, "Server reachable but the username or password was rejected")
    except (smtplib.SMTPException, OSError) as e:
        return CheckResult("smtp", True, False, f"Could not connect to {settings.SMTP_HOST}:{settings.SMTP_PORT} — {e}")
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

    codes = {p.get("plan_code") for p in resp.json().get("data", [])}
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
    return CheckResult("paystack", True, True, f"Key valid; both plan codes found among {len(codes)} plan(s)")


def _readable(error: Exception) -> str:
    """Provider SDK errors are long and mostly noise; keep the useful part."""
    text = str(error)
    if "authentication_error" in text or "401" in text:
        return "Key rejected. Generate a new one and update ANTHROPIC_API_KEY."
    if "credit balance" in text.lower() or "insufficient" in text.lower():
        return "Key valid but the account has no credit."
    return text[:300]


CHECKS = {
    "anthropic": check_anthropic,
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
