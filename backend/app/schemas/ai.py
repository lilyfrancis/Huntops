from pydantic import BaseModel, Field, ValidationError

from app.services.ai_client import AIResponseError


class ParsedResume(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    education: str | None = None
    summary: str | None = None
    achievements: list[str] = Field(default_factory=list)


class JobFitScore(BaseModel):
    job_index: int
    overall_score: float = Field(ge=0, le=100)
    skills_score: float = Field(ge=0, le=100)
    experience_score: float = Field(ge=0, le=100)
    location_score: float = Field(ge=0, le=100)
    reason: str


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
