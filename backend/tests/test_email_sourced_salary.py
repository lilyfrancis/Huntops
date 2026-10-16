"""The salary and seniority the alert emails were showing us and we discarded.

Indeed, Jobberman and MyJobMag print the pay on the card — "₦400,000 -
₦600,000 a month" — and the extraction asked for four fields: title, company,
URL, location. So every job that reached the database through an alert mailbox
had no salary, which made a salary filter useless on precisely the supply a
Nigerian user has most of.

Two silent faults in the parser made it worse, and both failed in the
direction that leaves a listing simply unpriced rather than visibly wrong,
which is why neither was noticed.
"""

import uuid

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.user import User
from app.models.user_preference import UserPreference
from app.schemas.ai import ExtractedJobPosting
from app.services import aggregation, preferences
from app.services.salary_parsing import parse_salary


# ---------- the parser ----------

def test_a_monthly_naira_salary_survives_the_word_monthly():
    """The "m" of "monthly" was being read as a millions suffix, so this
    parsed as two hundred and fifty billion naira, failed the plausibility
    ceiling, and was dropped."""
    parsed = parse_salary("₦250,000 monthly")

    assert parsed is not None
    assert parsed["annual_min"] == 3_000_000
    assert parsed["currency"] == "NGN"


def test_an_ordinary_lagos_senior_salary_is_not_treated_as_noise():
    """One global ceiling of ten million was calibrated on dollars. ₦1.5m a
    month is an ordinary senior salary in Lagos and annualises to ₦18m, so
    every Nigerian listing paying above about ₦833k a month arrived with no
    salary on it."""
    assert parse_salary("₦1,500,000 per month")["annual_max"] == 18_000_000
    assert parse_salary("₦18,000,000 - ₦24,000,000")["annual_max"] == 24_000_000


def test_the_ceiling_still_rejects_what_it_exists_to_reject():
    """A phone number and a reference number must not become pay. Nigerian
    mobile numbers are eleven digits, which is what set the NGN ceiling."""
    assert parse_salary("08031234567") is None
    assert parse_salary("Ref 2024 posting") is None


def test_a_gulf_listing_s_currency_is_recognised():
    """Numbers were being parsed and then stored against no currency, which
    is the same as not storing them — a floor is only ever compared within
    one currency, since there is no FX rate anywhere in this system."""
    parsed = parse_salary("AED 28,000 - 34,000 per month")

    assert parsed["currency"] == "AED"
    assert parsed["annual_min"] == 336_000


# ---------- the extraction ----------

def test_the_extractor_is_allowed_to_report_pay_and_work_mode():
    posting = ExtractedJobPosting(
        title="Backend Engineer", company="Paystack", url="https://jobberman.test/1",
        location="Lagos, Nigeria", salary="₦600,000 - ₦900,000 a month", work_mode="hybrid",
    )

    assert posting.salary == "₦600,000 - ₦900,000 a month"
    assert posting.work_mode == "hybrid"


def test_an_alert_that_shows_neither_produces_neither():
    """Not a default of onsite and not an invented figure: an alert that says
    nothing must leave both unknown, because a guess here would be filtered
    on as though it were fact."""
    posting = ExtractedJobPosting(title="Backend Engineer", company="Paystack")

    assert posting.salary is None
    assert posting.work_mode is None


def test_an_email_sourced_job_carries_its_pay_into_comparable_numbers():
    """The synthetic description the email bridge writes says nothing about
    pay or work mode, so both have to come from the posting itself."""
    normalized = aggregation.normalize_common(
        title="Backend Engineer", company="Paystack", url="https://jobberman.test/2",
        location="Lagos, Nigeria",
        description="Sourced from a jobberman job-alert email for the Nigeria market.",
        requirements=[], salary_range="₦600,000 - ₦900,000 a month",
        source="email-jobberman", work_mode="hybrid",
    )

    assert normalized["work_mode"] == "hybrid"
    assert normalized["salary_currency"] == "NGN"
    assert normalized["salary_annual_min"] == 7_200_000
    assert normalized["salary_annual_max"] == 10_800_000


def test_a_listing_the_alert_calls_remote_is_remote():
    """`is_remote` drives eligibility filtering, and the description the
    bridge synthesises would never have mentioned remote work."""
    normalized = aggregation.normalize_common(
        title="Growth Lead", company="Flutterwave", url="https://jobberman.test/3",
        location="Lagos, Nigeria", description="Sourced from a job-alert email.",
        requirements=[], salary_range=None, source="email-jobberman", work_mode="remote",
    )

    assert normalized["is_remote"] is True
    assert normalized["work_mode"] == "remote"


# ---------- seniority ----------

def _job(db, title, level) -> Job:
    job = Job(title=title, description="d" * 50, requirements=[], location="Lagos, Nigeria",
              job_type=JobType.full_time, experience_level=level, source="test",
              source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active)
    db.add(job)
    db.flush()
    return job


def test_seniority_is_its_own_filter(db_session):
    """"Engineer" and "Senior Engineer" are the same role at two levels, and a
    title keyword cannot tell them apart — "engineer" matches both."""
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    prefs = UserPreference(user_id=user.id, experience_levels=["mid", "entry"])
    db_session.add(prefs)
    db_session.flush()

    _job(db_session, "Backend Engineer", ExperienceLevel.mid)
    _job(db_session, "Graduate Engineer", ExperienceLevel.entry)
    _job(db_session, "Senior Backend Manager", ExperienceLevel.senior)

    titles = {job.title for job in preferences.feed_query(db_session, prefs).all()}
    assert titles == {"Backend Engineer", "Graduate Engineer"}


def test_an_unknown_level_is_refused_by_the_api(client):
    from tests.conftest import register_user

    data = register_user(client, email="levels@example.com")
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    resp = client.put("/api/users/preferences", headers=headers,
                      json={"experience_levels": ["wizard"]})

    assert resp.status_code == 422


def test_the_period_the_boards_actually_write():
    """"a month", not "per month". Read as annual, a Lagos listing paying
    ₦600k a month became ₦600k a year — wrong in the one direction that is
    invisible, because the job still appears with a plausible number on it."""
    assert parse_salary("₦400,000 a month")["annual_min"] == 4_800_000
    assert parse_salary("$75,000 a year")["annual_min"] == 75_000
    assert parse_salary("$25 an hour")["annual_min"] == 52_000
    assert parse_salary("£400 a day")["annual_min"] == 104_000
