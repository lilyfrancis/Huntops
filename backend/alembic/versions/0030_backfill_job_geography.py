"""backfill the geography and salary the filters read

Revision ID: 0030_backfill_geo
Revises: 0029_source_preference
Create Date: 2026-10-17

Migration 0026 added the columns and derived `work_mode` from `is_remote`.
It should have derived all three, and did not, so every row written before
it kept the old inference: `restricted_to` null on almost everything, which
the filter reads as "open to everybody", and `is_remote` false on the
remote-only boards whose location field names the eligible country rather
than an address.

The fix shipped as a script instead, which meant it only ran if somebody
remembered to run it — and nobody did, because pulling code does not execute
it and nothing anywhere said it was outstanding. A data fix that a deploy
does not apply is a data fix that does not happen. It belongs here, where
the migrate container runs it on every release.

The salary columns are here for the same reason. Three parser faults lost
figures outright or stored them twelve times too small, and the repair was
also a script, also unrun. Both read free text this migration never writes —
`location`, `description`, `source`, `salary_range` — so both are idempotent
and skip rows already holding the right values.

The scripts stay, for re-running after either parser improves again.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_backfill_geo"
down_revision: Union[str, None] = "0029_source_preference"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

CHUNK = 1000


def upgrade() -> None:
    try:
        from app.services.aggregation import derive_geography
        from app.services.salary_parsing import parse_salary
    except Exception as e:  # pragma: no cover - only if the package moves
        # Loud, and not fatal. Failing a release over a backfill would be
        # worse than the stale data, and the script is still there.
        print(
            f"\n  SKIPPED job backfill: {e}\n"
            "  Run it by hand: python -m app.scripts.rederive_job_geo\n"
            "                  python -m app.scripts.backfill_salaries\n"
        )
        return

    bind = op.get_bind()
    total = bind.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar() or 0
    changed = 0
    repriced = 0
    offset = 0

    while offset < total:
        rows = bind.execute(
            sa.text(
                "SELECT id, source, location, description, is_remote, restricted_to, "
                "work_mode, salary_range, salary_annual_min, salary_annual_max, salary_currency "
                "FROM jobs ORDER BY id LIMIT :limit OFFSET :offset"
            ),
            {"limit": CHUNK, "offset": offset},
        ).mappings().all()
        offset += CHUNK

        updates = []
        prices = []
        for row in rows:
            is_remote, restricted_to, work_mode = derive_geography(
                row["source"], row["location"], row["description"], row["is_remote"]
            )
            if (
                row["is_remote"] == is_remote
                and row["restricted_to"] == restricted_to
                and row["work_mode"] == work_mode
            ):
                continue
            updates.append({
                "id": row["id"], "is_remote": is_remote,
                "restricted_to": restricted_to, "work_mode": work_mode,
            })

        for row in rows:
            parsed = parse_salary(row["salary_range"])
            if parsed is None:
                continue
            if (
                row["salary_annual_min"] == parsed["annual_min"]
                and row["salary_annual_max"] == parsed["annual_max"]
                and row["salary_currency"] == parsed["currency"]
            ):
                continue
            prices.append({
                "id": row["id"], "lo": parsed["annual_min"],
                "hi": parsed["annual_max"], "cur": parsed["currency"],
            })

        if prices:
            bind.execute(
                sa.text(
                    "UPDATE jobs SET salary_annual_min = :lo, salary_annual_max = :hi, "
                    "salary_currency = :cur WHERE id = :id"
                ),
                prices,
            )
            repriced += len(prices)

        if updates:
            bind.execute(
                sa.text(
                    "UPDATE jobs SET is_remote = :is_remote, restricted_to = :restricted_to, "
                    "work_mode = :work_mode WHERE id = :id"
                ),
                updates,
            )
            changed += len(updates)

    print(
        f"  Backfilled {total} job(s): geography on {changed}, salary on {repriced}."
    )


def downgrade() -> None:
    """Nothing to undo.

    The previous values were wrong rather than different, and they were not
    recorded anywhere, so there is nothing to restore them from. Dropping the
    columns is 0026's and 0008's job.
    """
