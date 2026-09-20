"""Sending a draft by hand.

Apollo does not always find an email. When it does not, the pitch was
drafted, charged for, and then stranded — the page could show it and offer
nothing to do with it, which is the worst of both: the money is spent and
the message never leaves.
"""

from unittest.mock import patch

import pytest

from app.models.enums import OutreachStatus
from app.models.outreach import Outreach
from app.models.recruiter_contact import RecruiterContact
from app.services import outreach as outreach_service
from tests.conftest import auth_headers, register_user
from tests.test_outreach import _elite_user_with_resume, _job


@pytest.fixture
def seeker(db_session):
    return _elite_user_with_resume(db_session, email="sender@example.com")


@pytest.fixture
def seeded_job(db_session):
    return _job(db_session)


def _seed(db, user_id, job_id, *, contact_email=None, status=OutreachStatus.draft_no_contact):
    contact = None
    if contact_email is not None:
        contact = RecruiterContact(
            job_id=job_id, name="Dana Recruiter", title="Talent Lead", email=contact_email,
        )
        db.add(contact)
        db.flush()

    row = Outreach(
        user_id=user_id, job_id=job_id,
        recruiter_contact_id=contact.id if contact else None,
        email_subject="Interested in the Growth Lead role",
        email_body="Hello — I saw the role and would love to talk.",
        linkedin_msg="Hi Dana, ...", cv_bullets=["Grew pipeline 40%"],
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_a_draft_with_no_contact_can_be_sent_to_an_address_the_user_supplies(db_session, seeded_job, seeker):
    """The whole point: the draft is the expensive part, and most people can
    find the hiring manager themselves in a minute."""
    row = _seed(db_session, seeker.id, seeded_job.id)
    assert row.recipient_email is None

    with patch("app.services.outreach._send", return_value=True) as send:
        result = outreach_service.send_draft(
            db_session, seeker, row, to_email="dana@company.test")

    assert result.status is OutreachStatus.sent
    assert result.sent_at is not None
    assert send.call_args.args[2] == "dana@company.test"


def test_sending_without_a_recipient_says_so_rather_than_failing_silently(db_session, seeded_job, seeker):
    row = _seed(db_session, seeker.id, seeded_job.id)

    with pytest.raises(outreach_service.OutreachSendError, match="No recipient"):
        outreach_service.send_draft(db_session, seeker, row)


def test_the_apollo_contact_is_used_when_no_address_is_given(db_session, seeded_job, seeker):
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="found@company.test")
    assert row.recipient_email == "found@company.test"

    with patch("app.services.outreach._send", return_value=True) as send:
        outreach_service.send_draft(db_session, seeker, row)

    assert send.call_args.args[2] == "found@company.test"


def test_an_edited_draft_sends_the_edit_and_keeps_it(db_session, seeded_job, seeker):
    """Nobody should have to send a generated email they cannot change a word
    of, and the revision has to survive — the page shows what was sent."""
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="found@company.test")

    with patch("app.services.outreach._send", return_value=True) as send:
        outreach_service.send_draft(
            db_session, seeker, row,
            subject="  Growth Lead — quick note  ", body="  My own words.  ")

    assert send.call_args.args[3] == "Growth Lead — quick note"   # trimmed
    assert send.call_args.args[4] == "My own words."
    db_session.refresh(row)
    assert row.email_body == "My own words."


def test_an_already_sent_draft_is_not_sent_twice(db_session, seeded_job, seeker):
    """Double-sending a pitch to a recruiter is worse than not sending it."""
    row = _seed(db_session, seeker.id, seeded_job.id,
                contact_email="found@company.test", status=OutreachStatus.sent)

    with patch("app.services.outreach._send") as send:
        with pytest.raises(outreach_service.OutreachSendError, match="already been sent"):
            outreach_service.send_draft(db_session, seeker, row)
    send.assert_not_called()


def test_a_failed_send_keeps_the_draft_and_can_be_retried(db_session, seeded_job, seeker):
    """The draft is paid for. Losing it because SMTP was down would charge
    twice for one piece of work."""
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="found@company.test")

    with patch("app.services.outreach._send", return_value=False):
        with pytest.raises(outreach_service.OutreachSendError, match="could not be sent"):
            outreach_service.send_draft(db_session, seeker, row)

    db_session.refresh(row)
    assert row.status is OutreachStatus.failed
    assert row.email_body                      # still there

    with patch("app.services.outreach._send", return_value=True):
        assert outreach_service.send_draft(db_session, seeker, row).status is OutreachStatus.sent


def test_sending_charges_no_credits(db_session, seeded_job, seeker):
    """The drafting was charged. Sending it, or re-sending after a bad
    address, is not a second piece of work we did."""
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="found@company.test")
    before = seeker.ai_credits

    with patch("app.services.outreach._send", return_value=True):
        outreach_service.send_draft(db_session, seeker, row)

    db_session.refresh(seeker)
    assert seeker.ai_credits == before


def test_one_user_cannot_send_anothers_draft(client, db_session, seeded_job, seeker):
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="found@company.test")

    register_user(client, email="intruder@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "intruder@example.com", "password": "StrongPass1"}).json()
    headers = auth_headers(token["access_token"])

    with patch("app.services.outreach._send", return_value=True) as send:
        resp = client.post(f"/api/outreach/{row.id}/send", json={}, headers=headers)

    assert resp.status_code == 404
    send.assert_not_called()


def test_the_address_actually_used_is_recorded(db_session, seeded_job, seeker):
    """Weeks later, "sent" without a recipient is not a record of anything.
    The address the user supplied is not derivable from anywhere else."""
    row = _seed(db_session, seeker.id, seeded_job.id)

    with patch("app.services.outreach._send", return_value=True):
        result = outreach_service.send_draft(
            db_session, seeker, row, to_email="dana@company.example")

    assert result.sent_to_email == "dana@company.example"
    assert result.recipient_email == "dana@company.example"


def test_the_recorded_address_wins_over_a_contact_that_later_changes(db_session, seeded_job, seeker):
    """What was sent is history. If Apollo refreshes the contact afterwards,
    the record must not quietly claim it went somewhere it did not."""
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="old@company.test")

    with patch("app.services.outreach._send", return_value=True):
        outreach_service.send_draft(db_session, seeker, row, to_email="actual@company.example")

    contact = db_session.query(RecruiterContact).filter(
        RecruiterContact.id == row.recruiter_contact_id).one()
    contact.email = "changed@company.test"
    db_session.commit()
    db_session.refresh(row)

    assert row.recipient_email == "actual@company.example"


def test_a_failed_send_records_no_recipient(db_session, seeded_job, seeker):
    """Nothing was sent, so nothing was sent anywhere."""
    row = _seed(db_session, seeker.id, seeded_job.id, contact_email="found@company.test")

    with patch("app.services.outreach._send", return_value=False):
        with pytest.raises(outreach_service.OutreachSendError):
            outreach_service.send_draft(db_session, seeker, row)

    db_session.refresh(row)
    assert row.sent_to_email is None
