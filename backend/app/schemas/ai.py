from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.ai_client import AIResponseError


class ParsedResume(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    education: str | None = None
    summary: str | None = None
    achievements: list[str] = Field(default_factory=list)


class ExtractedJobPosting(BaseModel):
    """One job read out of a job-alert email.

    Salary and work mode are here because the alerts show them and we were
    throwing them away. Indeed and Jobberman print "₦400,000 - ₦600,000 a
    month" and "Hybrid" right on the card; the extraction asked for four
    fields and got four, so every email-sourced job in the database had no
    salary and no work mode — which made a salary filter useless on exactly
    the supply a Nigerian user has most of.

    Both optional and both default to None, because an alert that shows
    neither must produce a job with neither rather than an invented figure.
    """

    title: str
    company: str = "Unknown"
    url: str | None = None
    location: str | None = None
    # Free text, copied from the email verbatim — "₦400,000 - ₦600,000 a
    # month". Parsed into comparable annual numbers downstream by
    # services/salary_parsing, which is conservative and yields nothing rather
    # than a guess, so a garbled string costs a filter and never a wrong one.
    salary: str | None = None
    # "remote" | "hybrid" | "onsite". Null where the listing does not say,
    # which is different from onsite and must not be flattened into it.
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None


class OutreachDraft(BaseModel):
    email_subject: str
    email_body: str
    linkedin_msg: str
    cv_bullets: list[str] = Field(default_factory=list)


class TailoredApplication(BaseModel):
    """A cover letter and résumé bullets written for one specific job."""

    cover_letter: str
    bullets: list[str] = Field(default_factory=list)


class JobFitScore(BaseModel):
    job_index: int
    overall_score: float = Field(ge=0, le=100)
    skills_score: float = Field(ge=0, le=100)
    experience_score: float = Field(ge=0, le=100)
    location_score: float = Field(ge=0, le=100)
    reason: str


class InterviewQuestionSet(BaseModel):
    questions: list[str] = Field(min_length=1)


class AnswerFeedback(BaseModel):
    # "model_answer" is a genuine domain term here (the ideal answer), not a
    # Pydantic model attribute — opt out of the protected `model_` namespace.
    model_config = ConfigDict(protected_namespaces=())

    score: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    model_answer: str


class InterviewSummary(BaseModel):
    summary: str
    next_steps: list[str] = Field(default_factory=list)


class NegotiationLever(BaseModel):
    lever: str
    rationale: str


class NegotiationAdvice(BaseModel):
    verdict: str
    confidence: Literal["high", "medium", "low"]
    levers: list[NegotiationLever] = Field(default_factory=list)
    counter_script: str
    if_they_say_no: str
    watch_outs: list[str] = Field(default_factory=list)


def validate_or_raise(model_cls: type[BaseModel], data: object):
    """Enforce a schema on an AI reply instead of trusting raw JSON.

    This is the fix for the exact gap the prior prototype had: a bare
    json.loads() with no shape validation, so any drift in the model's
    output silently corrupted stored data instead of failing loudly.
    """
    try:
        if isinstance(data, list):
            return [model_cls.model_validate(item) for item in data]
        return model_cls.model_validate(data)
    except ValidationError as e:
        raise AIResponseError(f"AI response did not match expected schema: {e}") from e
