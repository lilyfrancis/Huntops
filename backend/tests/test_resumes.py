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


def _upload(client, headers, content=b"A" * 200, filename="resume.txt", **data):
    return client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        data=data or None,
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
def test_a_second_upload_adds_a_cv_rather_than_replacing_the_first(mock_parse, client):
    """Uploading used to overwrite the only CV. Now that somebody can keep one
    per career track, re-uploading the sales CV must not silently destroy the
    engineering one."""
    data = register_user(client, email="reupload@example.com")
    headers = auth_headers(data["access_token"])

    first = _upload(client, headers, content=b"B" * 200, label="Engineering")
    second = _upload(client, headers, content=b"C" * 200, label="Sales")

    assert first.json()["id"] != second.json()["id"]
    listed = client.get("/api/resumes", headers=headers).json()
    assert {r["label"] for r in listed} == {"Engineering", "Sales"}


@patch("app.routers.resumes.resumes_service.parse_resume", return_value=FAKE_PARSED)
def test_naming_a_cv_to_replace_overwrites_that_one(mock_parse, client):
    data = register_user(client, email="replace@example.com")
    headers = auth_headers(data["access_token"])

    first = _upload(client, headers, content=b"B" * 200, label="Engineering")
    again = _upload(client, headers, content=b"C" * 200, replaces=first.json()["id"])

    assert again.json()["id"] == first.json()["id"]
    assert len(client.get("/api/resumes", headers=headers).json()) == 1


@patch("app.routers.resumes.resumes_service.parse_resume", return_value=FAKE_PARSED)
def test_the_first_cv_becomes_the_fallback(mock_parse, client):
    data = register_user(client, email="firstprimary@example.com")
    headers = auth_headers(data["access_token"])

    first = _upload(client, headers, label="Engineering")
    second = _upload(client, headers, label="Sales")

    by_id = {r["id"]: r for r in client.get("/api/resumes", headers=headers).json()}
    assert by_id[first.json()["id"]]["is_primary"] is True
    assert by_id[second.json()["id"]]["is_primary"] is False


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
