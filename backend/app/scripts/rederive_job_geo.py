"""Re-derive who each stored job is open to.

The eligibility filter reads three columns: `is_remote`, `restricted_to` and
`work_mode`. Every job already in the database was written by the old
inference, which got all three wrong in ways that make the filter look
broken rather than strict:

  - The remote-only boards were not treated as remote. Remotive and Jobicy
    put the country a candidate must be *in* where other boards put an
    address, so `is_remote` was inferred from the word "remote" appearing in
    "Canada" — it does not — and a fully remote role open to Canadians was
    stored as an onsite Toronto job.
  - `restricted_to` only ever fired on three phrasings: "US only", "UK only",
    "EU only". Everything else came out null, and null means "open to
    everybody" to the filter. So a US-only remote job stored as
    (is_remote=true, restricted_to=null) is admitted for a user in Lagos —
    which is exactly the "why am I still seeing USA" complaint.
  - `work_mode` was backfilled by migration 0026 from `is_remote`, so it
    inherited the first fault.

Nothing is fetched and no model is called. The location text and description
are already on the row; this reads them again with the inference that works.

    python -m app.scripts.rederive_job_geo --dry-run
    python -m app.scripts.rederive_job_geo

Run it once after deploying, before judging whether the eligibility filter
works — until it has run, the filter is correct and the data under it is not.
"""

import argparse
import logging

from app.db.base import SessionLocal
from app.models.job import Job
from app.services.aggregation import derive_geography

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def rederive(dry_run: bool = False) -> dict:
    db = SessionLocal()
    changed = 0
    now_restricted = 0
    now_remote = 0
    unchanged = 0
    try:
        jobs = db.query(Job).all()
        for job in jobs:
            is_remote, restricted_to, work_mode = derive_geography(
                job.source, job.location, job.description, job.is_remote
            )

            if (
                job.is_remote == is_remote
                and job.restricted_to == restricted_to
                and job.work_mode == work_mode
            ):
                unchanged += 1
                continue

            if restricted_to is not None and job.restricted_to is None:
                now_restricted += 1
            if is_remote and not job.is_remote:
                now_remote += 1
            changed += 1

            if not dry_run:
                job.is_remote = is_remote
                job.restricted_to = restricted_to
                job.work_mode = work_mode

        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    summary = {
        "considered": changed + unchanged,
        "changed": changed,
        "newly_restricted": now_restricted,
        "newly_remote": now_remote,
        "unchanged": unchanged,
        "written": not dry_run,
    }
    # `newly_restricted` is the number that matters: each of those was a job
    # the eligibility filter was admitting for everybody, including people who
    # cannot apply for it.
    logger.info("Job geography re-derived: %s", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-derive job eligibility columns.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change and stop.")
    rederive(dry_run=parser.parse_args().dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
