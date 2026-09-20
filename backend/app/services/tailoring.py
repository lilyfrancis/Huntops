"""Writing an application for one specific job, rather than sending the same
one everywhere.

Auto-apply created applications with `cover_letter=None`, so the strongest
thing the product does — deciding a role is worth applying to — was followed
by the weakest possible application. This fills that in.

Cached per (user, job) like outreach: the draft is the expensive part, and
re-opening a job, editing the text, or applying a day later should not cost
again.
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.application_draft import ApplicationDraft
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.schemas.ai import TailoredApplication, validate_or_raise
from app.services import ai_client
from app.services.credits import adjust_credits

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = (
    "You write job applications. You are specific, you never invent experience the "
    "candidate does not have, and you never use the words 'passionate', 'synergy' or "
    "'leverage'. You write the way a competent person writes to another competent person."
)

MAX_TOKENS = 1600


class NoResumeError(Exception):
    pass


def _build_prompt(user: User, resume: Resume, job: Job) -> str:
    return f"""Candidate:
Name: {user.full_name}
Skills: {', '.join(resume.parsed_skills) or 'not listed'}
Years of experience: {resume.experience_years or 0}
Education: {resume.education or 'Not specified'}
Résumé: {resume.raw_text[:3000]}

Role:
{job.title} at {job.company_name or 'the company'} — {job.location}
Requirements: {', '.join(job.requirements[:8]) or 'not listed'}
{job.description[:1500]}

Write:
1. A cover letter of 150-220 words. Address the two or three requirements this
   candidate genuinely meets, with evidence from their résumé. Do not claim
   anything the résumé does not support. No greeting line addressed to a name
   you do not know — open with "Hello," if there is no name.
2. Four to six résumé bullets rewritten for this role: ATS-clean, starting with
   a verb, quantified wherever the résumé gives you a number. Reuse the
   candidate's real achievements, reworded to foreground what this role asks
   for. Do not invent metrics.

Respond ONLY with JSON:
{{
  "cover_letter": "...",
  "bullets": ["...", "..."]
}}"""


def generate(db: Session, user: User, job: Job, *, force: bool = False) -> ApplicationDraft:
    """The tailored draft for this job, from cache unless asked to redo it.

    Charged on generation only. A user who opens the same job three times,
    or edits their letter, pays once — the cost is the model call, and we
    only make it once.
    """
    existing = (
        db.query(ApplicationDraft)
        .filter(ApplicationDraft.user_id == user.id, ApplicationDraft.job_id == job.id)
        .first()
    )
    if existing is not None and not force:
        return existing

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if resume is None:
        raise NoResumeError("Upload a résumé first — there is nothing to tailor from.")

    # Raised, not caught: no draft row and no charge for a failed generation.
    raw = ai_client.complete_json(
        system=SYSTEM_PROMPT,
        prompt=_build_prompt(user, resume, job),
        model=settings.ANTHROPIC_DRAFTING_MODEL,
        max_tokens=MAX_TOKENS,
    )
    drafted: TailoredApplication = validate_or_raise(TailoredApplication, raw)

    if existing is None:
        existing = ApplicationDraft(user_id=user.id, job_id=job.id)
        db.add(existing)

    existing.cover_letter = drafted.cover_letter
    existing.bullets = drafted.bullets
    existing.edited = False

    adjust_credits(db, user, action="tailor", amount=-settings.TAILOR_CREDIT_COST)
    db.commit()
    db.refresh(existing)
    return existing


def save_edits(db: Session, draft: ApplicationDraft, *, cover_letter: str, bullets: list[str]) -> ApplicationDraft:
    """Keep what the person wrote. Editing is free — it is their work, not ours."""
    draft.cover_letter = cover_letter.strip()
    draft.bullets = [b.strip() for b in bullets if b.strip()]
    draft.edited = True
    db.commit()
    db.refresh(draft)
    return draft
