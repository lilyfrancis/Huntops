"""What a given viewer is allowed to see of a job.

The concierge only works if the user cannot simply go and do it themselves.
Showing the company name next to a link-free listing is an invitation to
search for it — the work is a twenty-second web search away, and the
product's whole promise is that they do not have to do it.

So an external listing a non-Elite user has not committed to shows enough
to want it and not enough to find it: the salary, the location, the shape
of the title. Not the company, not the description, not the source.

Redaction happens here, on the server, before serialisation. Hiding these
fields in the UI while the API still returns them would be undone by
opening the network tab, which is not a meaningful lock at all.
"""

import math

from app.models.enums import UserRole
from app.models.job import Job
from app.models.user import User

MASK = "•"


def is_locked(job: Job, viewer: User | None, unlocked_job_ids: set | None = None) -> bool:
    """Whether this viewer must be shown a redacted version.

    Credits decide this, not the plan. Every tier sees as many listings as
    their balance covers, and a plan is how many credits you get rather than
    a different set of walls — which means one rule to explain, one thing to
    buy, and no paying customer meeting a wall they cannot pay past.

    Internal listings are never locked: the user applies to those through us
    anyway, so there is nothing to route around and nothing to protect.
    """
    if job.source == "internal":
        return False
    if viewer is None:
        return True
    if viewer.role != UserRole.job_seeker:
        return False
    # Unlocked by paying to look, or by applying — either is a commitment.
    return job.id not in (unlocked_job_ids or set())


def mask_title(title: str) -> str:
    """Keep the front of the title, mask the rest.

    Enough to tell a sales role from an engineering one — which is what
    makes it worth unlocking — and not enough to paste into a search box.
    Letters become dots rather than the words disappearing, so the length
    still reads as a real title rather than as missing data.
    """
    words = title.split()
    if not words:
        return title
    keep = min(2, math.ceil(len(words) / 2))
    masked = [MASK * min(len(w), 9) for w in words[keep:]]
    return " ".join(words[:keep] + masked)


def redact(job: Job) -> dict:
    """The fields to override when a job is locked.

    Salary stays, deliberately. It is the single strongest reason to unlock
    something, and hiding it would make every locked row look the same.
    """
    return {
        "title": mask_title(job.title),
        "company_name": None,
        "employer_name": None,
        # The description names the company as often as not, so withholding
        # the company while showing it would leak exactly what it protects.
        "description": "Unlock this job to read the full description.",
        "source": "hidden",
        "source_url": None,
    }
