from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def _make_admin(client, email="admin2@example.com"):
    from app.db.base import SessionLocal
    from app.models.enums import UserRole
    from app.models.user import User

    data = register_user(client, email=email)
    session = SessionLocal()
    user = session.query(User).filter(User.email == email).first()
    user.role = UserRole.admin
    session.commit()
    session.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1"})
    return auth_headers(resp.json()["access_token"])


@patch("app.routers.admin.ingest_all", return_value={"remotive": {"fetched": 5, "inserted": 3, "status": "success"}})
def test_admin_can_trigger_aggregation(mock_ingest, client):
    headers = _make_admin(client)
    resp = client.post("/api/admin/jobs/aggregate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["remotive"]["inserted"] == 3
    mock_ingest.assert_called_once()


def test_non_admin_cannot_trigger_aggregation(client):
    data = register_user(client, email="regular@example.com")
    resp = client.post("/api/admin/jobs/aggregate", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 403


def test_admin_can_list_aggregation_runs(client):
    from app.db.base import SessionLocal
    from app.models.ingestion_run import IngestionRun

    session = SessionLocal()
    session.add(IngestionRun(source="remotive", status="success", fetched_count=10, inserted_count=4))
    session.commit()
    session.close()

    headers = _make_admin(client, email="admin3@example.com")
    resp = client.get("/api/admin/jobs/aggregation-runs", headers=headers)
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["source"] == "remotive"
    assert runs[0]["inserted_count"] == 4
