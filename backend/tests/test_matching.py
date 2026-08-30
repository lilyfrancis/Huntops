from unittest.mock import patch

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.resume import Resume
from app.services import matching
from tests.conftest import auth_headers, register_user


def _make_resume(user_id) -> Resume:
    return Resume(
        user_id=user_id,
        raw_text="dummy",
        parsed_skills=["Python", "SQL"],
        experience_years=5,
        education="B.Sc.",
        summary="Backend engineer",
        achievements=[],
    )


def _make_job(**overrides) -> Job:
    defaults = dict(
        title="Backend Engineer", description="Build APIs", requirements=["Python"],
        location="Remote", job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        status=JobStatus.active, source="remotive", is_remote=True, restricted_to=None,
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_score_jobs_applies_geo_boost_when_remote_and_unrestricted(db_session):
    user_id = "00000000-0000-0000-0000-000000000001"
    resume = _make_resume(user_id)
    job = _make_job()
    db_session.add(job)
    db_session.flush()

    fake_scores = [
        {"job_index": 0, "overall_score": 70, "skills_score": 80, "experience_score": 75, "location_score": 60, "reason": "Good fit"}
    ]
    with patch("app.services.matching.ai_client.complete_json", return_value=fake_scores):
        results = matching.score_jobs(resume, [job], home_market="Nigeria")

    assert len(results) == 1
    scored_job, score, boost_applied = results[0]
    assert boost_applied is True
    assert score.overall_score == 70 + 15  # GEO_MATCH_BOOST default


def test_score_jobs_does_not_boost_when_restricted_to_other_country(db_session):
    user_id = "00000000-0000-0000-0000-000000000002"
    resume = _make_resume(user_id)
    job = _make_job(restricted_to="US")
    db_session.add(job)
    db_session.flush()

    fake_scores = [
        {"job_index": 0, "overall_score": 70, "skills_score": 80, "experience_score": 75, "location_score": 60, "reason": "Good fit"}
    ]
    with patch("app.services.matching.ai_client.complete_json", return_value=fake_scores):
        results = matching.score_jobs(resume, [job], home_market="Nigeria")

    _, score, boost_applied = results[0]
    assert boost_applied is False
    assert score.overall_score == 70


def test_score_jobs_no_boost_without_home_market(db_session):
    user_id = "00000000-0000-0000-0000-000000000003"
    resume = _make_resume(user_id)
    job = _make_job()
    db_session.add(job)
    db_session.flush()

    fake_scores = [
        {"job_index": 0, "overall_score": 70, "skills_score": 80, "experience_score": 75, "location_score": 60, "reason": "Good fit"}
    ]
    with patch("app.services.matching.ai_client.complete_json", return_value=fake_scores):
        results = matching.score_jobs(resume, [job], home_market=None)

    _, score, boost_applied = results[0]
    assert boost_applied is False
    assert score.overall_score == 70


def test_score_jobs_caps_boost_at_100(db_session):
    user_id = "00000000-0000-0000-0000-000000000004"
    resume = _make_resume(user_id)
    job = _make_job()
    db_session.add(job)
    db_session.flush()

    fake_scores = [
        {"job_index": 0, "overall_score": 95, "skills_score": 90, "experience_score": 90, "location_score": 90, "reason": "Great fit"}
    ]
    with patch("app.services.matching.ai_client.complete_json", return_value=fake_scores):
        results = matching.score_jobs(resume, [job], home_market="Nigeria")

    _, score, _ = results[0]
    assert score.overall_score == 100


def test_score_jobs_sorts_best_first(db_session):
    user_id = "00000000-0000-0000-0000-000000000005"
    resume = _make_resume(user_id)
    job_a = _make_job(title="Job A")
    job_b = _make_job(title="Job B")
    db_session.add_all([job_a, job_b])
    db_session.flush()

    fake_scores = [
        {"job_index": 0, "overall_score": 40, "skills_score": 40, "experience_score": 40, "location_score": 40, "reason": "Weak"},
        {"job_index": 1, "overall_score": 90, "skills_score": 90, "experience_score": 90, "location_score": 90, "reason": "Strong"},
    ]
    with patch("app.services.matching.ai_client.complete_json", return_value=fake_scores):
        results = matching.score_jobs(resume, [job_a, job_b], home_market=None)

    assert results[0][0].title == "Job B"
    assert results[1][0].title == "Job A"


def test_score_jobs_empty_job_list_short_circuits(db_session):
    resume = _make_resume("00000000-0000-0000-0000-000000000006")
    with patch("app.services.matching.ai_client.complete_json") as mock_call:
        results = matching.score_jobs(resume, [], home_market=None)
    assert results == []
    mock_call.assert_not_called()


# ---------- endpoint-level test ----------

@patch("app.routers.resumes.resumes_service.parse_resume")
@patch("app.routers.matches.matching.score_jobs")
def test_match_jobs_endpoint_filters_below_threshold_and_persists(mock_score_jobs, mock_parse, client):
    import io
    from app.schemas.ai import ParsedResume, JobFitScore

    mock_parse.return_value = ParsedResume(skills=["Python"], experience_years=5, education="B.Sc.", summary="s", achievements=[])

    data = register_user(client, email="matcher@example.com")
    headers = auth_headers(data["access_token"])

    client.post(
        "/api/resumes/upload", headers=headers,
        files={"file": ("r.txt", io.BytesIO(b"A" * 200), "text/plain")},
    )

    # Seed one active job directly via the DB session used by the app.
    from app.db.base import SessionLocal
    session = SessionLocal()
    job = _make_job(title="High Fit Role")
    job2 = _make_job(title="Low Fit Role")
    session.add_all([job, job2])
    session.commit()
    session.refresh(job)
    session.refresh(job2)
    job_ids = [job.id, job2.id]
    session.close()

    def fake_score_jobs(resume, jobs, home_market):
        by_title = {j.title: j for j in jobs}
        return [
            (by_title["High Fit Role"], JobFitScore(job_index=0, overall_score=80, skills_score=80, experience_score=80, location_score=80, reason="great"), False),
            (by_title["Low Fit Role"], JobFitScore(job_index=1, overall_score=30, skills_score=30, experience_score=30, location_score=30, reason="weak"), False),
        ]

    mock_score_jobs.side_effect = fake_score_jobs

    resp = client.get("/api/ai/match-jobs", headers=headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["job"]["title"] == "High Fit Role"
    assert results[0]["fit_score"] == 80

    # A second call should reuse/update the same JobMatch row, not duplicate it.
    resp2 = client.get("/api/ai/match-jobs", headers=headers)
    assert resp2.status_code == 200

    from app.models.job_match import JobMatch
    session = SessionLocal()
    match_count = session.query(JobMatch).filter(JobMatch.job_id.in_(job_ids)).count()
    session.close()
    assert match_count == 1


def test_match_jobs_requires_resume_first(client):
    data = register_user(client, email="noresume-match@example.com")
    headers = auth_headers(data["access_token"])
    resp = client.get("/api/ai/match-jobs", headers=headers)
    assert resp.status_code == 404
