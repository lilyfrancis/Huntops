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
from app.services import matching, preferences, visibility

settings = get_settings()


def get_top_matches(db: Session, user: User) -> list[tuple[JobMatch, Job]]:
    """Reads whatever's already scored — this never triggers an AI call.
    The scheduled digest job scores first, then calls this; the interactive
    preview endpoint just renders what's there."""
    # Through the user's own filters, like the feed and autopilot.
    #
    # This read every score the user had ever been given, and scores are kept
    # forever so nothing is paid for twice — so a job scored before they
    # narrowed their job families was mailed to them every morning
    # afterwards, and no setting on the preferences page could stop it.
    prefs = preferences.get_or_create(db, user)
    rows = (
        preferences.feed_query(db, prefs)
        .join(JobMatch, (JobMatch.job_id == Job.id) & (JobMatch.user_id == user.id))
        .add_entity(JobMatch)
        # The threshold moved here from persistence: every score is kept now,
        # so that a job already considered is never paid for twice, and the
        # places that mean "worth your morning" filter for themselves.
        .filter(JobMatch.fit_score >= matching.MIN_SCORE_THRESHOLD)
        .order_by(desc(JobMatch.geo_boost_applied), desc(JobMatch.fit_score))
        .limit(settings.DIGEST_MAX_JOBS)
        .all()
    )
    # feed_query selects Job first; every caller here expects (match, job).
    return [(match, job) for job, match in rows]


def format_digest_email(
    matches: list[tuple[JobMatch, Job]], unlocked_job_ids: set | None = None
) -> tuple[str, str]:
    """The daily digest, redacted the same way the feed is.

    This was naming the company on every match. The whole point of locking a
    listing is that the company is what lets somebody go around us — and
    mailing it to them every morning is a more convenient leak than the
    website would have been.
    """
    if not matches:
        return "Your JobQuick AI digest", "No new high-fit matches today — check back tomorrow."

    unlocked = unlocked_job_ids or set()
    home_market_count = sum(1 for match, _ in matches if match.geo_boost_applied)

    lines = []
    for match, job in matches:
        shown = visibility.is_locked(job, None) and job.id not in unlocked
        title = visibility.mask_title(job.title) if shown else job.title
        where = "company hidden" if shown else (job.company_name or "a company")
        salary = f", {job.salary_range}" if job.salary_range else ""
        lines.append(
            f"{'[home market] ' if match.geo_boost_applied else ''}{title} at "
            f"{where} ({job.location}{salary}) — fit {round(match.fit_score)}"
        )

    subject = f"JobQuick AI digest: {len(matches)} match{'es' if len(matches) != 1 else ''}"
    if home_market_count:
        subject += f" ({home_market_count} home-market)"

    body = "\n".join(lines)
    return subject, body


def format_digest_whatsapp(
    user: User, matches: list[tuple[JobMatch, Job]], unlocked_job_ids: set | None = None
) -> list[str] | None:
    """Parameters for the approved template, or None when there is nothing to say.

    Returns None rather than an empty digest on purpose. A daily "no matches
    today" email is ignorable; the same thing as a WhatsApp notification every
    morning gets the number blocked, and a block is permanent.

    Order matches the template:
      "Hi {{1}}, you have {{2}} new job matches on JobQuick AI today. Top one: {{3}}"
    """
    if not matches:
        return None

    top_match, top_job = matches[0]
    unlocked = unlocked_job_ids or set()
    locked = visibility.is_locked(top_job, None) and top_job.id not in unlocked
    title = visibility.mask_title(top_job.title) if locked else top_job.title
    where = "a hidden company" if locked else (top_job.company_name or "a company")
    # Meta rejects a parameter containing a newline or a run of spaces, and
    # job titles arrive from job boards with both.
    top = " ".join(f"{title} at {where}".split())

    return [
        user.full_name.split()[0] if user.full_name.strip() else "there",
        str(len(matches)),
        top[:120],
    ]
