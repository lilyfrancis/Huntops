import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-only-in-ci")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENABLE_SIGNUP", "true")
os.environ.setdefault("PAYSTACK_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("PAYSTACK_PLAN_PRO", "PLN_test_pro")
os.environ.setdefault("PAYSTACK_PLAN_ELITE", "PLN_test_elite")

import pytest
from fastapi.testclient import TestClient

from app.core.limiter import limiter
from app.db.base import Base, engine, get_db, SessionLocal
from app.main import app

# Rate limits are exercised in production, not in a test suite that legitimately
# registers dozens of users from the same TestClient "IP" within seconds.
limiter.enabled = False


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Tables are built from the models, so the seed rows that migration 0015
    inserts are absent. The allowlist is seeded here to match, or every test
    touching a mailbox would see an empty one and recognise no senders."""
    Base.metadata.create_all(bind=engine)

    from app.core.config import get_settings
    from app.models.alert_sender import AlertSender

    session = SessionLocal()
    session.add_all([
        AlertSender(domain=domain) for domain in get_settings().email_alert_sender_domains_list
    ])
    session.commit()
    session.close()

    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_user(client, email="seeker@example.com", role="job_seeker", **extra):
    payload = {
        "email": email,
        "password": "StrongPass1",
        "full_name": "Test User",
        "role": role,
        **extra,
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
