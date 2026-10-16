"""The funnel that says which setting emptied a feed.

"It is still not showing the email jobs" has a dozen causes spread across
four subsystems — the mailbox never connected, the sender was not recognised,
the extractor returned nothing, the jobs are there but a preference excludes
them — and from the outside every one of them looks the same. Guessing at it
from a description costs a deploy cycle per guess.
"""

import uuid

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType
from app.models.job import Job
from app.models.user import User
from app.models.user_preference import UserPreference
from app.scripts.diagnose_feed import _funnel
from app.services import preferences


def _user(db, email):
    user = User(email=email, password_hash="x", full_name="Amara Obi", role="job_seeker")
    db.add(user)
    db.flush()
    return user


def _job(db, title, **kw):
    defaults = dict(
        description="A description.", requirements=[], location="Lagos, Nigeria",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="email-jobberman", source_url=f"https://x.test/{uuid.uuid4()}",
        status=JobStatus.active, restricted_to="Nigeria", lane=JobLane.engineering,
        work_mode="onsite",
    )
    job = Job(title=title, **{**defaults, **kw})
    db.add(job)
    db.flush()
    return job


def test_every_stage_is_labelled_with_the_setting_that_caused_it(db_session):
    """The labels are the whole product of this. A clause with no name tells
    an operator a number and nothing they can act on."""
    user = _user(db_session, f"{uuid.uuid4()}@example.com")
    prefs = UserPreference(
        user_id=user.id, eligibility=["Nigeria"], work_modes=["remote"],
        lanes=["engineering"], posted_within_days=7,
    )
    db_session.add(prefs)
    db_session.flush()

    labels = [label for label, _clause in preferences.filter_stages(prefs)]

    assert any("job families" in l for l in labels)
    assert any("can apply from" in l for l in labels)
    assert any("work mode" in l for l in labels)
    assert any("posted within 7 days" in l for l in labels)


def test_an_unset_preference_contributes_no_stage(db_session):
    """Empty means no filter, everywhere. A stage for a setting nobody chose
    would report a drop the user cannot undo."""
    user = _user(db_session, f"{uuid.uuid4()}@example.com")
    prefs = UserPreference(user_id=user.id)
    db_session.add(prefs)
    db_session.flush()

    assert preferences.filter_stages(prefs) == []


def test_the_funnel_names_the_filter_that_empties_the_feed(db_session, capsys):
    """The case this exists for: Nigerian jobs are in the pool, the
    eligibility filter admits them, and a work-mode of "remote" removes every
    one — because an onsite Lagos role is not remote and never will be."""
    email = f"{uuid.uuid4()}@example.com"
    user = _user(db_session, email)
    db_session.add(UserPreference(
        user_id=user.id, eligibility=["Nigeria"], work_modes=["remote"],
    ))
    _job(db_session, "Backend Engineer, Lagos")
    _job(db_session, "Data Analyst, Abuja", location="Abuja, Nigeria")
    db_session.commit()

    _funnel(db_session, email)
    out = capsys.readouterr().out

    assert "after can apply from ['Nigeria']" in out
    assert "this is what empties it" in out
    # Named on the line that actually did it, not on the one before.
    culprit = next(line for line in out.splitlines() if "empties it" in line)
    assert "work mode" in culprit


def test_the_funnel_reports_how_much_of_the_feed_came_from_email(db_session, capsys):
    email = f"{uuid.uuid4()}@example.com"
    user = _user(db_session, email)
    db_session.add(UserPreference(user_id=user.id, eligibility=["Nigeria"]))
    _job(db_session, "From Jobberman")
    _job(db_session, "From a board", source="remotive", restricted_to=None,
         is_remote=True, work_mode="remote", location="Worldwide")
    db_session.commit()

    _funnel(db_session, email)
    out = capsys.readouterr().out

    assert "2 job(s) in this feed, 1 of them from email alerts." in out


def test_an_unknown_account_says_so_rather_than_crashing(db_session, capsys):
    _funnel(db_session, "nobody@example.com")

    assert "No account for nobody@example.com." in capsys.readouterr().out


# ---------- choosing a supply pipeline ----------

def test_alerts_only_shows_only_what_the_mailboxes_read(db_session):
    """Measured on the live pool: 9,204 active jobs, 7 from the mailboxes. At
    that ratio no amount of filtering surfaces the Nigerian supply — it is
    outnumbered a thousand to one and sorted below higher-scoring board jobs.
    Filtering narrows a pool; only this chooses which pool."""
    user = _user(db_session, f"{uuid.uuid4()}@example.com")
    prefs = UserPreference(user_id=user.id, sources=["alerts"])
    db_session.add(prefs)
    _job(db_session, "From Jobberman", source="email-jobberman")
    _job(db_session, "From LinkedIn alert", source="email-linkedin")
    _job(db_session, "From Remotive", source="remotive")
    db_session.flush()

    titles = {j.title for j in preferences.feed_query(db_session, prefs).all()}
    assert titles == {"From Jobberman", "From LinkedIn alert"}


def test_boards_only_is_the_other_half(db_session):
    user = _user(db_session, f"{uuid.uuid4()}@example.com")
    prefs = UserPreference(user_id=user.id, sources=["boards"])
    db_session.add(prefs)
    _job(db_session, "From Jobberman", source="email-jobberman")
    _job(db_session, "From Remotive", source="remotive")
    db_session.flush()

    titles = {j.title for j in preferences.feed_query(db_session, prefs).all()}
    assert titles == {"From Remotive"}


def test_picking_both_is_the_same_as_picking_neither(db_session):
    """And emits no stage either way: a line reporting a drop of zero is a
    line the reader cannot act on."""
    user = _user(db_session, f"{uuid.uuid4()}@example.com")
    both = UserPreference(user_id=user.id, sources=["alerts", "boards"])
    db_session.add(both)
    db_session.flush()

    assert preferences.filter_stages(both) == []


def test_an_unknown_source_is_refused(client):
    from tests.conftest import register_user

    data = register_user(client, email="sources@example.com")
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    assert client.put("/api/users/preferences", headers=headers,
                      json={"sources": ["telepathy"]}).status_code == 422


# ---------- noticing that nothing has run ----------

def test_a_pool_that_stopped_filling_says_so(db_session, capsys):
    """The failure mode is an absence. Every scheduled job lives in one
    container, so they stop together and none of them reports it: a pool at
    its daily cap looks healthy long after the last thing was added, and a
    mailbox unread for a fortnight still shows its last sync as "success"."""
    from datetime import datetime, timedelta, timezone

    from app.models.email_sync_run import EmailSyncRun
    from app.models.ingestion_run import IngestionRun
    from app.scripts.diagnose_feed import _freshness

    long_ago = datetime.now(timezone.utc) - timedelta(days=13)
    db_session.add(IngestionRun(source="remotive", status="success", started_at=long_ago))
    db_session.add(EmailSyncRun(status="success", started_at=long_ago))
    db_session.commit()

    _freshness(db_session)
    out = capsys.readouterr().out

    assert "13 day(s) ago" in out
    assert "STALE" in out
    assert "scheduler" in out


def test_a_healthy_pool_raises_no_alarm(db_session, capsys):
    from datetime import datetime, timezone

    from app.models.email_sync_run import EmailSyncRun
    from app.models.ingestion_run import IngestionRun
    from app.scripts.diagnose_feed import _freshness

    now = datetime.now(timezone.utc)
    db_session.add(IngestionRun(source="remotive", status="success", started_at=now))
    db_session.add(EmailSyncRun(status="success", started_at=now))
    db_session.commit()

    _freshness(db_session)

    assert "STALE" not in capsys.readouterr().out


# ---------- recovering from downtime without being asked ----------

def test_catch_up_runs_a_job_that_has_not_run_in_too_long(db_session, monkeypatch):
    """APScheduler holds its jobs in memory, so a missed cron slot is simply
    gone and the next one is tomorrow. Survivable for a lunchtime restart;
    not for the fortnight of downtime that emptied the pool here."""
    from datetime import datetime, timedelta, timezone

    from app.core.config import get_settings
    from app.models.email_sync_run import EmailSyncRun
    from app.models.ingestion_run import IngestionRun
    from app.services import scheduler

    settings = get_settings()
    monkeypatch.setattr(settings, "CATCH_UP_AFTER_HOURS", 30)
    monkeypatch.setattr(scheduler.notifications, "alert_admin", lambda *a, **k: None)

    long_ago = datetime.now(timezone.utc) - timedelta(days=13)
    db_session.add(IngestionRun(source="remotive", status="success", started_at=long_ago))
    db_session.add(EmailSyncRun(status="success", started_at=long_ago))
    db_session.commit()

    ran = []
    assert scheduler.catch_up(run_now=lambda fn: ran.append(fn.__name__)) == ["aggregation", "email sync"]
    assert len(ran) == 2


def test_an_ordinary_restart_catches_up_on_nothing(db_session, monkeypatch):
    """A container restarted during a deploy must not re-run anything. The
    last run is hours old, not days, and that is the normal rhythm."""
    from datetime import datetime, timezone

    from app.core.config import get_settings
    from app.models.email_sync_run import EmailSyncRun
    from app.models.ingestion_run import IngestionRun
    from app.services import scheduler

    monkeypatch.setattr(get_settings(), "CATCH_UP_AFTER_HOURS", 30)
    now = datetime.now(timezone.utc)
    db_session.add(IngestionRun(source="remotive", status="success", started_at=now))
    db_session.add(EmailSyncRun(status="success", started_at=now))
    db_session.commit()

    assert scheduler.catch_up(run_now=lambda fn: None) == []


def test_a_fresh_install_catches_up_so_the_pool_is_not_empty_until_morning(db_session, monkeypatch):
    from app.core.config import get_settings
    from app.services import scheduler

    monkeypatch.setattr(get_settings(), "CATCH_UP_AFTER_HOURS", 30)
    monkeypatch.setattr(scheduler.notifications, "alert_admin", lambda *a, **k: None)

    assert scheduler.catch_up(run_now=lambda fn: None) == ["aggregation", "email sync"]


def test_the_catch_up_can_be_switched_off(db_session, monkeypatch):
    from app.core.config import get_settings
    from app.services import scheduler

    monkeypatch.setattr(get_settings(), "CATCH_UP_AFTER_HOURS", 0)

    assert scheduler.catch_up(run_now=lambda fn: None) == []
