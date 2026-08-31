import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType, SubscriptionTier
from app.models.job import Job
from app.models.user import User
from app.services import benchmarks
from tests.conftest import auth_headers, register_user

ADVICE = {
    "verdict": "Worth countering — the offer sits below the market median for this lane.",
    "confidence": "medium",
    "levers": [
        {"lever": "Base salary", "rationale": "The clearest gap against the benchmark."},
        {"lever": "Signing bonus", "rationale": "Easier for them to approve than base."},
    ],
    "counter_script": "Thanks for the offer. Based on what comparable roles are paying, I'd like to discuss base.",
    "if_they_say_no": "Ask what would need to be true at the next review to get there.",
    "watch_outs": ["Don't accept verbally before it's in writing."],
}

OFFER = {
    "role_title": "Senior RevOps Manager",
    "company_name": "Flow Corp",
    "location": "Remote",
    "currency": "USD",
    "base_salary": 110000,
    "has_competing_offer": False,
    "lane": "revops",
}


def _seed_listings(db, count, *, currency="USD", lane=JobLane.revops, low=100_000, step=5_000,
                   level=ExperienceLevel.senior, age_days=10):
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    for i in range(count):
        job = Job(
            title=f"Listing {i}",
            description="A description long enough to be realistic for a benchmark corpus.",
            requirements=["SQL"],
            location="Remote",
            salary_range=f"${low + i * step:,}",
            salary_annual_min=float(low + i * step),
            salary_annual_max=float(low + i * step),
            salary_currency=currency,
            job_type=JobType.full_time,
            experience_level=level,
            status=JobStatus.active,
            source="remotive",
            source_url=f"https://example.com/{uuid.uuid4()}",
            company_name="Corp",
            lane=lane,
        )
        job.created_at = created
        db.add(job)
    db.commit()


def _pro_seeker(client, db_session, email="negotiator@example.com", tier=SubscriptionTier.pro, credits=100):
    data = register_user(client, email=email)
    user = db_session.query(User).filter(User.email == email).first()
    user.subscription_tier = tier
    user.ai_credits = credits
    db_session.commit()
    return data


# ---------- benchmarks: the honesty rules ----------

def test_no_benchmark_below_the_minimum_sample(client, db_session):
    _seed_listings(db_session, benchmarks.MIN_SAMPLE - 1)
    assert benchmarks.benchmark(db_session, lane=JobLane.revops, currency="USD") is None


def test_benchmark_appears_once_the_sample_is_large_enough(client, db_session):
    _seed_listings(db_session, benchmarks.MIN_SAMPLE)
    result = benchmarks.benchmark(db_session, lane=JobLane.revops, currency="USD")
    assert result is not None
    assert result["sample_size"] == benchmarks.MIN_SAMPLE
    assert result["p25"] < result["median"] < result["p75"]


def test_benchmarks_never_mix_currencies(client, db_session):
    """No FX source exists, so a GBP listing must never inform a USD benchmark."""
    _seed_listings(db_session, 12, currency="USD", low=100_000)
    _seed_listings(db_session, 12, currency="GBP", low=40_000)

    usd = benchmarks.benchmark(db_session, lane=JobLane.revops, currency="USD")
    gbp = benchmarks.benchmark(db_session, lane=JobLane.revops, currency="GBP")

    assert usd["sample_size"] == 12 and gbp["sample_size"] == 12
    assert usd["median"] > 100_000
    assert gbp["median"] < 100_000


def test_stale_listings_fall_out_of_the_window(client, db_session):
    _seed_listings(db_session, 15, age_days=benchmarks.LOOKBACK_DAYS + 30)
    assert benchmarks.benchmark(db_session, lane=JobLane.revops, currency="USD") is None


def test_unparsed_salaries_are_excluded_from_the_corpus(client, db_session):
    _seed_listings(db_session, 12)
    # A listing whose salary string never parsed contributes nothing.
    db_session.add(Job(
        title="No salary", description="x" * 60, requirements=[], location="Remote",
        salary_range="Competitive", job_type=JobType.full_time,
        experience_level=ExperienceLevel.senior, status=JobStatus.active, source="remotive",
        source_url=f"https://example.com/{uuid.uuid4()}", company_name="Corp", lane=JobLane.revops,
    ))
    db_session.commit()

    assert benchmarks.benchmark(db_session, lane=JobLane.revops, currency="USD")["sample_size"] == 12


def test_benchmark_widens_the_cohort_before_giving_up(client, db_session):
    """Too few senior listings, but enough in the lane overall — say which was used."""
    _seed_listings(db_session, 12, level=ExperienceLevel.mid)

    result = benchmarks.benchmark_for_offer(
        db_session, lane=JobLane.revops, currency="USD", experience_level=ExperienceLevel.senior
    )
    assert result is not None
    assert result["cohort"] == "lane"


def test_benchmark_for_offer_returns_none_when_nothing_matches(client, db_session):
    assert benchmarks.benchmark_for_offer(
        db_session, lane=JobLane.revops, currency="NGN", experience_level=None
    ) is None


# ---------- the coach ----------

def test_offer_review_grounds_the_prompt_in_real_percentiles(client, db_session):
    _seed_listings(db_session, 20)
    seeker = _pro_seeker(client, db_session)

    with patch("app.services.negotiation.ai_client.complete_json", return_value=ADVICE) as mock_ai:
        resp = client.post("/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER)

    assert resp.status_code == 201, resp.text
    prompt = mock_ai.call_args.kwargs["prompt"]
    assert "MARKET DATA (from 20 real listings" in prompt
    assert "Use ONLY these figures when you reference market rate" in prompt

    body = resp.json()
    assert body["benchmark"]["sample_size"] == 20
    assert body["counter_script"] == ADVICE["counter_script"]


def test_without_data_the_prompt_forbids_inventing_a_market_rate(client, db_session):
    """The whole point: no corpus means tactics only, never a guessed number."""
    seeker = _pro_seeker(client, db_session)

    with patch("app.services.negotiation.ai_client.complete_json", return_value=ADVICE) as mock_ai:
        resp = client.post(
            "/api/negotiation",
            headers=auth_headers(seeker["access_token"]),
            json={**OFFER, "currency": "NGN"},
        )

    assert resp.status_code == 201, resp.text
    prompt = mock_ai.call_args.kwargs["prompt"]
    assert "MARKET DATA: none available" in prompt
    assert "You MUST NOT estimate one" in prompt
    assert resp.json()["benchmark"] is None


def test_the_stored_benchmark_is_frozen_with_the_advice(client, db_session):
    """Advice must not silently re-anchor to new numbers mid-negotiation."""
    _seed_listings(db_session, 20, low=100_000)
    seeker = _pro_seeker(client, db_session)

    with patch("app.services.negotiation.ai_client.complete_json", return_value=ADVICE):
        review_id = client.post(
            "/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER
        ).json()["id"]

    original = client.get(f"/api/negotiation/{review_id}", headers=auth_headers(seeker["access_token"])).json()

    # The corpus shifts hard after the advice was written.
    _seed_listings(db_session, 40, low=300_000)

    refetched = client.get(f"/api/negotiation/{review_id}", headers=auth_headers(seeker["access_token"])).json()
    assert refetched["benchmark"] == original["benchmark"]


def test_free_tier_is_blocked(client, db_session):
    seeker = _pro_seeker(client, db_session, email="free-neg@example.com", tier=SubscriptionTier.free)
    resp = client.post("/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER)
    assert resp.status_code == 403


def test_insufficient_credits_is_rejected_before_any_ai_call(client, db_session):
    seeker = _pro_seeker(client, db_session, email="broke-neg@example.com", credits=2)
    with patch("app.services.negotiation.ai_client.complete_json") as mock_ai:
        resp = client.post("/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER)
    assert resp.status_code == 402
    mock_ai.assert_not_called()


def test_credits_are_charged_only_after_the_call_succeeds(client, db_session):
    from app.services.ai_client import AIResponseError

    seeker = _pro_seeker(client, db_session, email="fail-neg@example.com", credits=100)
    with patch("app.services.negotiation.ai_client.complete_json", side_effect=AIResponseError("boom")):
        resp = client.post("/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER)

    assert resp.status_code == 502
    user = db_session.query(User).filter(User.email == "fail-neg@example.com").first()
    db_session.refresh(user)
    assert user.ai_credits == 100


def test_a_malformed_ai_reply_is_rejected(client, db_session):
    seeker = _pro_seeker(client, db_session)
    with patch("app.services.negotiation.ai_client.complete_json", return_value={**ADVICE, "confidence": "certain"}):
        resp = client.post("/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER)
    assert resp.status_code == 502


def test_reviews_are_scoped_to_their_owner(client, db_session):
    seeker = _pro_seeker(client, db_session, email="owner-neg@example.com")
    intruder = _pro_seeker(client, db_session, email="intruder-neg@example.com")

    with patch("app.services.negotiation.ai_client.complete_json", return_value=ADVICE):
        review_id = client.post(
            "/api/negotiation", headers=auth_headers(seeker["access_token"]), json=OFFER
        ).json()["id"]

    resp = client.get(f"/api/negotiation/{review_id}", headers=auth_headers(intruder["access_token"]))
    assert resp.status_code == 404


def test_coverage_endpoint_reports_what_data_we_actually_hold(client, db_session):
    _seed_listings(db_session, 12, currency="USD")
    _seed_listings(db_session, 3, currency="GBP")
    seeker = _pro_seeker(client, db_session)

    rows = client.get("/api/negotiation/coverage", headers=auth_headers(seeker["access_token"])).json()
    coverage = {row["currency"]: row["listings"] for row in rows}
    assert coverage["USD"] == 12
    assert coverage["GBP"] == 3


# ---------- ingest wiring ----------

def test_employer_posted_salaries_are_parsed_into_the_corpus(client, db_session):
    employer = register_user(client, email="salary-employer@example.com", role="employer", company_name="Acme")
    user = db_session.query(User).filter(User.email == "salary-employer@example.com").first()
    user.is_approved = True
    db_session.commit()

    resp = client.post(
        "/api/jobs",
        headers=auth_headers(employer["access_token"]),
        json={
            "title": "Head of RevOps", "description": "A long enough description for validation.",
            "requirements": ["SQL"], "location": "Remote", "salary_range": "$140,000 - $170,000",
            "job_type": "full_time", "experience_level": "senior",
        },
    )
    assert resp.status_code == 201, resp.text

    job = db_session.query(Job).filter(Job.title == "Head of RevOps").first()
    assert job.salary_annual_min == 140_000
    assert job.salary_annual_max == 170_000
    assert job.salary_currency == "USD"


def test_lane_is_inferred_from_the_role_title_when_not_supplied(client, db_session):
    """Reuses the ingest-time classifier so the cohort matches how the corpus
    was labelled — a second classifier here would compare against a differently
    assembled group."""
    _seed_listings(db_session, 15, lane=JobLane.revops)
    _seed_listings(db_session, 15, lane=JobLane.engineering, low=200_000)
    seeker = _pro_seeker(client, db_session)

    with patch("app.services.negotiation.ai_client.complete_json", return_value=ADVICE):
        resp = client.post(
            "/api/negotiation",
            headers=auth_headers(seeker["access_token"]),
            # no lane sent — must be inferred from "Revenue Operations"
            json={**OFFER, "lane": None, "role_title": "Revenue Operations Manager"},
        )

    benchmark = resp.json()["benchmark"]
    assert benchmark["lane"] == "revops"
    assert benchmark["sample_size"] == 15  # not 30 — engineering excluded
