"""Outreach drafting — ported from Job Engine's "Build Draft" node.

Job Engine hardcoded one person's voice, résumé, and positioning as prompt
constants for a single-tenant workflow. Here everything comes from the
requesting user's own stored résumé and optional positioning statement, so
the same prompt structure works for any candidate.
"""

from app.core.config import get_settings
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.schemas.ai import OutreachDraft, validate_or_raise
from app.services import ai_client

settings = get_settings()

SYSTEM_PROMPT = (
    "You are an expert career coach. Write outreach messages that are sharp, warm, "
    "specific, and completely free of filler, clichés, and generic template language. "
    "Never fabricate experience, skills, or metrics that aren't in the candidate's résumé."
)


def _build_prompt(user: User, resume: Resume, job: Job, recruiter_name: str | None, recruiter_title: str | None) -> str:
    positioning = f"\nHow the candidate wants to be positioned: {user.positioning_statement}" if user.positioning_statement else ""
    recruiter_line = f"{recruiter_name} ({recruiter_title})" if recruiter_name else "the hiring team"

    return f"""Write an outreach package for this candidate applying to this job.

Job: {job.title}
Company: {job.company_name or 'the company'}
Requirements: {', '.join(job.requirements[:8])}
Recruiter: {recruiter_line}

Candidate:
Skills: {', '.join(resume.parsed_skills[:8])}
Experience: {resume.experience_years or 0} years
Education: {resume.education or 'Not specified'}
Summary: {resume.summary or 'Not specified'}{positioning}

RULES:
1. Do not invent experience, skills, or numbers not already given above.
2. Weave in 2-3 genuine strengths relevant to this specific job's requirements.
3. No em dashes. No "I hope this finds you well." No generic flattery.

Generate:
1. A short, specific email subject line
2. A 120-160 word email body addressed to the recruiter
3. A 40-60 word LinkedIn connection note
4. 4-6 ATS-clean, tailored résumé bullets for this role

Respond ONLY with valid minified JSON in this exact format:
{{
  "email_subject": "...",
  "email_body": "...",
  "linkedin_msg": "...",
  "cv_bullets": ["...", "..."]
}}"""


def draft_outreach(user: User, resume: Resume, job: Job, recruiter_name: str | None, recruiter_title: str | None) -> OutreachDraft:
    raw = ai_client.complete_json(
        system=SYSTEM_PROMPT,
        prompt=_build_prompt(user, resume, job, recruiter_name, recruiter_title),
        model=settings.ANTHROPIC_DRAFTING_MODEL,
        max_tokens=1400,
    )
    return validate_or_raise(OutreachDraft, raw)
