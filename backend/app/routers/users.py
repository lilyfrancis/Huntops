from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_job_seeker
from app.db.base import get_db
from app.models.enums import JobType
from app.models.user import User
from app.schemas.preference import PreferenceOptions, PreferenceOut, PreferenceUpdate
from app.schemas.user import UserOut, UserProfileUpdate
from app.services import alert_mailboxes, preferences, whatsapp

router = APIRouter(prefix="/api/users", tags=["users"])


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.company_name is not None:
        current_user.company_name = payload.company_name
    if payload.home_market is not None:
        current_user.home_market = payload.home_market
    if payload.positioning_statement is not None:
        current_user.positioning_statement = payload.positioning_statement
    if payload.whatsapp_number is not None:
        # Refused at entry rather than stored and found broken at 07:30 — the
        # WhatsApp API fails silently on anything that isn't E.164.
        raw = payload.whatsapp_number.strip()
        if not raw:
            current_user.whatsapp_number = None
        else:
            normalised = whatsapp.normalise_number(raw)
            if normalised is None:
                raise HTTPException(
                    status_code=422,
                    detail="Include the country code, e.g. +234 803 123 4567",
                )
            current_user.whatsapp_number = normalised

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/preferences/options", response_model=PreferenceOptions)
def preference_options(db: Session = Depends(get_db)) -> PreferenceOptions:
    """Unauthenticated: the signup form has to populate this picker before the
    account it belongs to exists. Nothing here is private — it is the list of
    markets we serve, which is the same thing the marketing page advertises."""
    return PreferenceOptions(
        markets=alert_mailboxes.known_markets(db),
        lanes=preferences.lanes_with_supply(db),
        job_types=[job_type.value for job_type in JobType],
    )


@router.get("/preferences", response_model=PreferenceOut)
def get_preferences(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
):
    return preferences.get_or_create(db, current_user)


@router.put("/preferences", response_model=PreferenceOut)
def update_preferences(
    payload: PreferenceUpdate,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
):
    prefs = preferences.get_or_create(db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)

    # First save is what counts as onboarded — the app stops asking after this,
    # so it must not be re-stamped on every later settings tweak.
    if prefs.onboarded_at is None:
        prefs.onboarded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(prefs)
    return prefs
