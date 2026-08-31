from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.ai_client import AIResponseError


class ParsedResume(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    education: str | None = None
    summary: str | None = None
    achievements: list[str] = Field(default_factory=list)


class ExtractedJobPosting(BaseModel):
    title: str
    company: str = "Unknown"
    url: str | None = None
    location: str | None = None


class OutreachDraft(BaseModel):
    email_subject: str
    email_body: str
    linkedin_msg: str
    cv_bullets: list[str] = Field(default_factory=list)


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
