"""Run a scheduled job immediately, from the shell.

The daily jobs fire between 07:00 and 09:00 UTC. After downtime — or after
any change worth testing — waiting until morning to find out whether it
worked is a day per attempt, and the Admin buttons need a browser session
the person fixing a container usually does not have open.

    python -m app.scripts.run_now aggregate
    python -m app.scripts.run_now sync-mailboxes
    python -m app.scripts.run_now all

`aggregate` and `sync-mailboxes` are safe to repeat: both dedupe on
source_url, and a mailbox resumes from its stored UID, so a second run reads
nothing it has already read.

`digest` and `autopilot` are not listed. They send mail and act in somebody's
name, and a command that is easy to run twice should not be able to mail
every user twice. Those stay on the schedule, where running once a day is
the whole design.
"""

import argparse
import logging

from app.services.scheduler import _run_daily_aggregation, _run_email_sync

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

JOBS = {
    "aggregate": ("board aggregation", _run_daily_aggregation),
    "sync-mailboxes": ("alert mailbox sync", _run_email_sync),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a scheduled job now.")
    parser.add_argument("job", choices=[*JOBS, "all"])
    args = parser.parse_args()

    names = list(JOBS) if args.job == "all" else [args.job]
    for name in names:
        label, run = JOBS[name]
        print(f"\n--- {label} ---")
        run()
    print("\nDone. Check the result with: python -m app.scripts.diagnose_feed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
