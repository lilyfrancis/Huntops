"""Paging the matches list, and not paying to do it.

Matches are a stable ranking rather than a stream: a job is scored once and
keeps its score, so the top of the list is identical on every visit by
design. Without a way to go past it that reads as the page being broken,
which is how it was reported.
"""

import uuid

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.resume import Resume
from app.models.user import User
from tests.conftest import register_user


def _seed(db, count: int, user_id, score_from: float = 99.0):
    for i in range(count):
        job = Job(
            title=f"Role {i}", description="d" * 60, requirements=[], location="Lagos, Nigeria",
            job_type=JobType.full_time, experience_level=ExperienceLevel.mid, source="test",
            source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active,
        )
        db.add(job)
        db.flush()
        db.add(JobMatch(
            user_id=user_id, job_id=job.id, fit_score=score_from - i,
            skills_score=80, experience_score=80, geo_score=80, reason="r",
        ))
    db.commit()


def _auth(client, email="pager@example.com"):
    data = register_user(client, email=email)
    return {"Authorization": f"Bearer {data['access_token']}"}, uuid.UUID(data["user"]["id"])


def test_the_second_page_is_different_from_the_first(client):
    from app.db.base import SessionLocal

    headers, user_id = _auth(client)
    session = SessionLocal()
    try:
        session.add(Resume(user_id=user_id, raw_text="x", parsed_skills=["Python"], experience_years=4))
        session.commit()
        _seed(session, 30, user_id)
    finally:
        session.close()

    first = client.get("/api/ai/match-jobs?limit=10&skip=0", headers=headers).json()
    second = client.get("/api/ai/match-jobs?limit=10&skip=10", headers=headers).json()

    assert first["total"] == 30
    assert len(first["matches"]) == 10 and len(second["matches"]) == 10
    assert {m["job"]["id"] for m in first["matches"]}.isdisjoint(
        {m["job"]["id"] for m in second["matches"]}
    )


def test_paging_does_not_trigger_a_scoring_run(client, monkeypatch):
    """Scoring is an AI call behind a 20/hour limit. Spending it to show a
    list the user has already been shown would burn the budget on
    navigation."""
    from app.db.base import SessionLocal
    from app.routers import matches as matches_router

    headers, user_id = _auth(client, "nopay@example.com")
    session = SessionLocal()
    try:
        session.add(Resume(user_id=user_id, raw_text="x", parsed_skills=["Python"], experience_years=4))
        session.commit()
        _seed(session, 25, user_id)
    finally:
        session.close()

    calls = []
    monkeypatch.setattr(
        matches_router.matching, "score_jobs",
        lambda *a, **k: calls.append(1) or [],
    )

    client.get("/api/ai/match-jobs?limit=10&skip=10", headers=headers)
    assert calls == []


def test_tied_scores_do_not_make_pages_overlap(client):
    """Dozens of jobs share a score, and ordering on score alone is not a
    total order — Postgres may arrange a tied group differently per query,
    which produces pages that repeat some rows and skip others."""
    from app.db.base import SessionLocal

    headers, user_id = _auth(client, "ties@example.com")
    session = SessionLocal()
    try:
        session.add(Resume(user_id=user_id, raw_text="x", parsed_skills=["Python"], experience_years=4))
        session.commit()
        _seed(session, 20, user_id, score_from=75.0)
        # Every one of these shares a single score.
        for m in session.query(JobMatch).filter(JobMatch.user_id == user_id).all():
            m.fit_score = 75.0
        session.commit()
    finally:
        session.close()

    seen = []
    for page in range(4):
        body = client.get(f"/api/ai/match-jobs?limit=5&skip={page * 5}", headers=headers).json()
        seen.extend(m["job"]["id"] for m in body["matches"])

    assert len(seen) == len(set(seen)) == 20


def test_the_total_counts_everything_above_the_bar_not_the_page(client):
    from app.db.base import SessionLocal

    headers, user_id = _auth(client, "totals@example.com")
    session = SessionLocal()
    try:
        session.add(Resume(user_id=user_id, raw_text="x", parsed_skills=["Python"], experience_years=4))
        session.commit()
        _seed(session, 12, user_id)
    finally:
        session.close()

    body = client.get("/api/ai/match-jobs?limit=5", headers=headers).json()

    assert len(body["matches"]) == 5
    assert body["total"] == 12
