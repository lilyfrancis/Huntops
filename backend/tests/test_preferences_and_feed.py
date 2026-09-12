"""What a user asked for, and the feed that follows from it."""

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.models.user_preference import UserPreference
from tests.conftest import auth_headers, register_user


def _job(session, *, title="Role", market=None, lane=JobLane.marketing, remote=False,
         job_type=JobType.full_time, source="email-linkedin", ghost_score=None, url=None):
    job = Job(
        title=title, description="d", requirements=[], location=market or "Remote",
        job_type=job_type, experience_level=ExperienceLevel.mid, status=JobStatus.active,
        source=source, source_url=url or f"https://example.com/{title.replace(' ', '-')}",
        lane=lane, market=market, is_remote=remote, ghost_score=ghost_score,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _feed(client, headers, **params):
    resp = client.get("/api/jobs/feed", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------- preferences ----------

def test_signup_captures_market_and_lane_in_one_step(client, db_session):
    """The whole premise: someone in Canada picks Canada + marketing at
    signup and the feed is already theirs the first time they open it."""
    register_user(
        client,
        email="canada-marketer@example.com",
        preferences={"target_markets": ["Canada"], "lanes": ["marketing"]},
    )

    user = db_session.query(User).filter(User.email == "canada-marketer@example.com").one()
    prefs = db_session.query(UserPreference).filter(UserPreference.user_id == user.id).one()
    assert prefs.target_markets == ["Canada"]
    assert prefs.lanes == ["marketing"]
    assert prefs.onboarded_at is not None


def test_signup_without_preferences_leaves_the_user_un_onboarded(client, db_session):
    """An empty row, not a missing one — but onboarded_at stays null so the
    app knows to still ask."""
    register_user(client, email="no-prefs@example.com")

    user = db_session.query(User).filter(User.email == "no-prefs@example.com").one()
    prefs = db_session.query(UserPreference).filter(UserPreference.user_id == user.id).one()
    assert prefs.target_markets == []
    assert prefs.onboarded_at is None


def test_registering_an_unknown_lane_is_rejected(client):
    resp = client.post("/api/auth/register", json={
        "email": "bad-lane@example.com", "password": "StrongPass1", "full_name": "X",
        "role": "job_seeker", "preferences": {"lanes": ["astrology"]},
    })
    assert resp.status_code == 422


def test_a_later_settings_change_does_not_restamp_onboarding(client):
    """onboarded_at is what stops the app asking again; re-stamping it on every
    tweak would make "when did they onboard" meaningless."""
    data = register_user(client, email="restamp@example.com", preferences={"target_markets": ["UK"]})
    headers = auth_headers(data["access_token"])

    first = client.get("/api/users/preferences", headers=headers).json()["onboarded_at"]
    resp = client.put("/api/users/preferences", json={"remote_only": True}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["onboarded_at"] == first
    assert resp.json()["remote_only"] is True
    assert resp.json()["target_markets"] == ["UK"]  # untouched by a partial update


def test_options_only_offer_markets_with_a_live_mailbox(client, db_session):
    """Offering a country with no mailbox behind it promises supply that does
    not exist — the user picks it and gets an empty feed.

    Unauthenticated on purpose: the signup form needs this before the account
    it belongs to exists.
    """
    from tests.test_alert_mailboxes import _seed_mailbox

    _seed_mailbox(db_session, market="Canada")

    resp = client.get("/api/users/preferences/options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["markets"] == ["Canada"]
    assert "marketing" in body["lanes"]
    assert "other" not in body["lanes"]  # a fallback bucket, not something to choose


def test_autopilot_threshold_below_the_floor_is_rejected(client):
    """A threshold of 0 would apply to everything scored. The floor makes that
    unexpressible rather than merely inadvisable."""
    data = register_user(client, email="reckless@example.com")
    resp = client.put(
        "/api/users/preferences",
        json={"autopilot_apply_enabled": True, "autopilot_apply_threshold": 5},
        headers=auth_headers(data["access_token"]),
    )
    assert resp.status_code == 422


# ---------- the feed ----------

def test_feed_filters_to_the_users_market_and_lane(client, db_session):
    data = register_user(
        client, email="feed-filter@example.com",
        preferences={"target_markets": ["Canada"], "lanes": ["marketing"]},
    )
    headers = auth_headers(data["access_token"])

    _job(db_session, title="Canada Marketing Lead", market="Canada", lane=JobLane.marketing)
    _job(db_session, title="UK Marketing Lead", market="UK", lane=JobLane.marketing)
    _job(db_session, title="Canada Backend Engineer", market="Canada", lane=JobLane.engineering)

    assert [i["job"]["title"] for i in _feed(client, headers)] == ["Canada Marketing Lead"]


def test_feed_keeps_market_less_jobs_from_the_global_sources(client, db_session):
    """Aggregated remote listings have no market. They belong to everyone
    rather than nobody — filtering them out would leave a new market's feed
    empty until its mailbox first runs."""
    data = register_user(
        client, email="global-source@example.com", preferences={"target_markets": ["Canada"]}
    )
    _job(db_session, title="Remote Growth Lead", market=None, source="remotive")

    titles = [i["job"]["title"] for i in _feed(client, auth_headers(data["access_token"]))]
    assert titles == ["Remote Growth Lead"]


def test_feed_hides_flagged_ghosts(client, db_session):
    """This feed is what autopilot acts on. Applying to a listing we have
    flagged as probably fake is the one outcome nobody wants."""
    data = register_user(client, email="ghosts@example.com")
    _job(db_session, title="Real Role", ghost_score=5)
    _job(db_session, title="Ghost Role", ghost_score=95)

    titles = [i["job"]["title"] for i in _feed(client, auth_headers(data["access_token"]))]
    assert titles == ["Real Role"]


def test_feed_keeps_unscanned_jobs(client, db_session):
    """Absence of a ghost score isn't evidence of a ghost — it means the
    scanner hasn't reached it yet."""
    data = register_user(client, email="unscanned@example.com")
    _job(db_session, title="Not Yet Scanned", ghost_score=None)

    assert len(_feed(client, auth_headers(data["access_token"]))) == 1


def test_feed_sorts_scored_jobs_above_unscored_ones(client, db_session):
    data = register_user(client, email="sorting@example.com")
    headers = auth_headers(data["access_token"])

    good = _job(db_session, title="Strong Match")
    _job(db_session, title="Unscored")
    user = db_session.query(User).filter(User.email == "sorting@example.com").one()
    db_session.add(JobMatch(user_id=user.id, job_id=good.id, fit_score=91, reason="Great fit"))
    db_session.commit()

    items = _feed(client, headers)
    assert [i["job"]["title"] for i in items] == ["Strong Match", "Unscored"]
    assert items[0]["fit_score"] == 91
    assert items[0]["fit_reason"] == "Great fit"
    assert items[1]["fit_score"] is None


def test_feed_marks_internal_jobs_as_directly_applicable(client, db_session):
    """An aggregated listing lives behind someone else's form. A button
    claiming to apply to it would be a lie."""
    data = register_user(client, email="applicable@example.com")
    _job(db_session, title="Internal Role", source="internal")
    _job(db_session, title="Aggregated Role", source="remotive")

    items = {i["job"]["title"]: i["can_apply_directly"] for i in _feed(client, auth_headers(data["access_token"]))}
    assert items == {"Internal Role": True, "Aggregated Role": False}


def test_feed_reports_jobs_already_applied_to(client, db_session):
    data = register_user(client, email="already-applied@example.com")
    headers = auth_headers(data["access_token"])
    job = _job(db_session, title="Internal Role", source="internal")

    assert client.post("/api/applications", json={"job_id": str(job.id)}, headers=headers).status_code == 201
    assert _feed(client, headers)[0]["applied"] is True


def test_ignore_preferences_shows_the_whole_pool(client, db_session):
    data = register_user(
        client, email="show-all@example.com", preferences={"target_markets": ["Canada"]}
    )
    headers = auth_headers(data["access_token"])
    _job(db_session, title="Canada Role", market="Canada")
    _job(db_session, title="UK Role", market="UK")

    assert len(_feed(client, headers)) == 1
    assert len(_feed(client, headers, ignore_preferences=True)) == 2


def test_empty_preferences_mean_no_filter_not_an_empty_feed(client, db_session):
    """Half-finished onboarding must degrade to the full feed. The opposite
    failure — a blank dashboard — looks like a broken product."""
    data = register_user(client, email="unfiltered@example.com")
    _job(db_session, title="Canada Role", market="Canada")
    _job(db_session, title="UK Role", market="UK")

    assert len(_feed(client, auth_headers(data["access_token"]))) == 2


# ---------- only offer job families that have supply ----------

def _jobs(session, lane, count, *, status=JobStatus.active):
    for i in range(count):
        session.add(Job(
            title=f"{lane.value} role {i}", description="d", requirements=[], location="Remote",
            job_type=JobType.full_time, experience_level=ExperienceLevel.mid, status=status,
            source="email-linkedin", source_url=f"https://example.com/{lane.value}-{i}-{status.value}",
            lane=lane,
        ))
    session.commit()


def test_a_lane_with_almost_no_jobs_is_not_offered(client, db_session):
    """Offering a job family with one listing behind it is a promise of supply
    that does not exist — the user picks it and gets a feed of one."""
    from app.services.preferences import MIN_JOBS_FOR_LANE

    _jobs(db_session, JobLane.marketing, MIN_JOBS_FOR_LANE)
    _jobs(db_session, JobLane.finance, MIN_JOBS_FOR_LANE - 1)

    lanes = client.get("/api/users/preferences/options").json()["lanes"]
    assert "marketing" in lanes
    assert "finance" not in lanes


def test_lanes_are_offered_busiest_first(client, db_session):
    """The ordering is an honest signal of where the depth actually is."""
    from app.services.preferences import MIN_JOBS_FOR_LANE

    _jobs(db_session, JobLane.marketing, MIN_JOBS_FOR_LANE)
    _jobs(db_session, JobLane.sales, MIN_JOBS_FOR_LANE + 10)

    lanes = client.get("/api/users/preferences/options").json()["lanes"]
    assert lanes[0] == "sales"


def test_an_empty_pool_still_offers_every_lane(client):
    """A fresh deployment has no supply anywhere. An empty picker reads as
    broken, and the pool is too thin to say anything either way."""
    lanes = client.get("/api/users/preferences/options").json()["lanes"]
    assert "engineering" in lanes and "marketing" in lanes
    assert "other" not in lanes  # a fallback bucket, never something to choose


def test_closed_jobs_do_not_count_as_supply(client, db_session):
    from app.services.preferences import MIN_JOBS_FOR_LANE

    _jobs(db_session, JobLane.marketing, MIN_JOBS_FOR_LANE)
    _jobs(db_session, JobLane.hr, MIN_JOBS_FOR_LANE, status=JobStatus.closed)

    lanes = client.get("/api/users/preferences/options").json()["lanes"]
    assert "marketing" in lanes
    assert "hr" not in lanes
