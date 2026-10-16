import logging

from app.core.config import get_settings
from app.schemas.ai import ExtractedJobPosting, validate_or_raise
from app.services import ai_client

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = "You extract job postings from job-alert emails. Return ONLY a valid minified JSON array."

MAX_EMAIL_CHARS = 9000


def _build_prompt(email_text: str) -> str:
    truncated = email_text[:MAX_EMAIL_CHARS]
    return f"""Extract every distinct job posting mentioned in this job-alert email.

Email content:
{truncated}

Respond ONLY with a valid JSON array, one object per job. If there are no job
postings in this email, respond with an empty array: []

Format:
[
  {{
    "title": "Senior Software Engineer",
    "company": "Acme Corp",
    "url": "https://example.com/job/123",
    "location": "Lagos, Nigeria",
    "salary": "₦400,000 - ₦600,000 a month",
    "work_mode": "hybrid"
  }}
]

Rules for the fields that are allowed to be null:

- "url": null if the email shows no direct link for that job. Do not invent one.
- "salary": copy the pay exactly as the email prints it, including the
  currency symbol and the period ("a month", "per year"). Null if the email
  shows no pay for that job. Never estimate, and never carry a figure over
  from a different job in the same email.
- "work_mode": one of "remote", "hybrid", "onsite", or null if the listing
  does not say. Null is a real answer here — do not default to "onsite"."""


# A daily digest from LinkedIn or Indeed routinely lists 25 roles. The flat
# 1500 here had the same fault as scoring: enough for a short alert, silently
# cut off on a long one, and reported as malformed JSON.
#
# Raised from 80 with the salary and work_mode fields, which add a short
# string and a one-word enum per job. That is output tokens on an email we
# were already paying to read — a few cents a month across every mailbox —
# and it buys the only salary data the email-sourced supply has.
MAX_EXTRACTED_JOBS = 40
TOKENS_PER_EXTRACTED_JOB = 110


def extract_jobs_from_email(email_text: str) -> list[ExtractedJobPosting]:
    # Trimmed before it is sent, not after. The whole body used to go, and the
    # part past the listings is footer and legal text that costs input tokens
    # on every email forever. Logged when it bites, so a genuinely longer
    # alert shows up as a number to raise rather than as jobs silently missed.
    if len(email_text) > settings.MAX_EXTRACTION_CHARS:
        logger.info(
            "Alert email trimmed for extraction: %d chars -> %d",
            len(email_text), settings.MAX_EXTRACTION_CHARS,
        )
        email_text = email_text[: settings.MAX_EXTRACTION_CHARS]

    raw = ai_client.complete_json(
        feature="email_extraction",
        system=SYSTEM_PROMPT,
        prompt=_build_prompt(email_text),
        model=settings.ANTHROPIC_SCORING_MODEL,
        max_tokens=MAX_EXTRACTED_JOBS * TOKENS_PER_EXTRACTED_JOB,
    )
    if not raw:
        return []
    return validate_or_raise(ExtractedJobPosting, raw)
