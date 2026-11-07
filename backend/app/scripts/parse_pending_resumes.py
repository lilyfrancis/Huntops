"""Read the CVs that were accepted while the model was unavailable.

An upload never fails for want of a parse any more: the file is kept and the
row is marked pending. This is the other half — it catches those up once the
provider is answering again.

    python -m app.scripts.parse_pending_resumes --dry-run
    python -m app.scripts.parse_pending_resumes

It also runs each morning from the scheduler, so in the ordinary case nobody
has to call it. Run it by hand after topping up an account, to avoid making
a user wait a day for matches they are already paying for.

Stops at the first provider failure rather than working through the queue.
If the account is still out of credit, the first call says so and the next
two hundred will say the same at the same price.
"""

import argparse
import logging

from app.db.base import SessionLocal
from app.models.resume import Resume
from app.services import resumes as resumes_service
from app.services.ai_client import AIResponseError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_pending(dry_run: bool = False, limit: int = 200) -> dict:
    db = SessionLocal()
    done, failed = 0, 0
    try:
        pending = (
            db.query(Resume)
            .filter(Resume.parse_status == "pending")
            .order_by(Resume.created_at)
            .limit(limit)
            .all()
        )
        if dry_run:
            print(f"{len(pending)} CV(s) waiting to be read. Nothing was changed (--dry-run).")
            return {"pending": len(pending), "parsed": 0, "written": False}

        for resume in pending:
            try:
                parsed = resumes_service.parse_resume(resume.raw_text)
            except AIResponseError as e:
                # One failure means the provider is down or the account is
                # out of credit, and the next two hundred calls would fail
                # the same way at the same price.
                logger.error("Stopping: %s", e)
                failed += 1
                break
            resume.parse_status = "parsed"
            resume.parsed_skills = parsed.skills
            resume.experience_years = parsed.experience_years
            resume.education = parsed.education
            resume.summary = parsed.summary
            resume.achievements = parsed.achievements
            # Committed one at a time: a failure halfway through must not
            # throw away the ones already paid for.
            db.commit()
            done += 1

        remaining = db.query(Resume).filter(Resume.parse_status == "pending").count()
        summary = {"parsed": done, "stopped_early": bool(failed), "still_pending": remaining}
        logger.info("Pending CVs read: %s", summary)
        return summary
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read CVs stored while the model was unavailable.")
    parser.add_argument("--dry-run", action="store_true", help="Say how many are waiting and stop.")
    parse_pending(dry_run=parser.parse_args().dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
