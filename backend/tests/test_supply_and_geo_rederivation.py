"""Why a Nigerian user was still being shown US-only roles.

The eligibility filter reads three columns, and every job already in the
database was written by the old inference that got all three wrong. The
filter was correct; the data under it was not — which is indistinguishable
from the filter being broken if you are looking at a feed rather than a
table.

`restricted_to` is the one that bites. It only ever fired on "US only", "UK
only" and "EU only", so almost every listing came out null — and null means
"open to everybody" to the query.
"""

import uuid

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.user import User
from app.models.user_preference import UserPreference
from app.scripts.rederive_job_geo import rederive
from app.services import preferences


def _job(db, **kw) -> Job:
    defaults = dict(
        title="A role", description="A description.", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid, source="test",
        source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active,
    )
    job = Job(**{**defaults, **kw})
    db.add(job)
    db.commit()
    return job


def test_a_us_only_remote_job_stops_being_open_to_everybody(db_session):
    """Stored as (remote, no restriction) by the old inference, which the
    filter reads as "anyone may apply". This is the row that put USA in a
    Nigerian user's feed."""
    job = _job(db_session, title="Remote US role", location="USA",
               is_remote=True, restricted_to=None, source="remotive")

    rederive()
    db_session.expire_all()

    assert db_session.get(Job, job.id).restricted_to == "US"


def test_a_remote_only_board_s_listing_is_marked_remote(db_session):
    """Remotive puts the eligible country where other boards put an address,
    so inferring remoteness from that text said no — and a fully remote role
    open to Canadians was stored as an onsite Toronto job."""
    job = _job(db_session, location="Canada", is_remote=False, source="remotive")

    rederive()
    db_session.expire_all()
    refreshed = db_session.get(Job, job.id)

    assert refreshed.is_remote is True
    assert refreshed.work_mode == "remote"
    assert refreshed.restricted_to == "Canada"


def test_a_genuinely_global_listing_stays_global(db_session):
    job = _job(db_session, location="Worldwide", is_remote=True, source="remoteok")

    rederive()
    db_session.expire_all()
    refreshed = db_session.get(Job, job.id)

    assert refreshed.restricted_to is None
    assert refreshed.is_remote is True


def test_a_dry_run_writes_nothing(db_session):
    job = _job(db_session, location="USA", is_remote=True, restricted_to=None, source="remotive")

    summary = rederive(dry_run=True)
    db_session.expire_all()

    assert summary["changed"] == 1
    assert summary["written"] is False
    assert db_session.get(Job, job.id).restricted_to is None


def test_after_re_deriving_the_nigeria_filter_behaves(db_session):
    """End to end: the same three jobs, the same preference, before and after."""
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    prefs = UserPreference(user_id=user.id, eligibility=["Nigeria"])
    db_session.add(prefs)
    db_session.commit()

    _job(db_session, title="Remote US only", location="USA", is_remote=True,
         restricted_to=None, source="remotive")
    _job(db_session, title="Remote worldwide", location="Worldwide", is_remote=True,
         restricted_to=None, source="remoteok")
    _job(db_session, title="Lagos onsite", location="Lagos, Nigeria", is_remote=False,
         restricted_to=None, source="email-jobberman")

    before = {j.title for j in preferences.feed_query(db_session, prefs).all()}
    # The US role is admitted because its restriction was never recorded.
    assert "Remote US only" in before

    rederive()
    db_session.expire_all()

    after = {j.title for j in preferences.feed_query(db_session, prefs).all()}
    assert after == {"Remote worldwide", "Lagos onsite"}


# ---------- the supply report ----------

def test_the_supply_report_separates_the_two_pipelines(client, db_session):
    """"Is it pulling from my alerts" has to be answerable as a number. A sync
    run reports what it read, not what survived into the pool."""
    from tests.conftest import register_user

    _job(db_session, title="From Jobberman", source="email-jobberman", market="Nigeria")
    _job(db_session, title="From LinkedIn", source="email-linkedin", market="Nigeria")
    _job(db_session, title="From a board", source="remotive")

    register_user(client, email="admin-supply@example.com")
    from app.db.base import SessionLocal
    from app.models.enums import UserRole
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.email == "admin-supply@example.com").first()
        admin.role = UserRole.admin
        session.commit()
    finally:
        session.close()

    login = client.post("/api/auth/login",
                        json={"email": "admin-supply@example.com", "password": "StrongPass1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    body = client.get("/api/admin/supply", headers=headers).json()

    assert body["totals"]["from_alert_mailboxes"] == 2
    assert body["totals"]["from_job_boards"] == 1
    assert {row["name"] for row in body["by_source"]} == {
        "email-jobberman", "email-linkedin", "remotive"
    }
    assert {row["name"] for row in body["by_market"]} == {"Nigeria", "(none)"}


# ---------- which board an alert came from ----------

def test_a_board_that_sends_from_two_domains_is_still_one_board():
    """The slug picks the search URL used for an alert with no direct link,
    and that URL doubles as the dedupe key — so "indeedemail" would have
    given an Indeed job a LinkedIn search URL and the source
    "email-indeedemail"."""
    from app.services.alert_senders import detect_provider

    assert detect_provider("Indeed <donotreply@indeedemail.com>") == "indeed"
    assert detect_provider("Indeed <alert@indeed.com>") == "indeed"


def test_the_mailbox_s_own_address_is_not_what_is_checked():
    """The allowlist reads the From header, never the recipient. An operator
    mailbox on any domain works; mail *from* that domain is not a job alert."""
    from app.services.alert_senders import detect_provider

    assert detect_provider("Alerts <alerts@huntops.site>") is None
    assert detect_provider("LinkedIn <jobalerts-noreply@linkedin.com>") == "linkedin"


def test_a_subdomain_still_resolves_to_its_board():
    from app.services.alert_senders import detect_provider

    assert detect_provider("Jobberman <info@mail.jobberman.com>") == "jobberman"


def test_employer_side_mail_on_an_allowed_domain_is_still_refused():
    """These are notifications to a company that somebody applied to *their*
    posting. They match the allowlist, cost an AI call, and can be read as a
    vacancy that does not exist."""
    from app.services.alert_senders import detect_provider

    assert detect_provider("Indeed <employers-noreply@indeed.com>") is None
