"""Which of a user's CVs a given job should use.

A person applying for engineering roles and sales roles has two different
stories to tell. Scoring, tailoring and outreach all have to pick one, and
they all have to pick the same one — a job scored against the engineering CV
and then applied for with the sales CV is worse than having only one CV.

The rule is deterministic and free: the job already carries a `lane`, and a
CV claims the lanes it is for. No model call, nothing to charge for, and the
UI can state plainly which CV a job will use before anything is spent.

The alternative was scoring every job against every CV and keeping the best.
That is better on paper and multiplies the cost of the one operation that
already dominates the AI bill, for a decision the person can make themselves
in one click.
"""

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User


def all_for(db: Session, user: User) -> list[Resume]:
    """Every CV this user holds, primary first, then newest."""
    return (
        db.query(Resume)
        .filter(Resume.user_id == user.id)
        .order_by(desc(Resume.is_primary), desc(Resume.updated_at))
        .all()
    )


def primary(db: Session, user: User) -> Resume | None:
    """The fallback CV, or the newest if nothing is marked.

    Falls back rather than returning None so that an account mid-way through
    a change — a primary just deleted, none promoted yet — still works.
    """
    resumes = all_for(db, user)
    return resumes[0] if resumes else None


def for_job(db: Session, user: User, job: Job | None) -> Resume | None:
    """The CV to use for this job: the one claiming its lane, else the primary."""
    resumes = all_for(db, user)
    if not resumes:
        return None
    if job is None or job.lane is None:
        return resumes[0]

    lane = job.lane.value if hasattr(job.lane, "value") else str(job.lane)
    for resume in resumes:  # already ordered primary-first, then newest
        if lane in (resume.lanes or []):
            return resume
    return resumes[0]


def group_by_resume(db: Session, user: User, jobs: list[Job]) -> list[tuple[Resume, list[Job]]]:
    """The same choice, made once per job and then batched.

    Scoring sends many jobs in one call, so the jobs have to be grouped by
    the CV they will be scored against. With one CV this is one group and one
    call, exactly as before; the cost only rises for somebody who actually
    keeps several, which is the trade they chose by uploading them.
    """
    resumes = all_for(db, user)
    if not resumes:
        return []

    buckets: dict[str, tuple[Resume, list[Job]]] = {}
    for job in jobs:
        resume = for_job(db, user, job)
        if resume is None:
            continue
        bucket = buckets.setdefault(str(resume.id), (resume, []))
        bucket[1].append(job)
    return list(buckets.values())


def ensure_one_primary(db: Session, user: User, prefer: Resume | None = None) -> None:
    """Exactly one primary, with `prefer` winning if given.

    Called after every upload, delete and primary change. Enforced here and
    not by a constraint because the moment between deleting the primary and
    promoting the next one has to be survivable rather than a 500.
    """
    resumes = all_for(db, user)
    if not resumes:
        return

    chosen = prefer if prefer is not None and prefer.user_id == user.id else None
    if chosen is None:
        chosen = next((r for r in resumes if r.is_primary), resumes[0])

    for resume in resumes:
        resume.is_primary = resume.id == chosen.id
