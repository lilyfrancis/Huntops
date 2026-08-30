from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core.crypto import encrypt
from app.models.enums import ExperienceLevel, JobType, OutreachStatus, SubscriptionTier, UserRole
from app.models.gmail_connection import GmailConnection
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.recruiter_contact import RecruiterContact
from app.models.resume import Resume
from app.models.user import User
from app.schemas.ai import OutreachDraft
from app.services import outreach as outreach_service


def _elite_user_with_resume(db_session, email="elite@example.com", credits=100) -> User:
    user = User(
        email=email, password_hash="x", full_name="Elite User", role=UserRole.job_seeker,
        subscription_tier=SubscriptionTier.elite, ai_credits=credits,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Resume(user_id=user.id, raw_text="dummy", parsed_skills=["Python"], experience_years=5))
    db_session.commit()
    return user


def _job(db_session, **overrides) -> Job:
    defaults = dict(
        title="Backend Engineer", description="Build APIs", requirements=["Python"],
        location="Remote", job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="internal", company_name="Acme",
    )
    defaults.update(overrides)
    job = Job(**defaults)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


FAKE_DRAFT = OutreachDraft(
    email_subject="RevOps leader with 5 years driving Salesforce automation",
    email_body="Hi Jane, I saw the Backend Engineer role and wanted to reach out directly...",
    linkedin_msg="Hi Jane — following up on the Backend Engineer role at Acme...",
    cv_bullets=["Built an internal automation platform used by 40 reps"],
)


def test_rejects_non_elite_tier(db_session):
    user = _elite_user_with_resume(db_session, "free-tier@example.com")
    user.subscription_tier = SubscriptionTier.free
    db_session.commit()
    job = _job(db_session)

    with pytest.raises(outreach_service.TierRequiredError):
        outreach_service.initiate_outreach(db_session, user, job)


def test_rejects_insufficient_credits(db_session):
    user = _elite_user_with_resume(db_session, "poor@example.com", credits=5)
    job = _job(db_session)

    with pytest.raises(outreach_service.InsufficientCreditsError):
        outreach_service.initiate_outreach(db_session, user, job)


def test_requires_resume(db_session):
    user = User(email="noresume@example.com", password_hash="x", full_name="X", role=UserRole.job_seeker,
                subscription_tier=SubscriptionTier.elite, ai_credits=100)
    db_session.add(user)
    db_session.commit()
    job = _job(db_session)

    with pytest.raises(outreach_service.ResumeRequiredError):
        outreach_service.initiate_outreach(db_session, user, job)


def test_requires_job_company_name(db_session):
    user = _elite_user_with_resume(db_session, "nocompany@example.com")
    job = _job(db_session, company_name=None)

    with pytest.raises(outreach_service.MissingCompanyError):
        outreach_service.initiate_outreach(db_session, user, job)


@patch("app.services.outreach.outreach_drafting.draft_outreach", return_value=FAKE_DRAFT)
@patch("app.services.outreach.apollo.enrich_person", return_value={"email": "jane@acme.com", "email_status": "verified", "name": "Jane", "title": "Recruiter"})
@patch("app.services.outreach.apollo.search_people", return_value=[{"id": "p1", "name": "Jane", "title": "Recruiter"}])
def test_drafts_and_sends_when_recruiter_email_and_gmail_connected(mock_search, mock_enrich, mock_draft, db_session):
    user = _elite_user_with_resume(db_session)
    job = _job(db_session)
    db_session.add(GmailConnection(
        user_id=user.id, access_token_encrypted=encrypt("tok"), refresh_token_encrypted=encrypt("rtok"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1), label_id="Label_1",
    ))
    db_session.commit()

    with patch("app.services.outreach.gmail_oauth.send_message", return_value="msg123") as mock_send:
        result = outreach_service.initiate_outreach(db_session, user, job)

    assert result.status == OutreachStatus.sent
    assert result.sent_at is not None
    mock_send.assert_called_once()
    assert mock_send.call_args[0][1] == "jane@acme.com"

    db_session.refresh(user)
    assert user.ai_credits == 100 - outreach_service.settings.OUTREACH_CREDIT_COST

    contact = db_session.query(RecruiterContact).filter(RecruiterContact.job_id == job.id).first()
    assert contact.email == "jane@acme.com"


@patch("app.services.outreach.outreach_drafting.draft_outreach", return_value=FAKE_DRAFT)
@patch("app.services.outreach.apollo.search_people", return_value=[])
def test_draft_only_when_no_recruiter_found(mock_search, mock_draft, db_session):
    user = _elite_user_with_resume(db_session, "nomatch@example.com")
    job = _job(db_session, title="Obscure Role")

    result = outreach_service.initiate_outreach(db_session, user, job)

    assert result.status == OutreachStatus.draft_no_contact
    assert result.recruiter_contact_id is None
    # Credits still charged — drafting is the expensive part regardless of send outcome.
    db_session.refresh(user)
    assert user.ai_credits == 100 - outreach_service.settings.OUTREACH_CREDIT_COST


@patch("app.services.outreach.outreach_drafting.draft_outreach", return_value=FAKE_DRAFT)
@patch("app.services.outreach.apollo.enrich_person", return_value={"email": "jane@acme.com", "name": "Jane", "title": "Recruiter"})
@patch("app.services.outreach.apollo.search_people", return_value=[{"id": "p1", "name": "Jane", "title": "Recruiter"}])
def test_draft_only_when_recruiter_found_but_gmail_not_connected(mock_search, mock_enrich, mock_draft, db_session):
    user = _elite_user_with_resume(db_session, "no-gmail@example.com")
    job = _job(db_session, title="Another Role")

    result = outreach_service.initiate_outreach(db_session, user, job)

    assert result.status == OutreachStatus.draft_no_contact


@patch("app.services.outreach.outreach_drafting.draft_outreach", return_value=FAKE_DRAFT)
@patch("app.services.outreach.apollo.search_people")
def test_apollo_failure_falls_back_to_draft_only(mock_search, mock_draft, db_session):
    from app.services.apollo import ApolloAPIError

    mock_search.side_effect = ApolloAPIError("Apollo is down")
    user = _elite_user_with_resume(db_session, "apollo-down@example.com")
    job = _job(db_session, title="Yet Another Role")

    result = outreach_service.initiate_outreach(db_session, user, job)
    assert result.status == OutreachStatus.draft_no_contact


def test_second_request_for_same_job_returns_cached_result_without_recharging(db_session):
    user = _elite_user_with_resume(db_session, "cached@example.com")
    job = _job(db_session, title="Cache Test Role")

    existing = Outreach(
        user_id=user.id, job_id=job.id, email_subject="Cached subject",
        email_body="Cached body", linkedin_msg="Cached note", cv_bullets=[],
        status=OutreachStatus.draft_no_contact,
    )
    db_session.add(existing)
    db_session.commit()

    with patch("app.services.outreach.outreach_drafting.draft_outreach") as mock_draft:
        result = outreach_service.initiate_outreach(db_session, user, job)

    mock_draft.assert_not_called()
    assert result.id == existing.id

    db_session.refresh(user)
    assert user.ai_credits == 100  # untouched — no re-charge


@patch("app.services.outreach.apollo.search_people", return_value=[])
def test_recruiter_contact_reused_across_users_for_same_job(mock_search, db_session):
    """The recruiter cache is per-job, not per-user — a second user targeting
    the same job must not trigger a second Apollo search."""
    job = _job(db_session, title="Shared Job")
    db_session.add(RecruiterContact(job_id=job.id, name="Jane", title="Recruiter", email="jane@acme.com"))
    db_session.commit()

    user = _elite_user_with_resume(db_session, "second-user@example.com")
    with patch("app.services.outreach.outreach_drafting.draft_outreach", return_value=FAKE_DRAFT):
        outreach_service.initiate_outreach(db_session, user, job)

    mock_search.assert_not_called()
