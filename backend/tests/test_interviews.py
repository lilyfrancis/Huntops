from unittest.mock import patch

import pytest

from app.models.enums import InterviewStatus, SubscriptionTier
from app.models.user import User
from tests.conftest import auth_headers, register_user

QUESTIONS = {
    "questions": [
        "Walk me through a revenue process you rebuilt end to end.",
        "How do you decide what to instrument first in a new CRM?",
        "Tell me about a forecast you got badly wrong.",
        "How would you unblock a sales team fighting the tooling?",
        "What would your first 30 days here look like?",
    ]
}

FEEDBACK = {
    "score": 72.0,
    "strengths": ["Concrete example with a real metric"],
    "improvements": ["Name the tradeoff you rejected"],
    "model_answer": "A strong answer would open with the business problem, then the change, then the number.",
}

SUMMARY = {
    "summary": "Solid, specific answers with room to tighten structure.",
    "next_steps": ["Practise the STAR close", "Prepare two forecasting stories"],
}


def _make_seeker(client, db_session, email="interview-seeker@example.com", tier=SubscriptionTier.pro, credits=100):
    data = register_user(client, email=email)
    user = db_session.query(User).filter(User.email == email).first()
    user.subscription_tier = tier
    user.ai_credits = credits
    db_session.commit()
    return data


def _start(client, headers, **payload):
    with patch("app.services.interviews.ai_client.complete_json", return_value=QUESTIONS):
        return client.post("/api/interviews", headers=headers, json=payload or {"role_title": "RevOps Manager"})


def test_starting_an_interview_generates_all_questions_up_front(client, db_session):
    seeker = _make_seeker(client, db_session)
    resp = _start(client, auth_headers(seeker["access_token"]))

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role_title"] == "RevOps Manager"
    assert body["status"] == "in_progress"
    assert len(body["turns"]) == 5
    assert [t["position"] for t in body["turns"]] == [0, 1, 2, 3, 4]
    assert all(t["answer"] is None and t["score"] is None for t in body["turns"])


def test_starting_an_interview_charges_credits_once(client, db_session):
    seeker = _make_seeker(client, db_session, credits=100)
    _start(client, auth_headers(seeker["access_token"]))

    user = db_session.query(User).filter(User.email == "interview-seeker@example.com").first()
    db_session.refresh(user)
    assert user.ai_credits == 85  # 100 - INTERVIEW_CREDIT_COST


def test_free_tier_cannot_start_an_interview(client, db_session):
    seeker = _make_seeker(client, db_session, email="free@example.com", tier=SubscriptionTier.free)
    resp = _start(client, auth_headers(seeker["access_token"]))
    assert resp.status_code == 403
    assert "Pro" in resp.json()["detail"]


def test_insufficient_credits_is_rejected_before_any_ai_call(client, db_session):
    seeker = _make_seeker(client, db_session, email="broke@example.com", credits=5)

    with patch("app.services.interviews.ai_client.complete_json") as mock_ai:
        resp = client.post("/api/interviews", headers=auth_headers(seeker["access_token"]), json={"role_title": "X"})

    assert resp.status_code == 402
    mock_ai.assert_not_called()


def test_a_failed_generation_does_not_charge_credits(client, db_session):
    from app.services.ai_client import AIResponseError

    seeker = _make_seeker(client, db_session, email="fail@example.com", credits=100)
    with patch("app.services.interviews.ai_client.complete_json", side_effect=AIResponseError("boom")):
        resp = client.post("/api/interviews", headers=auth_headers(seeker["access_token"]), json={"role_title": "X"})

    assert resp.status_code == 502
    user = db_session.query(User).filter(User.email == "fail@example.com").first()
    db_session.refresh(user)
    assert user.ai_credits == 100


def test_starting_without_a_job_or_role_title_is_rejected(client, db_session):
    seeker = _make_seeker(client, db_session, email="norole@example.com")
    with patch("app.services.interviews.ai_client.complete_json", return_value=QUESTIONS):
        resp = client.post("/api/interviews", headers=auth_headers(seeker["access_token"]), json={})
    assert resp.status_code == 400


def test_answering_a_question_stores_the_grade(client, db_session):
    seeker = _make_seeker(client, db_session)
    headers = auth_headers(seeker["access_token"])
    session_id = _start(client, headers).json()["id"]

    with patch("app.services.interviews.ai_client.complete_json", return_value=FEEDBACK):
        resp = client.post(
            f"/api/interviews/{session_id}/turns/0/answer",
            headers=headers,
            json={"answer": "I rebuilt lead routing and cut response time from 4 hours to 20 minutes."},
        )

    assert resp.status_code == 200, resp.text
    turn = resp.json()
    assert turn["score"] == 72.0
    assert turn["strengths"] == FEEDBACK["strengths"]
    assert turn["model_answer"] == FEEDBACK["model_answer"]
    assert turn["answered_at"] is not None


def test_answering_an_unknown_question_position_is_404(client, db_session):
    seeker = _make_seeker(client, db_session)
    headers = auth_headers(seeker["access_token"])
    session_id = _start(client, headers).json()["id"]

    resp = client.post(f"/api/interviews/{session_id}/turns/99/answer", headers=headers, json={"answer": "hi"})
    assert resp.status_code == 404


def test_completing_a_session_averages_scores_and_summarizes(client, db_session):
    seeker = _make_seeker(client, db_session)
    headers = auth_headers(seeker["access_token"])
    session_id = _start(client, headers).json()["id"]

    for position, score in ((0, 80.0), (1, 60.0)):
        with patch("app.services.interviews.ai_client.complete_json", return_value={**FEEDBACK, "score": score}):
            client.post(
                f"/api/interviews/{session_id}/turns/{position}/answer",
                headers=headers,
                json={"answer": "An answer with a concrete example."},
            )

    with patch("app.services.interviews.ai_client.complete_json", return_value=SUMMARY):
        resp = client.post(f"/api/interviews/{session_id}/complete", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["average_score"] == 70.0  # unanswered turns are excluded
    assert body["summary"] == SUMMARY["summary"]
    assert body["next_steps"] == SUMMARY["next_steps"]
    assert body["completed_at"] is not None


def test_a_completed_session_rejects_further_answers(client, db_session):
    seeker = _make_seeker(client, db_session)
    headers = auth_headers(seeker["access_token"])
    session_id = _start(client, headers).json()["id"]

    with patch("app.services.interviews.ai_client.complete_json", return_value=SUMMARY):
        client.post(f"/api/interviews/{session_id}/complete", headers=headers)

    with patch("app.services.interviews.ai_client.complete_json", return_value=FEEDBACK):
        resp = client.post(f"/api/interviews/{session_id}/turns/0/answer", headers=headers, json={"answer": "late"})

    assert resp.status_code == 409


def test_sessions_are_scoped_to_their_owner(client, db_session):
    owner = _make_seeker(client, db_session, email="owner@example.com")
    intruder = _make_seeker(client, db_session, email="intruder@example.com")

    session_id = _start(client, auth_headers(owner["access_token"])).json()["id"]

    resp = client.get(f"/api/interviews/{session_id}", headers=auth_headers(intruder["access_token"]))
    assert resp.status_code == 404

    resp = client.post(
        f"/api/interviews/{session_id}/turns/0/answer",
        headers=auth_headers(intruder["access_token"]),
        json={"answer": "not mine"},
    )
    assert resp.status_code == 404


def test_listing_my_interviews_omits_the_transcript(client, db_session):
    seeker = _make_seeker(client, db_session)
    headers = auth_headers(seeker["access_token"])
    _start(client, headers)

    resp = client.get("/api/interviews", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert "turns" not in rows[0]
    assert rows[0]["role_title"] == "RevOps Manager"


def test_a_malformed_ai_reply_is_rejected_not_stored(client, db_session):
    seeker = _make_seeker(client, db_session)
    headers = auth_headers(seeker["access_token"])
    session_id = _start(client, headers).json()["id"]

    # score out of range — must fail schema validation rather than persist
    with patch("app.services.interviews.ai_client.complete_json", return_value={**FEEDBACK, "score": 900}):
        resp = client.post(f"/api/interviews/{session_id}/turns/0/answer", headers=headers, json={"answer": "x"})

    assert resp.status_code == 502

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["turns"][0]["score"] is None
    assert detail["turns"][0]["answer"] is None


def test_interview_can_be_tailored_to_a_real_job(client, db_session):
    import uuid

    from app.models.enums import ExperienceLevel, JobStatus, JobType
    from app.models.job import Job

    job = Job(
        title="Senior RevOps Manager",
        description="Own the RevOps stack end to end across Salesforce and HubSpot.",
        requirements=["Salesforce", "HubSpot"],
        location="Remote",
        job_type=JobType.full_time,
        experience_level=ExperienceLevel.senior,
        status=JobStatus.active,
        source="remotive",
        source_url=f"https://example.com/{uuid.uuid4()}",
        company_name="Flow Corp",
    )
    db_session.add(job)
    db_session.commit()

    seeker = _make_seeker(client, db_session)
    with patch("app.services.interviews.ai_client.complete_json", return_value=QUESTIONS) as mock_ai:
        resp = client.post(
            "/api/interviews", headers=auth_headers(seeker["access_token"]), json={"job_id": str(job.id)}
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role_title"] == "Senior RevOps Manager"
    assert body["company_name"] == "Flow Corp"
    assert body["job_id"] == str(job.id)

    # the job's real requirements must reach the prompt, not just its title
    prompt = mock_ai.call_args.kwargs["prompt"]
    assert "Salesforce" in prompt


def test_starting_against_an_unknown_job_is_404(client, db_session):
    import uuid

    seeker = _make_seeker(client, db_session)
    resp = client.post(
        "/api/interviews",
        headers=auth_headers(seeker["access_token"]),
        json={"job_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
