from app.core.config import get_settings
from app.schemas.ai import ParsedResume, validate_or_raise
from app.services import ai_client

settings = get_settings()

SYSTEM_PROMPT = "You are an expert resume parser. Extract key information accurately."


def _build_prompt(resume_text: str) -> str:
    return f"""Parse this resume and extract:
1. List of skills (as JSON array)
2. Years of experience (as integer)
3. Education level
4. Brief professional summary (2-3 sentences)
5. Key achievements (list)

Resume text:
{resume_text}

Respond ONLY with valid JSON in this exact format:
{{
  "skills": ["skill1", "skill2"],
  "experience_years": 5,
  "education": "Bachelor's in Computer Science",
  "summary": "Professional summary here",
  "achievements": ["achievement1", "achievement2"]
}}"""


def parse_resume(resume_text: str) -> ParsedResume:
    raw = ai_client.complete_json(
        system=SYSTEM_PROMPT,
        prompt=_build_prompt(resume_text),
        model=settings.ANTHROPIC_SCORING_MODEL,
        max_tokens=1500,
    )
    return validate_or_raise(ParsedResume, raw)
