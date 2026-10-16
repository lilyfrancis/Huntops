"""What each user asked for, and how that becomes a query.

The one place that turns a UserPreference row into a filter. The feed, the
digest and autopilot all call `apply_to_query`, so "jobs for me" means exactly
the same thing in all three — a user can't see a job on their dashboard that
autopilot considers out of scope, or vice versa.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.models.enums import JobLane, JobStatus
from app.models.job import Job
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services import geo
from app.services.ghost_detection import GHOST_THRESHOLD

# The work modes a job can be in, and the only values the API accepts.
WORK_MODES = ("remote", "hybrid", "onsite")

# What "how recent" is allowed to mean. A free-form number would let somebody
# ask for the last 0 days and then report the feed as broken.
RECENCY_CHOICES = (1, 3, 7, 14, 30)


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


def filter_stages(prefs: UserPreference) -> list[tuple[str, object]]:
    """Every narrowing clause this user's settings produce, in order, each
    labelled with the setting that caused it.

    `apply_to_query` consumes this, and so does the diagnostic that counts how
    many jobs survive each step. Sharing one list is the point: an explanation
    of why a feed is empty is worthless if it can drift from the filter it
    claims to explain.

    A clause is omitted entirely when its setting is unset, so a user who
    picked only a country still sees every lane there rather than nothing.
    """
    stages: list[tuple[str, object]] = []

    if prefs.target_markets:
        # Jobs with no market are the global API sources: remote-first listings
        # that belong to every market rather than none, so they stay visible.
        # Filtering them out would leave a new market with an empty feed until
        # its mailbox has run.
        stages.append((
            f"markets {prefs.target_markets}",
            or_(Job.market.in_(prefs.target_markets), Job.market.is_(None)),
        ))

    if prefs.locations:
        # Substring, case-insensitive, because a board writes the same city a
        # dozen ways: "Toronto", "Toronto, ON", "Downtown Toronto (Hybrid)".
        #
        # Remote jobs always pass. Someone who asked for Toronto wants the
        # roles they can actually take, and a remote job in their own market is
        # one of them — a strict city match would hide exactly the listings
        # most people are hoping for.
        clauses = [Job.location.ilike(f"%{name.strip()}%") for name in prefs.locations if name.strip()]
        if clauses:
            stages.append((f"cities {prefs.locations}", or_(*clauses, Job.is_remote.is_(True))))

    if prefs.lanes:
        stages.append((f"job families {prefs.lanes}", Job.lane.in_(prefs.lanes)))

    if prefs.experience_levels:
        stages.append((f"seniority {prefs.experience_levels}", Job.experience_level.in_(prefs.experience_levels)))

    if prefs.job_types:
        stages.append((f"employment type {prefs.job_types}", Job.job_type.in_(prefs.job_types)))

    if prefs.remote_only:
        stages.append(("remote only", Job.is_remote.is_(True)))

    # Eligibility: who may apply, which is a different question from
    # `target_markets` above. See services/geo.py — picking Nigeria admits a
    # remote role anywhere that has not shut Nigerians out, and rejects a
    # US-only one however remote it is.
    eligibility = geo.eligibility_clause(prefs.eligibility or [])
    if eligibility is not None:
        stages.append((f"can apply from {prefs.eligibility}", eligibility))

    if prefs.work_modes:
        # Jobs ingested before work_mode existed have none, and a null is not
        # evidence of anything. Hiding them would empty the feed of everything
        # older than this release for anybody who touches this filter.
        stages.append((
            f"work mode {prefs.work_modes}",
            or_(Job.work_mode.in_(prefs.work_modes), Job.work_mode.is_(None)),
        ))

    if prefs.salary_min_annual and prefs.salary_currency:
        # Only listings we can actually compare are judged. Most boards
        # publish no salary at all, and a floor that also hid every unpriced
        # listing would throw away the majority of the pool to enforce a
        # number nobody stated. A listing in another currency is unknowable
        # without an FX rate, so it is kept for the same reason.
        stages.append((
            f"salary at least {prefs.salary_min_annual:,.0f} {prefs.salary_currency}",
            or_(
                Job.salary_annual_max.is_(None),
                Job.salary_currency != prefs.salary_currency,
                Job.salary_annual_max >= prefs.salary_min_annual,
            ),
        ))

    if prefs.posted_within_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=prefs.posted_within_days)
        stages.append((f"posted within {prefs.posted_within_days} days", Job.created_at >= cutoff))

    if prefs.title_keywords:
        # Title only. Matching the description would return roles whose
        # connection to "backend engineer" is invisible on the card, which
        # reads as the filter being ignored.
        clauses = [
            Job.title.ilike(f"%{word.strip()}%")
            for word in prefs.title_keywords
            if word.strip()
        ]
        if clauses:
            stages.append((f"role title {prefs.title_keywords}", or_(*clauses)))

    return stages


def apply_to_query(query: Query, prefs: UserPreference | None) -> Query:
    """Narrow a Job query to what this user asked for.

    Absent preferences mean no narrowing — never an empty feed.
    """
    if prefs is None:
        return query
    for _label, clause in filter_stages(prefs):
        query = query.filter(clause)
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


# A lane needs at least this many live jobs before it is offered at signup.
# One stray listing is not a job family; picking it would produce a feed of one.
MIN_JOBS_FOR_LANE = 5


def lanes_with_supply(db: Session) -> list[str]:
    """Job families worth offering, i.e. ones with real listings behind them.

    Symmetric with `known_markets`: offering a lane with nothing in it is a
    promise of supply that does not exist, and the user finds out by getting an
    empty feed on the day they signed up.

    Falls back to every lane when nothing clears the bar, so a fresh deployment
    offers a full choice rather than none — an empty picker reads as broken,
    and at that point the pool is too thin to say anything either way.
    """
    rows = (
        db.query(Job.lane, func.count(Job.id))
        .filter(Job.status == JobStatus.active, Job.lane.isnot(None), Job.lane != JobLane.other)
        .group_by(Job.lane)
        .having(func.count(Job.id) >= MIN_JOBS_FOR_LANE)
        .all()
    )
    if not rows:
        return [lane.value for lane in JobLane if lane is not JobLane.other]

    # Busiest first: the lane with the most supply is the likeliest pick, and
    # the ordering doubles as an honest signal of where the depth is.
    return [lane.value for lane, _ in sorted(rows, key=lambda r: -r[1])]
