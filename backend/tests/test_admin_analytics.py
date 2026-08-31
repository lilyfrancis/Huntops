from app.models.enums import ExperienceLevel, JobStatus, JobType, OutreachStatus, SubscriptionTier, UserRole
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.user import User
from tests.conftest import auth_headers, register_user


def _make_admin(client, email="analytics-admin@example.com"):
    from app.db.base import SessionLocal

    data = register_user(client, email=email)
    session = SessionLocal()
    user = session.query(User).filter(User.email == email).first()
    user.role = UserRole.admin
    session.commit()
    session.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1"})
    return auth_headers(resp.json()["access_token"])


def test_analytics_requires_admin(client):
    data = register_user(client, email="notadmin@example.com")
    resp = client.get("/api/admin/analytics", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 403


def test_analytics_reports_counts_and_revenue_estimate(client, db_session):
    admin_headers = _make_admin(client)

    pro_user = User(email="pro@example.com", password_hash="x", full_name="Pro", role=UserRole.job_seeker,
                     subscription_tier=SubscriptionTier.pro)
    elite_user = User(email="elite@example.com", password_hash="x", full_name="Elite", role=UserRole.job_seeker,
                       subscription_tier=SubscriptionTier.elite)
    db_session.add_all([pro_user, elite_user])
    db_session.flush()

    job = Job(
        title="Role", description="d", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="remotive", source_url="https://example.com/analytics-job", status=JobStatus.active,
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(Outreach(user_id=elite_user.id, job_id=job.id, cv_bullets=[], status=OutreachStatus.sent))
    db_session.commit()

    resp = client.get("/api/admin/analytics", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["users"]["pro"] >= 1
    assert body["users"]["elite"] >= 1
    assert body["outreach"]["total"] >= 1
    assert body["outreach"]["sent"] >= 1
    assert body["outreach"]["success_rate"] > 0
    from app.services.aggregation import settings as agg_settings  # noqa: F401
    from app.routers.admin import settings as admin_settings

    expected = round(1 * admin_settings.PRO_PRICE_USD + 1 * admin_settings.ELITE_PRICE_USD, 2)
    assert body["revenue"]["monthly_recurring_estimate_usd"] >= expected - 0.01


def test_analytics_ingestion_health_null_when_no_runs(client):
    admin_headers = _make_admin(client, "no-runs-admin@example.com")
    resp = client.get("/api/admin/analytics", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["ingestion_health"]["success_rate"] is None
