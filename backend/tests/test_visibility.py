"""What a locked viewer can see — and, more importantly, cannot.

The concierge only works if the user cannot trivially do it themselves.
Showing the company beside a link-free listing is an invitation to search
for it, and the work we are charging to remove is then a web search away.
"""

import pytest

from app.models.enums import SubscriptionTier, UserRole
from app.models.user import User
from app.schemas.job import job_out_for
from app.services import visibility
from tests.conftest import auth_headers, register_user
from tests.test_outreach import _job


@pytest.fixture
def external(db_session):
    from app.models.enums import JobStatus

    # Active, or feed_query filters it out and the feed test proves nothing.
    return _job(db_session, title="Director of Sales, New Logo", source="weworkremotely",
                source_url="https://weworkremotely.com/jobs/1", company_name="Temporal Technologies",
                description="Temporal Technologies is hiring a Director of Sales.",
                salary_range="$120k – $160k", status=JobStatus.active)


def _seeker(db_session, tier=SubscriptionTier.free, email="locked@example.com"):
    from app.core.security import hash_password

    user = User(email=email, password_hash=hash_password("StrongPass1"), full_name="Ada Seeker",
                role=UserRole.job_seeker, subscription_tier=tier, ai_credits=100)
    db_session.add(user)
    db_session.commit()
    return user


# ---------- what is hidden ----------

def test_a_free_user_cannot_see_the_company_or_the_description(db_session, external):
    out = job_out_for(external, _seeker(db_session), set())

    assert out.locked is True
    assert out.company_name is None
    assert "Temporal" not in out.description
    assert out.source_url is None
    assert out.source == "hidden"


def test_the_salary_is_shown_because_it_is_the_reason_to_unlock(db_session, external):
    """Hiding it would make every locked row look identical, and the salary
    is the single strongest argument for paying."""
    out = job_out_for(external, _seeker(db_session), set())

    assert out.salary_range == "$120k – $160k"
    assert out.location == external.location
    assert out.is_remote == external.is_remote


def test_the_title_keeps_its_shape_but_not_its_words(db_session, external):
    """Enough to tell a sales role from an engineering one — which is what
    makes it worth unlocking — and not enough to paste into a search box."""
    out = job_out_for(external, _seeker(db_session), set())

    assert out.title.startswith("Director of")
    assert "New Logo" not in out.title
    assert "•" in out.title


# ---------- who is not locked ----------

def test_even_elite_is_locked_until_they_unlock(db_session, external):
    """Credits are the gate for everyone now. A plan is how many credits you
    get, not a different set of walls — otherwise a paying customer meets
    one they cannot pay past, which is where churn comes from."""
    out = job_out_for(external, _seeker(db_session, SubscriptionTier.elite), set())
    assert out.locked is True


def test_a_job_already_applied_for_is_unlocked(db_session, external):
    """They committed and were charged. It is theirs to see."""
    out = job_out_for(external, _seeker(db_session), {external.id})
    assert out.locked is False
    assert out.company_name == "Temporal Technologies"


def test_internal_jobs_are_never_locked(db_session):
    """Nothing to route around: the user applies to those through us anyway."""
    internal = _job(db_session, title="Internal Role", source="internal", company_name="Acme")
    out = job_out_for(internal, _seeker(db_session), set())
    assert out.locked is False
    assert out.company_name == "Acme"


def test_admins_and_employers_see_everything(db_session, external):
    admin = _seeker(db_session, email="admin-vis@example.com")
    admin.role = UserRole.admin
    db_session.commit()
    assert job_out_for(external, admin, set()).locked is False


# ---------- the hole this would otherwise leave ----------

def test_the_single_job_route_redacts_too(client, db_session, external):
    """It took no user at all, so everything the feed withheld could be read
    straight back out of it by id — which made the feed's redaction
    decorative."""
    register_user(client, email="byid@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "byid@example.com", "password": "StrongPass1"}).json()

    body = client.get(f"/api/jobs/{external.id}",
                      headers=auth_headers(token["access_token"])).json()

    assert body["locked"] is True
    assert body["company_name"] is None
    assert body["source_url"] is None


def test_an_anonymous_reader_gets_the_locked_version_not_a_401(client, db_session, external):
    body = client.get(f"/api/jobs/{external.id}").json()
    assert body["locked"] is True
    assert body["company_name"] is None


def test_the_feed_redacts_every_row(client, db_session, external):
    register_user(client, email="feedvis@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "feedvis@example.com", "password": "StrongPass1"}).json()

    rows = client.get("/api/jobs/feed", headers=auth_headers(token["access_token"])).json()
    external_rows = [r for r in rows if r["job"]["locked"]]

    assert external_rows, "the external job should be in the feed and locked"
    for row in external_rows:
        assert row["job"]["company_name"] is None
        assert row["job"]["source_url"] is None


def test_masking_leaves_a_one_word_title_alone(db_session):
    """Nothing to protect: one generic word with no company is not a job
    anyone can find."""
    assert visibility.mask_title("Engineer") == "Engineer"
