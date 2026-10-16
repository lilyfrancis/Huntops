"""Why a feed is empty, answered in one page of output.

"It is still not showing the email jobs" has at least a dozen causes spread
across four subsystems — the mailbox never connected, the sender was not
recognised, the extractor returned nothing, the jobs are there but a
preference is excluding them — and from the outside all of them look
identical. This walks the whole path and prints where it stops.

    python -m app.scripts.diagnose_feed
    python -m app.scripts.diagnose_feed --user you@example.com

With a user it adds the part that is usually the answer: a funnel counting
how many jobs survive each of that user's filters, one line per setting. The
clauses come from preferences.filter_stages, the same list the real feed
uses, so this cannot describe a filter the feed does not apply.

Read-only. Nothing is fetched, written, or sent to a model.
"""

import argparse
from datetime import datetime, timezone

from sqlalchemy import desc, func

from app.db.base import SessionLocal
from app.models.alert_mailbox import AlertMailbox
from app.models.email_sync_run import EmailSyncRun
from app.models.ingestion_run import IngestionRun
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import User
from app.services import preferences
from app.services.ghost_detection import GHOST_THRESHOLD


def _rule(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def _mailboxes(db) -> None:
    _rule("Alert mailboxes")
    boxes = db.query(AlertMailbox).all()
    if not boxes:
        print("  NONE CONFIGURED — nothing can arrive from email at all.")
        print("  Add one in Admin -> Alert mailboxes.")
        return
    for box in boxes:
        print(f"  {box.email_address}  folder={box.imap_folder!r}  market={box.market!r}")
        print(f"    active={box.is_active}  last_synced={box.last_synced_at}  last_uid={box.last_seen_uid}")
        if box.lanes:
            print(f"    restricted to lanes {box.lanes} — jobs outside these are dropped at ingest")
        if box.last_error:
            print(f"    LAST ERROR: {box.last_error[:300]}")


def _sync_runs(db) -> None:
    _rule("Recent mailbox syncs (newest first)")
    runs = db.query(EmailSyncRun).order_by(desc(EmailSyncRun.started_at)).limit(10).all()
    if not runs:
        print("  No sync has ever run. Press 'Sync now' in Admin -> Alert mailboxes,")
        print("  or check that the scheduler container is up and ENABLE_SCHEDULED_EMAIL_SYNC is true.")
        return
    for run in runs:
        print(
            f"  {run.started_at}  {run.status:8} "
            f"fetched={run.fetched_count:<4} extracted={run.extracted_count:<4} inserted={run.inserted_count}"
        )
        if run.error:
            print(f"    {run.error[:400]}")
    newest = runs[0]
    if newest.fetched_count and not newest.extracted_count:
        print("\n  Mail arrived and none of it was recognised as a job alert.")
        print("  The sender domain is not on the allowlist, or a forwarder rewrote the From")
        print("  header. The skipped domains are on the mailbox, under LAST ERROR in the")
        print("  first section above — not on the run, which is why it still says success.")
        print("  Add the real ones in Admin -> Integrations.")
    elif not newest.fetched_count:
        print("\n  No mail was fetched. Either the folder is wrong, or every message in it")
        print("  is already behind the stored UID cursor, or the alerts are older than")
        print("  EMAIL_SYNC_LOOKBACK_DAYS on a first sync.")


def _freshness(db) -> None:
    """Whether anything has run lately.

    Every scheduled job lives in one container, so they stop together and
    none of them says so. A pool at its daily cap looks healthy long after
    the last thing was added to it, and a mailbox that has not been read for
    a fortnight still shows its last sync as "success" — the failure mode is
    an absence, and nothing in the product was reporting absences.
    """
    _rule("Freshness")
    now = datetime.now(timezone.utc)

    def _age(when) -> str | None:
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        days = (now - when).days
        return f"{when:%Y-%m-%d %H:%M} ({days} day(s) ago)"

    newest_job = db.query(func.max(Job.created_at)).scalar()
    newest_sync = db.query(func.max(EmailSyncRun.started_at)).scalar()
    newest_ingest = db.query(func.max(IngestionRun.started_at)).scalar()

    print(f"  newest job in the pool   {_age(newest_job) or 'never'}")
    print(f"  last board aggregation   {_age(newest_ingest) or 'never'}")
    print(f"  last mailbox sync        {_age(newest_sync) or 'never'}")

    stale = [
        name for name, when in (
            ("board aggregation", newest_ingest), ("mailbox sync", newest_sync),
        )
        if when is None or (now - (when if when.tzinfo else when.replace(tzinfo=timezone.utc))).days >= 2
    ]
    if stale:
        print(f"\n  STALE: {' and '.join(stale)} has not run in days.")
        print("  Every scheduled job runs in the `scheduler` container, so they stop")
        print("  together. Check it:")
        print("    docker compose -f docker-compose.prod.yml ps scheduler")
        print("    docker compose -f docker-compose.prod.yml logs --tail=100 scheduler")
        print("  It needs RUN_SCHEDULER=true, and it registers its jobs at startup —")
        print("  a container that crashed on boot registers nothing and reports nothing.")


def _supply(db) -> None:
    _rule("Live pool, by source")
    rows = (
        db.query(Job.source, func.count(Job.id))
        .filter(Job.status == JobStatus.active)
        .group_by(Job.source)
        .order_by(desc(func.count(Job.id)))
        .all()
    )
    if not rows:
        print("  The pool is empty.")
        return
    for source, count in rows:
        marker = "  <- from your alert mailboxes" if (source or "").startswith("email-") else ""
        print(f"  {count:>6}  {source}{marker}")

    from_email = sum(c for s, c in rows if (s or "").startswith("email-"))
    print(f"\n  {from_email} of {sum(c for _s, c in rows)} active jobs came from email alerts.")


def _geography(db) -> None:
    _rule("Geography the eligibility filter reads")
    active = db.query(Job).filter(Job.status == JobStatus.active)
    total = active.count()
    restricted = active.filter(Job.restricted_to.isnot(None)).count()
    print(f"  {restricted:>6}  carry a restriction (only these can be excluded by eligibility)")
    print(f"  {active.filter(Job.restricted_to.is_(None), Job.is_remote.is_(True)).count():>6}  remote, no restriction — treated as open to everybody")
    print(f"  {active.filter(Job.restricted_to.is_(None), Job.is_remote.is_(False)).count():>6}  neither — invisible to eligibility unless the location matches")
    if total > 20 and restricted / total < 0.1:
        print("\n  Almost nothing carries a restriction, so eligibility is reading nulls as")
        print("  'open to everybody'. Run: python -m app.scripts.rederive_job_geo")


def _funnel(db, email: str) -> None:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        print(f"\nNo account for {email}.")
        return

    prefs = preferences.get_or_create(db, user)
    _rule(f"What {email} is asking for")
    for field in (
        "eligibility", "work_modes", "experience_levels", "title_keywords",
        "lanes", "job_types", "target_markets", "locations",
        "salary_min_annual", "salary_currency", "posted_within_days", "remote_only",
    ):
        value = getattr(prefs, field)
        print(f"  {field:20} {value if value not in ([], None, False) else '(not set)'}")

    _rule(f"How many jobs survive each filter, for {email}")
    query = db.query(Job).filter(Job.status == JobStatus.active)
    print(f"  {query.count():>6}  active jobs")

    query = query.filter((Job.ghost_score.is_(None)) | (Job.ghost_score < GHOST_THRESHOLD))
    print(f"  {query.count():>6}  after hiding likely ghost listings")

    # The same clauses the real feed applies, in the same order.
    for label, clause in preferences.filter_stages(prefs):
        before = query.count()
        query = query.filter(clause)
        after = query.count()
        lost = before - after
        flag = "   <-- this is what empties it" if after == 0 and before > 0 else ""
        print(f"  {after:>6}  after {label}   (-{lost}){flag}")

    final = query.count()
    from_email = query.filter(Job.source.like("email-%")).count()
    print(f"\n  {final} job(s) in this feed, {from_email} of them from email alerts.")
    if final and not from_email:
        print("  The pool has email-sourced jobs but none of them clear this user's filters.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain an empty or unexpected feed.")
    parser.add_argument("--user", help="Email address of the account to trace.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        _freshness(db)
        _mailboxes(db)
        _sync_runs(db)
        _supply(db)
        _geography(db)
        if args.user:
            _funnel(db, args.user)
        else:
            print("\nPass --user you@example.com to trace one account's filters.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
