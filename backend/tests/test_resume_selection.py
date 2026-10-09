"""Which CV a job uses.

The failure this guards against is subtle: a job scored against the
engineering CV and then applied for with the sales one. Nothing errors, the
application just arrives written for a different career — so every path has
to make the same choice from the same rule.
"""

import uuid

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.services import resume_selection


def _user(db) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db.add(user)
    db.flush()
    return user


def _cv(db, user, label, lanes, primary=False) -> Resume:
    resume = Resume(user_id=user.id, raw_text="x" * 120, label=label,
                    lanes=lanes, is_primary=primary, parsed_skills=[])
    db.add(resume)
    db.flush()
    return resume


def _job(db, lane) -> Job:
    job = Job(title="A role", description="d", requirements=[], location="Lagos, Nigeria",
              job_type=JobType.full_time, experience_level=ExperienceLevel.senior,
              source="internal", source_url=f"https://x.test/{uuid.uuid4()}",
              status=JobStatus.active, lane=lane)
    db.add(job)
    db.flush()
    return job


def test_a_job_uses_the_cv_that_claims_its_family(db_session):
    user = _user(db_session)
    eng = _cv(db_session, user, "Engineering", ["engineering"], primary=True)
    sales = _cv(db_session, user, "Sales", ["sales"])

    assert resume_selection.for_job(db_session, user, _job(db_session, JobLane.engineering)).id == eng.id
    assert resume_selection.for_job(db_session, user, _job(db_session, JobLane.sales)).id == sales.id


def test_an_unclaimed_family_falls_back_to_the_primary(db_session):
    user = _user(db_session)
    _cv(db_session, user, "Engineering", ["engineering"])
    fallback = _cv(db_session, user, "General", [], primary=True)

    chosen = resume_selection.for_job(db_session, user, _job(db_session, JobLane.finance))

    assert chosen.id == fallback.id


def test_a_job_with_no_family_falls_back_too(db_session):
    user = _user(db_session)
    _cv(db_session, user, "Engineering", ["engineering"])
    fallback = _cv(db_session, user, "General", [], primary=True)

    assert resume_selection.for_job(db_session, user, _job(db_session, None)).id == fallback.id
    assert resume_selection.for_job(db_session, user, None).id == fallback.id


def test_one_cv_behaves_exactly_as_before(db_session):
    """Every existing account has one CV and must not notice this change."""
    user = _user(db_session)
    only = _cv(db_session, user, "My CV", [], primary=True)

    assert resume_selection.for_job(db_session, user, _job(db_session, JobLane.engineering)).id == only.id


def test_no_cv_returns_nothing_rather_than_raising(db_session):
    assert resume_selection.for_job(db_session, _user(db_session), None) is None


def test_scoring_groups_the_candidates_by_cv(db_session):
    """One call per CV in play, not one per job — and one CV stays one call."""
    user = _user(db_session)
    _cv(db_session, user, "Engineering", ["engineering"], primary=True)
    _cv(db_session, user, "Sales", ["sales"])
    jobs = [
        _job(db_session, JobLane.engineering),
        _job(db_session, JobLane.engineering),
        _job(db_session, JobLane.sales),
    ]

    groups = resume_selection.group_by_resume(db_session, user, jobs)

    assert sorted(len(g[1]) for g in groups) == [1, 2]
    assert {g[0].label for g in groups} == {"Engineering", "Sales"}


def test_deleting_the_fallback_promotes_another(db_session):
    """Otherwise the account is left with CVs but no fallback, and every job
    whose family nobody claims has nowhere to go."""
    user = _user(db_session)
    primary = _cv(db_session, user, "General", [], primary=True)
    _cv(db_session, user, "Engineering", ["engineering"])

    db_session.delete(primary)
    db_session.flush()
    resume_selection.ensure_one_primary(db_session, user)

    remaining = resume_selection.all_for(db_session, user)
    assert len(remaining) == 1
    assert remaining[0].is_primary is True


def test_there_is_never_more_than_one_primary(db_session):
    user = _user(db_session)
    a = _cv(db_session, user, "A", [], primary=True)
    b = _cv(db_session, user, "B", [], primary=True)

    resume_selection.ensure_one_primary(db_session, user, prefer=b)

    assert [r.is_primary for r in resume_selection.all_for(db_session, user)].count(True) == 1
    assert resume_selection.primary(db_session, user).id == b.id
    assert a.is_primary is False
