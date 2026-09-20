"""A reply that got cut off is not a malformed reply.

Both arrive as unparseable JSON, and reporting the first as the second is
what made this take so long to find: "AI response was not valid JSON" sends
you to the prompt and the model, when the budget was the problem.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services import ai_client, matching
from app.services.ai_client import AIResponseError


def _reply(text, stop_reason="end_turn"):
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.stop_reason = stop_reason
    return response


def _with(response):
    client = MagicMock()
    client.messages.create.return_value = response
    return patch.object(ai_client, "_get_client", return_value=client), client


def test_a_truncated_reply_says_it_was_truncated():
    ctx, _ = _with(_reply('[{"job_index": 0, "overall_sc', stop_reason="max_tokens"))
    with ctx:
        with pytest.raises(AIResponseError) as e:
            ai_client.complete_json("s", "p", "m", max_tokens=2000)

    assert "cut off" in str(e.value)
    assert "2000" in str(e.value)          # the number you have to change
    assert "not valid JSON" not in str(e.value)


def test_genuinely_malformed_output_is_still_reported_as_malformed():
    """The truncation check must not swallow the case it was added beside."""
    ctx, _ = _with(_reply("Sure! Here are the scores:", stop_reason="end_turn"))
    with ctx:
        with pytest.raises(AIResponseError, match="not valid JSON"):
            ai_client.complete_json("s", "p", "m")


def test_a_complete_reply_parses_normally():
    ctx, _ = _with(_reply('```json\n[{"job_index": 0}]\n```'))
    with ctx:
        assert ai_client.complete_json("s", "p", "m") == [{"job_index": 0}]


# ---------- the budget itself ----------

def test_the_scoring_budget_grows_with_the_candidate_count():
    """A flat 2000 against MAX_MATCH_CANDIDATES of 40 left no room: forty
    scored jobs with a one-sentence reason each is roughly 3000 tokens."""
    assert matching._scoring_budget(40) > 3000
    assert matching._scoring_budget(40) > matching._scoring_budget(10)


def test_the_budget_has_a_floor_so_a_single_job_is_not_starved():
    assert matching._scoring_budget(1) >= 1000


def test_scoring_asks_for_a_budget_that_fits_the_jobs_it_sends(db_session):
    """The wiring, not just the arithmetic."""
    from app.models.enums import ExperienceLevel, JobType
    from app.models.job import Job
    from app.models.resume import Resume

    jobs = [
        Job(title=f"Role {i}", description="d", requirements=[], location="Remote",
            job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
            source="internal", source_url=f"https://x.test/{i}")
        for i in range(40)
    ]
    resume = Resume(user_id=None, raw_text="x", parsed_skills=["Python"], experience_years=5)

    with patch.object(matching.ai_client, "complete_json", return_value=[]) as call:
        matching.score_jobs(resume, jobs, "Nigeria")

    assert call.call_args.kwargs["max_tokens"] >= 4000


def test_the_prompt_bounds_the_reason_so_the_budget_is_a_real_bound():
    """A budget computed per job only holds if the model is told how long a
    reason may be — otherwise the ceiling just moves."""
    from app.models.enums import ExperienceLevel, JobType
    from app.models.job import Job
    from app.models.resume import Resume

    job = Job(title="R", description="d", requirements=[], location="Remote",
              job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
              source="internal", source_url="https://x.test/1")
    resume = Resume(user_id=None, raw_text="x", parsed_skills=["Python"], experience_years=5)

    assert "15 words" in matching._build_prompt(resume, [job], "Nigeria")
