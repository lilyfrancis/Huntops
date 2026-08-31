"""Job-hunt momentum stats — funnel, streak, and activity.

Derived entirely from timestamps already on Application, Outreach, and
InterviewSession. No new table: an "activity log" would duplicate rows that
already exist and immediately risk drifting from them.

Available on every tier, deliberately. The paid features are the ones that cost
an AI call; showing someone their own effort back should never be behind a
paywall — and it is the screen that brings them back tomorrow.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.enums import ApplicationStatus, InterviewStatus, OutreachStatus
from app.models.interview import InterviewSession
from app.models.job_match import JobMatch
from app.models.outreach import Outreach
from app.models.user import User

ACTIVITY_WINDOW_DAYS = 56  # 8 weeks, so the heatmap is a clean 8x7 grid

# An application's current status implies every stage it already cleared: one
# that is "offered" was necessarily reviewed and interviewed on the way there.
# Without this the funnel would show later stages as larger than earlier ones.
_REACHED_REVIEWED = (ApplicationStatus.reviewed, ApplicationStatus.interviewing, ApplicationStatus.offered)
_REACHED_INTERVIEWING = (ApplicationStatus.interviewing, ApplicationStatus.offered)
_REACHED_OFFERED = (ApplicationStatus.offered,)


def _as_date(value: datetime) -> date:
    """SQLite drops tzinfo on round-trip; normalize before taking the date."""
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).date()


def _activity_dates(db: Session, user: User) -> list[date]:
    """Every distinct day this user did something that moves the hunt forward."""
    stamps: list[datetime] = []
    stamps += [row[0] for row in db.query(Application.created_at).filter(Application.candidate_id == user.id)]
    stamps += [row[0] for row in db.query(Outreach.created_at).filter(Outreach.user_id == user.id)]
    stamps += [row[0] for row in db.query(InterviewSession.created_at).filter(InterviewSession.user_id == user.id)]
    return sorted({_as_date(s) for s in stamps if s is not None})


def _streaks(active: list[date], today: date) -> tuple[int, int]:
    """Return (current streak, longest streak) in days.

    A streak survives a day that hasn't happened yet: if the last active day is
    today *or* yesterday the run is still live, so opening the app in the
    morning doesn't show a streak that looks broken until you act.
    """
    if not active:
        return 0, 0

    longest = run = 1
    for previous, current in zip(active, active[1:]):
        run = run + 1 if (current - previous).days == 1 else 1
        longest = max(longest, run)

    current_streak = 0
    if active[-1] in (today, today - timedelta(days=1)):
        current_streak = 1
        for previous, current in zip(reversed(active[:-1]), reversed(active[1:])):
            if (current - previous).days == 1:
                current_streak += 1
            else:
                break

    return current_streak, longest


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def build_stats(db: Session, user: User) -> dict:
    today = datetime.now(timezone.utc).date()

    applications = db.query(Application).filter(Application.candidate_id == user.id)
    applied = applications.count()
    reviewed = applications.filter(Application.status.in_(_REACHED_REVIEWED)).count()
    interviewing = applications.filter(Application.status.in_(_REACHED_INTERVIEWING)).count()
    offered = applications.filter(Application.status.in_(_REACHED_OFFERED)).count()

    active = _activity_dates(db, user)
    current_streak, longest_streak = _streaks(active, today)

    window_start = today - timedelta(days=ACTIVITY_WINDOW_DAYS - 1)
    active_in_window = {d for d in active if d >= window_start}
    activity = [
        {"date": (window_start + timedelta(days=offset)).isoformat(),
         "active": (window_start + timedelta(days=offset)) in active_in_window}
        for offset in range(ACTIVITY_WINDOW_DAYS)
    ]

    return {
        "funnel": [
            {"stage": "applied", "label": "Applied", "count": applied},
            {"stage": "reviewed", "label": "Reviewed", "count": reviewed},
            {"stage": "interviewing", "label": "Interviewing", "count": interviewing},
            {"stage": "offered", "label": "Offered", "count": offered},
        ],
        "totals": {
            "matches_scored": db.query(JobMatch).filter(JobMatch.user_id == user.id).count(),
            "applications": applied,
            "outreach_sent": db.query(Outreach)
            .filter(Outreach.user_id == user.id, Outreach.status == OutreachStatus.sent)
            .count(),
            "interviews_completed": db.query(InterviewSession)
            .filter(
                InterviewSession.user_id == user.id,
                InterviewSession.status == InterviewStatus.completed,
            )
            .count(),
        },
        "streak": {
            "current_days": current_streak,
            "longest_days": longest_streak,
            "active_days_in_window": len(active_in_window),
            "window_days": ACTIVITY_WINDOW_DAYS,
        },
        "conversion": {
            "applied_to_interviewing": _rate(interviewing, applied),
            "applied_to_offered": _rate(offered, applied),
        },
        "activity": activity,
    }
