"""Re-read the salary text already stored on every job.

The parser had three faults, and all three failed by storing nothing or by
storing a figure twelve times too small:

  - the "m" of "monthly" was read as a millions suffix, so "₦250,000 monthly"
    became two hundred and fifty billion naira and was discarded;
  - the plausibility ceiling was a flat ten million, calibrated on dollars, so
    every Nigerian listing paying above about ₦833k a month was discarded;
  - "a month" was not recognised as a period, so "₦600,000 a month" was
    stored as ₦600,000 a year.

The free-text `salary_range` was kept on every one of those rows, so the
numbers can simply be parsed again. Nothing is fetched and no model is
called; this is arithmetic over data already in the table.

    python -m app.scripts.reparse_salaries --dry-run
    python -m app.scripts.reparse_salaries

A job whose text still will not parse is left exactly as it was, including
its existing numbers — this only ever replaces a value with a better reading
of the same string, or leaves it alone.
"""

import argparse

from app.db.base import SessionLocal
from app.models.job import Job
from app.services.salary_parsing import parse_salary


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-parse stored salary strings.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change and stop.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(Job.salary_range.isnot(None)).all()
        recovered, corrected, unparseable = 0, 0, 0

        for job in jobs:
            parsed = parse_salary(job.salary_range)
            if parsed is None:
                unparseable += 1
                continue

            was_missing = job.salary_annual_max is None
            changed = (
                job.salary_annual_min != parsed["annual_min"]
                or job.salary_annual_max != parsed["annual_max"]
                or job.salary_currency != parsed["currency"]
            )
            if not changed:
                continue

            if was_missing:
                recovered += 1
            else:
                corrected += 1
                print(
                    f"  {job.title[:48]:48} {job.salary_range[:28]:28} "
                    f"{job.salary_annual_max} -> {parsed['annual_max']} {parsed['currency']}"
                )

            if not args.dry_run:
                job.salary_annual_min = parsed["annual_min"]
                job.salary_annual_max = parsed["annual_max"]
                job.salary_currency = parsed["currency"]

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print(
            f"{len(jobs)} job(s) carry salary text. "
            f"{recovered} had no numbers and now do, {corrected} had the wrong ones, "
            f"{unparseable} still cannot be read."
            + (" Nothing was written (--dry-run)." if args.dry_run else "")
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
