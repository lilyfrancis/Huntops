from app.core.config import get_settings
from app.schemas.ai import ExtractedJobPosting, validate_or_raise
from app.services import ai_client

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


def extract_jobs_from_email(email_text: str) -> list[ExtractedJobPosting]:
    raw = ai_client.complete_json(
        system=SYSTEM_PROMPT,
        prompt=_build_prompt(email_text),
        model=settings.ANTHROPIC_SCORING_MODEL,
        max_tokens=1500,
    )
    if not raw:
        return []
    return validate_or_raise(ExtractedJobPosting, raw)
