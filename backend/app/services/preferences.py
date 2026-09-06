"""What each user asked for, and how that becomes a query.

The one place that turns a UserPreference row into a filter. The feed, the
digest and autopilot all call `apply_to_query`, so "jobs for me" means exactly
the same thing in all three — a user can't see a job on their dashboard that
autopilot considers out of scope, or vice versa.
"""

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services.ghost_detection import GHOST_THRESHOLD


def get_or_create(db: Session, user: User) -> UserPreference:
    """Every user has preferences; an untouched row means "no filters yet".

    Created on read rather than at registration so users who signed up before
    this existed aren't a separate case everything downstream has to handle.
    """
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if prefs is None:
        prefs = UserPreference(user_id=user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def apply_to_query(query: Query, prefs: UserPreference | None) -> Query:
    """Narrow a Job query to what this user asked for.

    Each clause is skipped when its list is empty, so a user who only picked a
    country still sees every lane there rather than nothing at all. Absent
    preferences mean no narrowing — never an empty feed.
    """
    if prefs is None:
        return query

    if prefs.target_markets:
        # Jobs with no market are the global API sources: remote-first listings
        # that belong to every market rather than none, so they stay visible.
        # Filtering them out would leave a new market with an empty feed until
        # its mailbox has run.
        query = query.filter(or_(Job.market.in_(prefs.target_markets), Job.market.is_(None)))
    if prefs.lanes:
        query = query.filter(Job.lane.in_(prefs.lanes))
    if prefs.job_types:
        query = query.filter(Job.job_type.in_(prefs.job_types))
    if prefs.remote_only:
        query = query.filter(Job.is_remote.is_(True))

    return query


def feed_query(db: Session, prefs: UserPreference | None, *, hide_ghosts: bool = True) -> Query:
    """The base query behind a user's feed: active, non-ghost, on-preference.

    Ghosts are hidden by default here (unlike the public listing, where the
    caller opts in) because this feed is what autopilot acts on — applying to
    a listing we have flagged as probably fake is the one outcome nobody wants.
    Unscanned jobs stay visible: absence of a score isn't evidence of a ghost.
    """
    query = db.query(Job).filter(Job.status == JobStatus.active)
    if hide_ghosts:
        query = query.filter(or_(Job.ghost_score.is_(None), Job.ghost_score < GHOST_THRESHOLD))
    return apply_to_query(query, prefs)
