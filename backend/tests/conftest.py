import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-only-in-ci")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENABLE_SIGNUP", "true")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("STRIPE_PRICE_PRO", "price_test_pro")
os.environ.setdefault("STRIPE_PRICE_ELITE", "price_test_elite")

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
    Base.metadata.create_all(bind=engine)
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
