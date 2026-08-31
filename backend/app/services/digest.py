"""Daily digest — ported from Job Engine's "Build Digest" step, generalized
past a single Telegram chat into per-user email, home-market matches first.
"""

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User

settings = get_settings()


def get_top_matches(db: Session, user: User) -> list[tuple[JobMatch, Job]]:
    """Reads whatever's already scored — this never triggers an AI call.
    The scheduled digest job scores first, then calls this; the interactive
    preview endpoint just renders what's there."""
    rows = (
        db.query(JobMatch, Job)
        .join(Job, JobMatch.job_id == Job.id)
        .filter(JobMatch.user_id == user.id, Job.status == JobStatus.active)
        .order_by(desc(JobMatch.geo_boost_applied), desc(JobMatch.fit_score))
        .limit(settings.DIGEST_MAX_JOBS)
        .all()
    )
    return rows


def format_digest_email(matches: list[tuple[JobMatch, Job]]) -> tuple[str, str]:
    if not matches:
        return "Your HuntOps digest", "No new high-fit matches today — check back tomorrow."

    home_market_count = sum(1 for match, _ in matches if match.geo_boost_applied)
    lines = [
        f"{'[home market] ' if match.geo_boost_applied else ''}{job.title} at "
        f"{job.company_name or 'a company'} ({job.location}) — fit {round(match.fit_score)}"
        for match, job in matches
    ]

    subject = f"HuntOps digest: {len(matches)} match{'es' if len(matches) != 1 else ''}"
    if home_market_count:
        subject += f" ({home_market_count} home-market)"

    body = "\n".join(lines)
    return subject, body
