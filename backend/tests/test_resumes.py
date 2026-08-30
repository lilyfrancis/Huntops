import io
from unittest.mock import patch

from app.schemas.ai import ParsedResume
from tests.conftest import auth_headers, register_user

FAKE_PARSED = ParsedResume(
    skills=["Python", "SQL", "Salesforce"],
    experience_years=6,
    education="B.Sc. Computer Science",
    summary="Experienced backend engineer with RevOps tooling background.",
    achievements=["Built an internal automation platform used by 40 reps"],
)


def _upload(client, headers, content=b"A" * 200, filename="resume.txt"):
    return client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


@patch("app.routers.resumes.resumes_service.parse_resume", return_value=FAKE_PARSED)
def test_upload_resume_parses_and_stores(mock_parse, client):
    data = register_user(client, email="seeker@example.com")
    headers = auth_headers(data["access_token"])

    resp = _upload(client, headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["parsed_skills"] == ["Python", "SQL", "Salesforce"]
    assert body["experience_years"] == 6
    mock_parse.assert_called_once()


@patch("app.routers.resumes.resumes_service.parse_resume", return_value=FAKE_PARSED)
def test_reupload_overwrites_previous_resume(mock_parse, client):
    data = register_user(client, email="reupload@example.com")
    headers = auth_headers(data["access_token"])

    first = _upload(client, headers, content=b"B" * 200)
    second = _upload(client, headers, content=b"C" * 200)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]  # same row, updated in place


def test_upload_rejects_unsupported_extension(client):
    data = register_user(client, email="badfile@example.com")
    headers = auth_headers(data["access_token"])
    resp = _upload(client, headers, filename="resume.exe")
    assert resp.status_code == 400


def test_upload_rejects_too_short_content(client):
    data = register_user(client, email="tooshort@example.com")
    headers = auth_headers(data["access_token"])
    resp = _upload(client, headers, content=b"too short")
    assert resp.status_code == 400


def test_only_job_seekers_can_upload_resumes(client):
    data = register_user(client, email="employer-resume@example.com", role="employer", company_name="Acme")
    headers = auth_headers(data["access_token"])
    resp = _upload(client, headers)
    assert resp.status_code == 403


def test_get_my_resume_404_when_none_uploaded(client):
    data = register_user(client, email="noresume@example.com")
    headers = auth_headers(data["access_token"])
    resp = client.get("/api/resumes/me", headers=headers)
    assert resp.status_code == 404


@patch("app.routers.resumes.resumes_service.parse_resume")
def test_upload_returns_502_on_ai_failure(mock_parse, client):
    from app.services.ai_client import AIResponseError

    mock_parse.side_effect = AIResponseError("model returned garbage")
    data = register_user(client, email="aifail@example.com")
    headers = auth_headers(data["access_token"])

    resp = _upload(client, headers)
    assert resp.status_code == 502
