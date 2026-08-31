"""Re-parse salary_range into the normalized salary columns.

Run once after migration 0008, and any time the parser improves:

    python -m app.scripts.backfill_salaries

Idempotent — re-running re-derives the same values, and rows whose string
can't be parsed are simply left null.
"""

import logging

from app.db.base import SessionLocal
from app.models.job import Job
from app.services.salary_parsing import parse_salary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill() -> dict:
    db = SessionLocal()
    parsed_count = 0
    skipped = 0
    try:
        jobs = db.query(Job).filter(Job.salary_range.isnot(None)).all()
        for job in jobs:
            parsed = parse_salary(job.salary_range)
            if parsed is None:
                skipped += 1
                continue
            job.salary_annual_min = parsed["annual_min"]
            job.salary_annual_max = parsed["annual_max"]
            job.salary_currency = parsed["currency"]
            parsed_count += 1
        db.commit()
    finally:
        db.close()

    summary = {"considered": parsed_count + skipped, "parsed": parsed_count, "unparseable": skipped}
    logger.info("Salary backfill complete: %s", summary)
    return summary


if __name__ == "__main__":
    backfill()
