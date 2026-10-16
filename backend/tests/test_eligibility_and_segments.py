"""Filters a job board is expected to have, and the one it was missing.

The feed could narrow by market and by lane, and nothing else. Market is
where a listing's supply came from — which alert mailbox — so a person in
Lagos asking for Nigerian work got "jobs that arrived through the Nigeria
mailbox" rather than "jobs I can apply for from Nigeria". The two overlap by
accident and diverge in exactly the cases that matter: a fully remote role
open to anyone is the first thing that reader wants and the first thing that
filter drops.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services import aggregation, geo, preferences


def _user(db) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db.add(user)
    db.flush()
    return user


def _prefs(db, user, **kw) -> UserPreference:
    prefs = UserPreference(user_id=user.id, **kw)
    db.add(prefs)
    db.flush()
    return prefs


def _job(db, title, **kw) -> Job:
    defaults = dict(
        description="A description long enough to look real.", requirements=[],
        location="Remote", job_type=JobType.full_time, experience_level=ExperienceLevel.senior,
        source="test", source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active,
    )
    job = Job(title=title, **{**defaults, **kw})
    db.add(job)
    db.flush()
    return job


def _titles(db, prefs) -> set[str]:
    return {job.title for job in preferences.feed_query(db, prefs).all()}


# ---------- the vocabulary ----------

@pytest.mark.parametrize("text,expected", [
    ("Lagos, Nigeria", "Nigeria"),
    ("Remote - Canada", "Canada"),
    ("Anywhere in Europe", "Europe"),
    ("USA", "US"),
    ("Toronto, ON", "Canada"),
    ("EMEA", "EMEA"),
    # Open to everybody is the absence of a place, not a place of its own.
    ("Worldwide", None),
    ("Remote", None),
    ("Anywhere", None),
    ("Atlantis", None),
    ("", None),
])
def test_a_board_s_location_string_resolves_to_a_place(text, expected):
    assert geo.canonical(text) == expected


def test_a_place_inside_a_stated_region_still_counts():
    """A remote role advertised for EMEA is open to somebody in Lagos. This is
    the single rule that makes "remote global, applicable to Nigeria" a thing
    the query can express."""
    assert geo.admits("EMEA", "Nigeria") is True
    assert geo.admits("Africa", "Nigeria") is True
    assert geo.admits(None, "Nigeria") is True
    assert geo.admits("US", "Nigeria") is False
    assert geo.admits("Canada", "Nigeria") is False


# ---------- eligibility, which is not market ----------

def test_picking_nigeria_means_what_a_nigerian_can_apply_for(db_session):
    user = _user(db_session)
    prefs = _prefs(db_session, user, eligibility=["Nigeria"])

    _job(db_session, "Open to anyone", is_remote=True, restricted_to=None, work_mode="remote")
    _job(db_session, "Remote EMEA", is_remote=True, restricted_to="EMEA", work_mode="remote")
    _job(db_session, "Onsite in Lagos", location="Lagos, Nigeria", work_mode="onsite")
    _job(db_session, "US only", is_remote=True, restricted_to="US", work_mode="remote")
    _job(db_session, "Onsite in Berlin", location="Berlin, Germany", work_mode="onsite")

    assert _titles(db_session, prefs) == {"Open to anyone", "Remote EMEA", "Onsite in Lagos"}


def test_remote_canada_is_a_different_request_from_nigeria(db_session):
    """The two selections the user described as distinct: "I want remote
    Canada" must not return the same list as "I want Nigeria"."""
    user = _user(db_session)
    prefs = _prefs(db_session, user, eligibility=["Canada"], work_modes=["remote"])

    _job(db_session, "Remote Canada", is_remote=True, restricted_to="Canada", work_mode="remote")
    _job(db_session, "Onsite Toronto", location="Toronto, ON", work_mode="onsite")
    _job(db_session, "Remote Nigeria", is_remote=True, restricted_to="Nigeria", work_mode="remote")

    assert _titles(db_session, prefs) == {"Remote Canada"}


def test_an_eligibility_nobody_recognises_does_not_empty_the_feed(db_session):
    """Degrading to the full feed is the right failure: a blank screen reads as
    the product being broken, and the user has no way to tell which of their
    settings did it."""
    user = _user(db_session)
    prefs = _prefs(db_session, user, eligibility=["Atlantis"])
    _job(db_session, "Something", is_remote=True)

    assert _titles(db_session, prefs) == {"Something"}


def test_no_eligibility_set_means_no_narrowing(db_session):
    user = _user(db_session)
    prefs = _prefs(db_session, user)
    _job(db_session, "US only", is_remote=True, restricted_to="US")

    assert _titles(db_session, prefs) == {"US only"}


def test_market_and_eligibility_are_not_the_same_filter(db_session):
    """The bug this whole change exists for. The global boards carry no
    market, so a market filter drops every remote listing in the pool — which
    is most of it, and all of the listings a Nigerian can actually take."""
    user = _user(db_session)
    remote = _job(db_session, "Remote, open to all", is_remote=True, market=None)

    by_market = _prefs(db_session, _user(db_session), target_markets=["Nigeria"])
    by_eligibility = _prefs(db_session, user, eligibility=["Nigeria"])

    # Market keeps it only because null markets are deliberately exempted;
    # eligibility keeps it on its own terms, which survives a tighter market.
    assert remote.title in _titles(db_session, by_market)
    assert remote.title in _titles(db_session, by_eligibility)

    _job(db_session, "Nigeria mailbox, US only", market="Nigeria", is_remote=True, restricted_to="US")
    assert "Nigeria mailbox, US only" in _titles(db_session, by_market)
    assert "Nigeria mailbox, US only" not in _titles(db_session, by_eligibility)


# ---------- work mode ----------

def test_hybrid_is_not_remote(db_session):
    """A boolean cannot say "three days in the office", which is why the
    column exists. Somebody filtering for remote work cannot take a hybrid
    role and was being shown it anyway."""
    user = _user(db_session)
    prefs = _prefs(db_session, user, work_modes=["remote"])

    _job(db_session, "Fully remote", is_remote=True, work_mode="remote")
    _job(db_session, "Hybrid Lagos", is_remote=True, location="Hybrid - Lagos", work_mode="hybrid")
    _job(db_session, "Onsite", work_mode="onsite")

    assert _titles(db_session, prefs) == {"Fully remote"}


def test_a_job_ingested_before_the_column_existed_is_not_hidden(db_session):
    """Null is not evidence of a work mode. Hiding these would empty the feed
    of everything older than this release the moment anybody touched the
    filter."""
    user = _user(db_session)
    prefs = _prefs(db_session, user, work_modes=["onsite"])
    _job(db_session, "Legacy", work_mode=None)

    assert _titles(db_session, prefs) == {"Legacy"}


# ---------- salary ----------

def test_a_salary_floor_drops_only_what_it_can_actually_compare(db_session):
    user = _user(db_session)
    prefs = _prefs(db_session, user, salary_min_annual=10_000_000, salary_currency="NGN")

    _job(db_session, "Pays enough", salary_annual_max=18_000_000, salary_currency="NGN")
    _job(db_session, "Pays too little", salary_annual_max=4_000_000, salary_currency="NGN")
    # Most listings publish nothing. A floor that hid them all would discard
    # the majority of the pool to enforce a number nobody stated.
    _job(db_session, "Says nothing", salary_annual_max=None)
    # No FX rate anywhere in this system, so this is unknowable rather than low.
    _job(db_session, "Other currency", salary_annual_max=90_000, salary_currency="USD")

    assert _titles(db_session, prefs) == {"Pays enough", "Says nothing", "Other currency"}


def test_a_floor_without_a_currency_does_nothing(db_session):
    """Both or neither: 80000 is meaningless without knowing whether that is
    dollars or naira, and guessing would be worse than not filtering."""
    user = _user(db_session)
    prefs = _prefs(db_session, user, salary_min_annual=500_000, salary_currency=None)
    _job(db_session, "Cheap", salary_annual_max=1000, salary_currency="USD")

    assert _titles(db_session, prefs) == {"Cheap"}


# ---------- recency and exact role ----------

def test_how_many_days_ago(db_session):
    user = _user(db_session)
    prefs = _prefs(db_session, user, posted_within_days=3)

    _job(db_session, "Today")
    old = _job(db_session, "Three weeks ago")
    old.created_at = datetime.now(timezone.utc) - timedelta(days=21)
    db_session.flush()

    assert _titles(db_session, prefs) == {"Today"}


def test_the_exact_role_not_just_the_family(db_session):
    """`engineering` covers QA, SRE and mobile, so a React developer asking
    for React had no way to say so — which is what made a feed of "Senior
    Backend Manager" look like broken matching rather than an unset filter."""
    user = _user(db_session)
    prefs = _prefs(db_session, user, title_keywords=["react", "frontend"])

    _job(db_session, "React Developer")
    _job(db_session, "Senior Frontend Engineer")
    _job(db_session, "Senior Backend Manager")

    assert _titles(db_session, prefs) == {"React Developer", "Senior Frontend Engineer"}


def test_filters_compose_rather_than_replace_each_other(db_session):
    """Indeed-style stacking: a country, then a work mode, then a floor. Each
    one narrows what the last one left."""
    user = _user(db_session)
    prefs = _prefs(
        db_session, user,
        eligibility=["Nigeria"], work_modes=["remote"],
        salary_min_annual=5_000_000, salary_currency="NGN", title_keywords=["engineer"],
    )

    _job(db_session, "Remote Engineer, pays well", is_remote=True, work_mode="remote",
         salary_annual_max=12_000_000, salary_currency="NGN")
    _job(db_session, "Remote Engineer, US only", is_remote=True, work_mode="remote",
         restricted_to="US", salary_annual_max=12_000_000, salary_currency="NGN")
    _job(db_session, "Remote Manager", is_remote=True, work_mode="remote",
         salary_annual_max=12_000_000, salary_currency="NGN")
    _job(db_session, "Remote Engineer, pays little", is_remote=True, work_mode="remote",
         salary_annual_max=900_000, salary_currency="NGN")

    assert _titles(db_session, prefs) == {"Remote Engineer, pays well"}


# ---------- what ingest now records ----------

def test_a_remote_only_board_s_location_field_is_an_eligibility_statement(db_session):
    """Remotive puts the country a candidate must be in where other boards put
    an address. Inferred from the text alone, a fully remote role open to
    Canadians arrived as an onsite Toronto job — and eligibility filtering is
    built on `is_remote`, so that one mistake decided whether anybody abroad
    ever saw it."""
    normalized = aggregation.normalize_remotive({
        "title": "Backend Engineer",
        "company_name": "Acme",
        "url": "https://remotive.test/1",
        "candidate_required_location": "Canada",
        "description": "Work with us.",
        "tags": [],
    })

    assert normalized["is_remote"] is True
    assert normalized["work_mode"] == "remote"
    assert normalized["restricted_to"] == "Canada"


def test_worldwide_is_recorded_as_no_restriction_at_all(db_session):
    normalized = aggregation.normalize_remotive({
        "title": "Backend Engineer", "company_name": "Acme",
        "url": "https://remotive.test/2",
        "candidate_required_location": "Worldwide",
        "description": "Work with us.", "tags": [],
    })

    assert normalized["restricted_to"] is None
    assert normalized["is_remote"] is True


def test_a_listing_that_says_both_remote_and_hybrid_is_hybrid(db_session):
    assert aggregation.infer_work_mode("Remote", "Hybrid, two days in the Lagos office", True) == "hybrid"
    assert aggregation.infer_work_mode("Remote", "Work from anywhere", True) == "remote"
    assert aggregation.infer_work_mode("Lagos", "In our office", False) == "onsite"


def test_a_description_merely_naming_a_country_is_not_a_restriction(db_session):
    """Half of all listings name a head office. Treating that as "you must be
    here" would restrict most of the pool to wherever the company banks."""
    assert aggregation.infer_restriction("Not specified", "Our head office is in the United States.") is None
    assert aggregation.infer_restriction("Not specified", "This role is US-only.") == "US"


# ---------- the API around them ----------

def _auth(client, email):
    from tests.conftest import register_user
    data = register_user(client, email=email)
    return {"Authorization": f"Bearer {data['access_token']}"}


def test_saving_the_new_filters_round_trips(client):
    headers = _auth(client, "segments@example.com")
    resp = client.put("/api/users/preferences", headers=headers, json={
        "eligibility": ["lagos", "Nigeria", "remote - canada"],
        "work_modes": ["remote", "hybrid"],
        "title_keywords": [" React Developer ", "react developer"],
        "salary_min_annual": 8_000_000,
        "salary_currency": "ngn",
        "posted_within_days": 7,
    })

    assert resp.status_code == 200, resp.text
    saved = resp.json()
    # Canonicalised and deduplicated on the way in, so the stored value is the
    # one the query understands rather than whatever the user typed.
    assert saved["eligibility"] == ["Nigeria", "Canada"]
    assert saved["work_modes"] == ["remote", "hybrid"]
    assert saved["title_keywords"] == ["React Developer"]
    assert saved["salary_currency"] == "NGN"
    assert saved["posted_within_days"] == 7


def test_a_place_we_cannot_resolve_is_refused_rather_than_dropped(client):
    """Silently dropping it would widen the feed back to everything, which
    reads as the filter being ignored instead of rejected."""
    headers = _auth(client, "unknown-place@example.com")
    resp = client.put("/api/users/preferences", headers=headers, json={"eligibility": ["Atlantis"]})

    assert resp.status_code == 422
    assert "Atlantis" in resp.text


def test_a_recency_we_do_not_offer_is_refused(client):
    headers = _auth(client, "recency@example.com")
    assert client.put("/api/users/preferences", headers=headers,
                      json={"posted_within_days": 0}).status_code == 422
    assert client.put("/api/users/preferences", headers=headers,
                      json={"posted_within_days": 365}).status_code == 422


def test_the_picker_is_told_what_it_may_offer(client):
    options = client.get("/api/users/preferences/options").json()

    assert "Nigeria" in options["eligibility"]
    assert options["work_modes"] == ["remote", "hybrid", "onsite"]
    assert options["recency_choices"] == [1, 3, 7, 14, 30]


def test_the_feed_pages(client, db_session):
    """Next is offset paging over what is already in the pool — it costs
    nothing, unlike scoring, which is why it can be a button."""
    headers = _auth(client, "paging@example.com")
    for i in range(7):
        _job(db_session, f"Role {i}", is_remote=True)
    db_session.commit()

    first = client.get("/api/jobs/feed?limit=3", headers=headers).json()
    second = client.get("/api/jobs/feed?limit=3&skip=3", headers=headers).json()

    assert len(first) == 3 and len(second) == 3
    assert {item["job"]["id"] for item in first}.isdisjoint({item["job"]["id"] for item in second})


def test_the_home_market_boost_understands_regions(db_session):
    """`restricted_to` is no longer only a country name, and the boost was an
    equality test. A remote role advertised for EMEA is open to somebody in
    Nigeria, and string equality called it ineligible — withholding the boost
    from exactly the listings the boost exists to surface."""
    from app.schemas.ai import JobFitScore
    from app.services import matching

    emea = _job(db_session, "Remote EMEA", is_remote=True, restricted_to="EMEA")
    us_only = _job(db_session, "Remote US only", is_remote=True, restricted_to="US")
    scores = [
        JobFitScore(job_index=0, overall_score=70, skills_score=70,
                    experience_score=70, location_score=70, reason="r"),
        JobFitScore(job_index=1, overall_score=70, skills_score=70,
                    experience_score=70, location_score=70, reason="r"),
    ]

    from app.models.resume import Resume
    resume = Resume(user_id=None, raw_text="x", parsed_skills=["Python"], experience_years=5)

    def fake_complete(system, prompt, model, max_tokens, feature="unknown"):
        return [s.model_dump() for s in scores]

    original = matching.ai_client.complete_json
    matching.ai_client.complete_json = fake_complete
    try:
        results = matching.score_jobs(resume, [emea, us_only], "Nigeria")
    finally:
        matching.ai_client.complete_json = original

    boosted = {job.title: applied for job, _score, applied in results}
    assert boosted["Remote EMEA"] is True
    assert boosted["Remote US only"] is False
