"""Autopilot Outreach orchestration — the blueprint's flagship feature.

Ports Job Engine's Phase 3 (Apollo search → enrich → draft → send) into a
gated, metered, multi-tenant flow: Elite-tier only, credit-checked up front
so a user who can't pay never costs a real Apollo/Anthropic call, and
cached per (user, job) so re-opening the same job never re-drafts or
re-charges.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import OutreachStatus, SubscriptionTier
from app.models.gmail_connection import GmailConnection
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.recruiter_contact import RecruiterContact
from app.models.resume import Resume
from app.models.user import User
from app.services import apollo, email_bridge, gmail_oauth, outreach_drafting
from app.services.apollo import ApolloAPIError
from app.services.credits import adjust_credits
from app.services.gmail_oauth import GmailAPIError

logger = logging.getLogger(__name__)
settings = get_settings()


class TierRequiredError(Exception):
    pass


class InsufficientCreditsError(Exception):
    pass


class ResumeRequiredError(Exception):
    pass


class MissingCompanyError(Exception):
    pass


def _get_or_discover_recruiter(db: Session, job: Job) -> RecruiterContact | None:
    contact = db.query(RecruiterContact).filter(RecruiterContact.job_id == job.id).first()
    if contact is not None:
        return contact

    try:
        people = apollo.search_people(job.company_name)
        candidate = apollo.pick_best_candidate(people)
        if candidate is None:
            return None

        enriched = apollo.enrich_person(candidate["id"])
        contact = RecruiterContact(
            job_id=job.id,
            apollo_person_id=candidate.get("id"),
            name=enriched.get("name") or candidate.get("name"),
            title=enriched.get("title") or candidate.get("title"),
            email=enriched.get("email"),
            email_status=enriched.get("email_status"),
            linkedin_url=enriched.get("linkedin_url"),
        )
        db.add(contact)
        db.flush()
        return contact
    except ApolloAPIError as e:
        logger.warning("Apollo lookup failed for job=%s: %s — proceeding draft-only", job.id, e)
        return None


def initiate_outreach(db: Session, user: User, job: Job) -> Outreach:
    existing = db.query(Outreach).filter(Outreach.user_id == user.id, Outreach.job_id == job.id).first()
    if existing is not None:
        return existing

    if user.subscription_tier != SubscriptionTier.elite:
        raise TierRequiredError("Autopilot Outreach is an Elite-tier feature")
    if user.ai_credits < settings.OUTREACH_CREDIT_COST:
        raise InsufficientCreditsError(f"Need {settings.OUTREACH_CREDIT_COST} credits, have {user.ai_credits}")

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if resume is None:
        raise ResumeRequiredError("Upload a résumé before requesting outreach")
    if not job.company_name:
        raise MissingCompanyError("This job has no company name on file — can't search for a recruiter")

    contact = _get_or_discover_recruiter(db, job)

    # Raises AIResponseError on failure — deliberately not caught here, so no
    # Outreach row is created and no credits are spent on a failed draft.
    draft = outreach_drafting.draft_outreach(
        user, resume, job,
        recruiter_name=contact.name if contact else None,
        recruiter_title=contact.title if contact else None,
    )

    result = Outreach(
        user_id=user.id,
        job_id=job.id,
        recruiter_contact_id=contact.id if contact else None,
        email_subject=draft.email_subject,
        email_body=draft.email_body,
        linkedin_msg=draft.linkedin_msg,
        cv_bullets=draft.cv_bullets,
        status=OutreachStatus.draft_no_contact,
    )
    db.add(result)
    db.flush()

    if contact and contact.email:
        gmail_connection = db.query(GmailConnection).filter(GmailConnection.user_id == user.id).first()
        if gmail_connection is None:
            logger.info("User %s has a recruiter email but no connected Gmail — leaving as draft", user.id)
        else:
            try:
                access_token = email_bridge.get_valid_access_token(db, gmail_connection)
                gmail_oauth.send_message(access_token, contact.email, draft.email_subject, draft.email_body)
                result.status = OutreachStatus.sent
                result.sent_at = datetime.now(timezone.utc)
            except GmailAPIError as e:
                logger.error("Sending outreach failed for user=%s job=%s: %s", user.id, job.id, e)
                result.status = OutreachStatus.failed

    # The draft succeeded regardless of send outcome — that's the expensive
    # part (Apollo reveal + Sonnet draft), so it's what gets charged.
    adjust_credits(db, user, action="outreach", amount=-settings.OUTREACH_CREDIT_COST)
    db.commit()
    db.refresh(result)
    return result
