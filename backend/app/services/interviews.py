"""Mock interview simulator — practise the real interview before you sit it.

Gated at Pro rather than Elite: Autopilot Outreach is the Elite flagship, and
Pro needed a capability of its own rather than just a bigger credit bucket.

Two deliberate design choices:

1. All questions are generated up front, in one call, and the whole session is
   charged once at the start. A user can never be stranded halfway through an
   interview by an empty balance or a later AI failure.
2. Grading happens per answer, so feedback is immediate and specific to what
   the candidate actually said, rather than one lump verdict at the end.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import InterviewStatus, SubscriptionTier
from app.models.interview import InterviewSession, InterviewTurn
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.schemas.ai import AnswerFeedback, InterviewQuestionSet, InterviewSummary, validate_or_raise
from app.services import ai_client
from app.services.credits import adjust_credits

logger = logging.getLogger(__name__)
settings = get_settings()


class TierRequiredError(Exception):
    pass


class InsufficientCreditsError(Exception):
    pass


class SessionClosedError(Exception):
    pass


QUESTION_SYSTEM_PROMPT = (
    "You are a seasoned hiring manager running a realistic screening interview. "
    "Ask questions this specific candidate would actually face for this specific role. "
    "No riddles, no trivia, no generic 'what is your greatest weakness' filler."
)

GRADING_SYSTEM_PROMPT = (
    "You are an interview coach grading one answer. Be specific and honest: praise what "
    "genuinely worked, name what was missing, and never invent achievements the candidate "
    "did not mention. A vague or empty answer should score low."
)

SUMMARY_SYSTEM_PROMPT = (
    "You are an interview coach summarising a full mock interview. Be direct and practical. "
    "Focus on patterns across answers, not a restatement of each one."
)


def _candidate_block(user: User, resume: Resume | None) -> str:
    if resume is None:
        return "Candidate: no résumé on file — ask role-appropriate questions for a general candidate."
    positioning = f"\nPositioning: {user.positioning_statement}" if user.positioning_statement else ""
    return (
        f"Candidate skills: {', '.join(resume.parsed_skills[:10]) or 'Not specified'}\n"
        f"Experience: {resume.experience_years or 0} years\n"
        f"Summary: {resume.summary or 'Not specified'}{positioning}"
    )


def _role_block(role_title: str, company_name: str | None, job: Job | None) -> str:
    block = f"Role: {role_title}\nCompany: {company_name or 'a company in this space'}"
    if job is not None:
        block += f"\nRequirements: {', '.join(job.requirements[:8]) or 'Not specified'}"
        block += f"\nJob description: {job.description[:1200]}"
    return block


def generate_questions(user: User, resume: Resume | None, role_title: str, company_name: str | None, job: Job | None) -> list[str]:
    count = settings.INTERVIEW_QUESTION_COUNT
    prompt = f"""Write {count} interview questions for this candidate and role.

{_role_block(role_title, company_name, job)}

{_candidate_block(user, resume)}

RULES:
1. Mix behavioural and role-specific technical questions.
2. Ground at least two questions in the candidate's actual background above.
3. Order them the way a real screen would run: warm-up first, hardest in the middle.

Respond ONLY with valid minified JSON:
{{"questions": ["...", "..."]}}"""

    raw = ai_client.complete_json(
        system=QUESTION_SYSTEM_PROMPT,
        prompt=prompt,
        model=settings.ANTHROPIC_DRAFTING_MODEL,
        max_tokens=1200,
    )
    parsed = validate_or_raise(InterviewQuestionSet, raw)
    return parsed.questions[:count]


def grade_answer(session: InterviewSession, turn: InterviewTurn, answer: str) -> AnswerFeedback:
    prompt = f"""Grade this interview answer.

Role: {session.role_title}
Company: {session.company_name or 'Not specified'}

Question: {turn.question}

Candidate's answer:
{answer}

Score 0-100 on substance, specificity, and structure. An answer with no concrete
example scores below 50 no matter how confident it sounds.

Respond ONLY with valid minified JSON:
{{"score": 0, "strengths": ["..."], "improvements": ["..."], "model_answer": "..."}}"""

    raw = ai_client.complete_json(
        system=GRADING_SYSTEM_PROMPT,
        prompt=prompt,
        model=settings.ANTHROPIC_DRAFTING_MODEL,
        max_tokens=1000,
    )
    return validate_or_raise(AnswerFeedback, raw)


def summarize_session(session: InterviewSession) -> InterviewSummary:
    transcript = "\n\n".join(
        f"Q{turn.position + 1}: {turn.question}\nAnswer: {turn.answer or '(skipped)'}\nScore: {turn.score if turn.score is not None else 'n/a'}"
        for turn in session.turns
    )
    prompt = f"""Summarise this mock interview for the candidate.

Role: {session.role_title}

{transcript}

Respond ONLY with valid minified JSON:
{{"summary": "2-4 sentences on overall performance", "next_steps": ["concrete thing to practise", "..."]}}"""

    raw = ai_client.complete_json(
        system=SUMMARY_SYSTEM_PROMPT,
        prompt=prompt,
        model=settings.ANTHROPIC_DRAFTING_MODEL,
        max_tokens=800,
    )
    return validate_or_raise(InterviewSummary, raw)


def start_session(db: Session, user: User, job: Job | None, role_title: str | None) -> InterviewSession:
    """Create a session with all questions pre-generated, charging credits once."""
    if user.subscription_tier == SubscriptionTier.free:
        raise TierRequiredError("Mock interviews are available on Pro and Elite")
    if user.ai_credits < settings.INTERVIEW_CREDIT_COST:
        raise InsufficientCreditsError(
            f"Need {settings.INTERVIEW_CREDIT_COST} credits, have {user.ai_credits}"
        )

    title = role_title or (job.title if job else None)
    if not title:
        raise ValueError("Either job_id or role_title is required")
    company = job.company_name if job else None

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    questions = generate_questions(user, resume, title, company, job)

    session = InterviewSession(
        user_id=user.id,
        job_id=job.id if job else None,
        role_title=title[:255],
        company_name=company,
        status=InterviewStatus.in_progress,
    )
    session.turns = [
        InterviewTurn(position=i, question=question) for i, question in enumerate(questions)
    ]
    db.add(session)

    # Charged only after the AI call succeeds — a failed generation must never
    # cost the user credits.
    adjust_credits(db, user, action="interview", amount=-settings.INTERVIEW_CREDIT_COST)
    db.commit()
    db.refresh(session)
    return session


def submit_answer(db: Session, session: InterviewSession, turn: InterviewTurn, answer: str) -> InterviewTurn:
    if session.status != InterviewStatus.in_progress:
        raise SessionClosedError("This interview is already complete")

    feedback = grade_answer(session, turn, answer)

    turn.answer = answer
    turn.score = feedback.score
    turn.strengths = feedback.strengths
    turn.improvements = feedback.improvements
    turn.model_answer = feedback.model_answer
    turn.answered_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(turn)
    return turn


def complete_session(db: Session, session: InterviewSession) -> InterviewSession:
    if session.status != InterviewStatus.in_progress:
        raise SessionClosedError("This interview is already complete")

    scored = [turn.score for turn in session.turns if turn.score is not None]
    summary = summarize_session(session)

    session.average_score = round(sum(scored) / len(scored), 1) if scored else None
    session.summary = summary.summary
    session.next_steps = summary.next_steps
    session.status = InterviewStatus.completed
    session.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(session)
    return session
