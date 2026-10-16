"""Re-parse salary_range into the normalized salary columns.

Run once after migration 0008, and any time the parser improves:

    python -m app.scripts.backfill_salaries --dry-run
    python -m app.scripts.backfill_salaries

Idempotent — re-running re-derives the same values, and rows whose string
can't be parsed are left exactly as they were, existing numbers included.
This only ever replaces a value with a better reading of the same string.

Nothing is fetched and no model is called: the free-text salary is already on
the row, so this is arithmetic over data we hold. Which is what makes it the
fix for a parser bug — and there were three, each of which lost a figure
quietly. The "m" of "monthly" was read as a millions suffix; the plausibility
ceiling was a flat ten million, calibrated on dollars, which discarded any
Nigerian salary above roughly ₦833k a month; and "a month" was not recognised
as a period, so "₦600,000 a month" was stored as ₦600,000 a year.

`--dry-run` reports what would change and writes nothing, which matters here
because the second and third faults mean some rows already hold a number —
a wrong one — rather than nothing.
"""

import argparse
import logging

from app.db.base import SessionLocal
from app.models.job import Job
from app.services.salary_parsing import parse_salary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill(dry_run: bool = False) -> dict:
    db = SessionLocal()
    recovered = 0  # had no numbers, now does
    corrected = 0  # had numbers, and they were wrong
    unchanged = 0
    skipped = 0
    try:
        jobs = db.query(Job).filter(Job.salary_range.isnot(None)).all()
        for job in jobs:
            parsed = parse_salary(job.salary_range)
            if parsed is None:
                skipped += 1
                continue

            if (
                job.salary_annual_min == parsed["annual_min"]
                and job.salary_annual_max == parsed["annual_max"]
                and job.salary_currency == parsed["currency"]
            ):
                unchanged += 1
                continue

            if job.salary_annual_max is None:
                recovered += 1
            else:
                corrected += 1
                # Printed rather than counted: a row whose stored figure
                # changes is a number somebody may already have filtered or
                # negotiated against, and it should be possible to look at the
                # list before accepting it.
                logger.info(
                    "  %-48s %-28s %s -> %s %s",
                    job.title[:48], (job.salary_range or "")[:28],
                    job.salary_annual_max, parsed["annual_max"], parsed["currency"],
                )

            if not dry_run:
                job.salary_annual_min = parsed["annual_min"]
                job.salary_annual_max = parsed["annual_max"]
                job.salary_currency = parsed["currency"]

        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    summary = {
        "considered": recovered + corrected + unchanged + skipped,
        "recovered": recovered,
        "corrected": corrected,
        "unchanged": unchanged,
        "unparseable": skipped,
        "written": not dry_run,
    }
    logger.info("Salary backfill complete: %s", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-parse stored salary strings.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change and stop.")
    backfill(dry_run=parser.parse_args().dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
