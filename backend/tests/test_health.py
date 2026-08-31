from app.db.base import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import auth_headers, register_user


def _make_admin(client, email="health-admin@example.com"):
    data = register_user(client, email=email)
    session = SessionLocal()
    user = session.query(User).filter(User.email == email).first()
    user.role = UserRole.admin
    session.commit()
    session.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1"})
    return auth_headers(resp.json()["access_token"])


def test_public_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_detailed_health_requires_admin(client):
    data = register_user(client, email="nothealthadmin@example.com")
    resp = client.get("/api/health/detailed", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 403


def test_detailed_health_reports_all_integrations(client):
    admin_headers = _make_admin(client)
    resp = client.get("/api/health/detailed", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("database", "stripe", "anthropic", "apollo", "gmail_oauth", "smtp", "scheduler"):
        assert key in body
    assert body["scheduler"]["running"] is False  # scheduler doesn't start in the test environment
