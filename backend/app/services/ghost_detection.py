"""Ghost-job detection — flags listings that probably aren't a real, fillable role.

Deliberately heuristic and deterministic rather than AI-scored. Three reasons:
every job in the feed gets checked (an AI call per listing would dominate
ingestion cost), the signals below are cheap and legible, and a candidate
deserves to see *why* something was flagged rather than an opaque model score.

Scores are 0-100, where higher means more suspicious. `classify` turns a score
into the band the UI actually renders.
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.job import Job

CAUTION_THRESHOLD = 30
GHOST_THRESHOLD = 60

STALE_DAYS = 45
VERY_STALE_DAYS = 90

# Evergreen "always accepting applicants" postings — the classic pipeline-builder
# that never maps to one fillable seat.
_EVERGREEN_RE = re.compile(
    r"\b(various positions|multiple positions|general application|open application|"
    r"talent (pool|pipeline|community)|future opening|future opportunit|expression of interest|"
    r"always hiring|candidates? wanted|register your interest)\b",
    re.I,
)

# Staffing-agency listings that stand in for an unnamed employer.
_ANONYMOUS_CLIENT_RE = re.compile(
    r"\b(confidential client|our client|a leading client|staffing agency|recruitment agency|"
    r"on behalf of our client)\b",
    re.I,
)


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; normalize before any comparison."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _repost_count(db: Session, job: Job) -> int:
    """How many other live listings share this job's title + company.

    A role reposted under many distinct URLs is either an agency spraying the
    same seat across boards or an evergreen ad — both worth flagging.
    """
    if not job.company_name:
        return 0
    query = db.query(func.count(Job.id)).filter(
        Job.title == job.title,
        Job.company_name == job.company_name,
    )
    # A job scored during ingestion has no id yet and isn't in the table, so
    # there is nothing to exclude — filtering on `id != NULL` would match nothing.
    if job.id is not None:
        query = query.filter(Job.id != job.id)
    return query.scalar() or 0


def score_job(job: Job, *, db: Session | None = None, now: datetime | None = None) -> tuple[int, list[str]]:
    """Return (score, human-readable flags) for one job."""
    now = now or datetime.now(timezone.utc)
    score = 0
    flags: list[str] = []

    # created_at is populated at flush time, so a not-yet-inserted job scored
    # during ingestion has none yet — it is brand new, so age 0.
    created_at = _as_aware_utc(job.created_at) if job.created_at else now
    age_days = (now - created_at).days
    if age_days >= VERY_STALE_DAYS:
        score += 40
        flags.append(f"Still listed after {age_days} days")
    elif age_days >= STALE_DAYS:
        score += 25
        flags.append(f"Listed for over {STALE_DAYS} days")

    description = job.description or ""
    if len(description) < 150:
        score += 30
        flags.append("Almost no job description")
    elif len(description) < 300:
        score += 20
        flags.append("Unusually thin job description")

    if not job.salary_range:
        score += 10
        flags.append("No salary disclosed")

    if not job.requirements:
        score += 10
        flags.append("No requirements listed")

    haystack = f"{job.title} {description}"
    if _EVERGREEN_RE.search(haystack):
        score += 35
        flags.append("Reads as an evergreen talent-pool ad, not one open seat")

    if _ANONYMOUS_CLIENT_RE.search(haystack):
        score += 15
        flags.append("Employer is not named — posted on behalf of a client")

    if db is not None:
        reposts = _repost_count(db, job)
        if reposts >= 3:
            # Weighted to clear CAUTION_THRESHOLD on its own: a role sprayed
            # across four-plus listings is the pipeline-builder pattern, and
            # deserves a badge even when the copy itself looks fine.
            score += 30
            flags.append(f"Same role posted {reposts + 1} times")
        elif reposts >= 1:
            score += 10
            flags.append("Same role posted more than once")

    return min(score, 100), flags


def classify(score: int | None) -> str:
    if score is None:
        return "unchecked"
    if score >= GHOST_THRESHOLD:
        return "likely_ghost"
    if score >= CAUTION_THRESHOLD:
        return "caution"
    return "clean"


def apply_score(db: Session, job: Job, *, now: datetime | None = None) -> Job:
    score, flags = score_job(job, db=db, now=now)
    job.ghost_score = score
    job.ghost_flags = flags
    job.ghost_checked_at = now or datetime.now(timezone.utc)
    return job


def rescan_all(db: Session, *, older_than: timedelta | None = None) -> dict:
    """Re-score every active job. Used by the daily scheduler and the admin endpoint.

    Scores decay-in over time (a job that was fine on day 1 becomes stale on day
    45), so this has to re-run on a schedule rather than only at ingest.
    """
    now = datetime.now(timezone.utc)
    query = db.query(Job)
    if older_than is not None:
        cutoff = now - older_than
        query = query.filter((Job.ghost_checked_at.is_(None)) | (Job.ghost_checked_at < cutoff))

    counts = {"clean": 0, "caution": 0, "likely_ghost": 0}
    scanned = 0
    for job in query.all():
        apply_score(db, job, now=now)
        counts[classify(job.ghost_score)] += 1
        scanned += 1

    db.commit()
    return {"scanned": scanned, **counts}
