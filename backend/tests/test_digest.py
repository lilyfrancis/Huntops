from app.models.enums import ExperienceLevel, JobStatus, JobType, UserRole
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.services import digest
from tests.conftest import auth_headers, register_user


def _seeded_user_with_match(db_session, geo_boost=False, fit=75.0, email="seeded@example.com"):
    user = User(email=email, password_hash="x", full_name="X", role=UserRole.job_seeker)
    db_session.add(user)
    db_session.flush()

    job = Job(
        title="Backend Engineer", description="desc", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid, source="remotive",
        source_url=f"https://example.com/{email}", company_name="Acme", status=JobStatus.active,
    )
    db_session.add(job)
    db_session.flush()

    match = JobMatch(user_id=user.id, job_id=job.id, fit_score=fit, geo_boost_applied=geo_boost)
    db_session.add(match)
    db_session.commit()
    return user


def test_get_top_matches_returns_geo_boosted_first(db_session):
    user = User(email="rank@example.com", password_hash="x", full_name="X", role=UserRole.job_seeker)
    db_session.add(user)
    db_session.flush()

    def make_job(url):
        job = Job(
            title="Role", description="d", requirements=[], location="Remote",
            job_type=JobType.full_time, experience_level=ExperienceLevel.mid, source="remotive", source_url=url,
            status=JobStatus.active,
        )
        db_session.add(job)
        db_session.flush()
        return job

    high_score_no_boost = make_job("https://example.com/1")
    low_score_with_boost = make_job("https://example.com/2")

    db_session.add(JobMatch(user_id=user.id, job_id=high_score_no_boost.id, fit_score=90, geo_boost_applied=False))
    db_session.add(JobMatch(user_id=user.id, job_id=low_score_with_boost.id, fit_score=60, geo_boost_applied=True))
    db_session.commit()

    results = digest.get_top_matches(db_session, user)
    assert results[0][1].id == low_score_with_boost.id  # geo-boosted wins even with a lower raw score


def test_format_digest_email_empty():
    subject, body = digest.format_digest_email([])
    assert "No new" in body


def test_format_digest_email_includes_home_market_marker(db_session):
    user = _seeded_user_with_match(db_session, geo_boost=True)
    matches = digest.get_top_matches(db_session, user)
    subject, body = digest.format_digest_email(matches)
    assert "home market" in subject or "home-market" in subject or "1" in subject
    assert "[home market]" in body


def test_digest_preview_endpoint_requires_job_seeker(client):
    data = register_user(client, email="employer-digest@example.com", role="employer", company_name="Acme")
    resp = client.get("/api/digest/preview", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 403


def test_digest_preview_endpoint_empty_when_no_matches(client):
    data = register_user(client, email="nomatches@example.com")
    resp = client.get("/api/digest/preview", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


# ---------- the digest leaked what the feed hides ----------

def _locked_job(db_session, **kw):
    from app.models.enums import ExperienceLevel, JobStatus, JobType
    from app.models.job import Job

    defaults = dict(
        title="Director of Sales, New Logo", description="d", requirements=[],
        location="Lagos", job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="weworkremotely", source_url="https://x.test/1", status=JobStatus.active,
        company_name="Temporal Technologies", salary_range="$140k",
    )
    defaults.update(kw)
    job = Job(**defaults)
    db_session.add(job)
    db_session.commit()
    return job


def _match(db_session, job, score=88):
    from app.models.job_match import JobMatch

    return JobMatch(job_id=job.id, user_id=None, fit_score=score, geo_boost_applied=False)


def test_the_email_does_not_name_a_company_the_user_has_not_unlocked(db_session):
    """Mailing it every morning is a more convenient leak than the website
    ever was."""
    from app.services.digest import format_digest_email

    job = _locked_job(db_session)
    _subject, body = format_digest_email([(_match(db_session, job), job)])

    assert "Temporal Technologies" not in body
    assert "company hidden" in body
    assert "New Logo" not in body        # the title is masked too


def test_the_email_keeps_the_salary_because_that_is_the_pull(db_session):
    from app.services.digest import format_digest_email

    job = _locked_job(db_session)
    _subject, body = format_digest_email([(_match(db_session, job), job)])
    assert "$140k" in body


def test_an_unlocked_job_is_named_in_full(db_session):
    from app.services.digest import format_digest_email

    job = _locked_job(db_session)
    _subject, body = format_digest_email([(_match(db_session, job), job)], {job.id})

    assert "Temporal Technologies" in body
    assert "Director of Sales, New Logo" in body


def test_internal_jobs_are_named_without_unlocking(db_session):
    from app.services.digest import format_digest_email

    job = _locked_job(db_session, source="internal", company_name="Acme")
    _subject, body = format_digest_email([(_match(db_session, job), job)])
    assert "Acme" in body


def test_the_whatsapp_nudge_does_not_name_a_locked_company(db_session):
    from app.models.enums import UserRole
    from app.models.user import User
    from app.services.digest import format_digest_whatsapp

    user = User(email="wa@example.com", password_hash="x", full_name="Ada Seeker",
                role=UserRole.job_seeker)
    job = _locked_job(db_session)
    params = format_digest_whatsapp(user, [(_match(db_session, job), job)])

    assert params is not None
    assert "Temporal Technologies" not in " ".join(params)
    assert "hidden company" in " ".join(params)
