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
    "location": "Remote"
  }}
]

If a job has no visible direct URL in the email, set "url" to null — do not
invent one."""


# A daily digest from LinkedIn or Indeed routinely lists 25 roles, and each
# extracted posting is a title, company, URL and location — about 60 tokens.
# The flat 1500 here had the same fault as scoring: enough for a short alert,
# silently cut off on a long one, and reported as malformed JSON.
MAX_EXTRACTED_JOBS = 40
TOKENS_PER_EXTRACTED_JOB = 80


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
