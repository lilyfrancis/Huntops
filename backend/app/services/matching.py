from app.core.config import get_settings
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.ai import JobFitScore, validate_or_raise
from app.services import ai_client

settings = get_settings()

SYSTEM_PROMPT = "You are an expert job matching AI. Provide detailed, objective assessments."


def _build_prompt(resume: Resume, jobs: list[Job], home_market: str | None) -> str:
    jobs_summary = "\n".join(
        f"{i}. {job.title} | Location: {job.location} | Remote: {job.is_remote} | "
        f"Restricted to: {job.restricted_to or 'none'} | "
        f"Requirements: {', '.join(job.requirements[:5])} | "
        f"{job.description[:200]}"
        for i, job in enumerate(jobs)
    )

    geo_note = (
        f"\nThe candidate is based in {home_market}. Treat a job as a strong geographic fit if it is "
        f"remote with no restriction, or if its 'Restricted to' matches the candidate's location. "
        f"Score location_score low if the job is restricted to a different country/region."
        if home_market
        else ""
    )

    return f"""Candidate Profile:
Skills: {', '.join(resume.parsed_skills)}
Experience: {resume.experience_years or 0} years
Education: {resume.education or 'Not specified'}
{geo_note}

Available Jobs:
{jobs_summary}

For each job, provide:
1. Overall match score (0-100)
2. Skills match score (0-100)
3. Experience match score (0-100)
4. Location/remote fit (0-100)
5. Brief reason

Respond ONLY with a valid JSON array, one object per job, in this exact format:
[
  {{
    "job_index": 0,
    "overall_score": 85,
    "skills_score": 90,
    "experience_score": 80,
    "location_score": 85,
    "reason": "Strong technical match with relevant experience"
  }}
]"""


def score_jobs(resume: Resume, jobs: list[Job], home_market: str | None) -> list[tuple[Job, JobFitScore, bool]]:
    """Returns (job, score, geo_boost_applied) tuples, geo-boosted and sorted best-first."""
    if not jobs:
        return []

    raw = ai_client.complete_json(
        system=SYSTEM_PROMPT,
        prompt=_build_prompt(resume, jobs, home_market),
        model=settings.ANTHROPIC_SCORING_MODEL,
        max_tokens=2000,
    )
    scores: list[JobFitScore] = validate_or_raise(JobFitScore, raw)

    results = []
    for score in scores:
        if score.job_index >= len(jobs):
            continue
        job = jobs[score.job_index]

        geo_eligible = job.is_remote and (not job.restricted_to or job.restricted_to == home_market)
        boost_applied = bool(home_market and geo_eligible)
        if boost_applied:
            score.overall_score = min(100, score.overall_score + settings.GEO_MATCH_BOOST)

        results.append((job, score, boost_applied))

    results.sort(key=lambda r: r[1].overall_score, reverse=True)
    return results
