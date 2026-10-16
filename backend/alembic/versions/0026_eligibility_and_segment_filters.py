"""say what you can apply for, not where the listing came from

Revision ID: 0026_eligibility_filters
Revises: 0025_last_seen_at
Create Date: 2026-10-16

Two columns the feed could not answer a question without.

`jobs.work_mode` exists because `is_remote` is a boolean and hybrid is not a
third state of a boolean. A listing that says "remote, 2 days in the Lagos
office" was stored as remote, and was being shown to people who cannot get
to Lagos.

The six `user_preferences` columns are the filters an ordinary job board has
and this one did not: who may apply (eligibility), how the work is done,
what it pays, how fresh it is, and the exact role. Without them the only
narrowing available was market + lane, which is why a marketing candidate
saw "Senior Backend Manager" — nothing had been asked of the query.

`work_mode` is backfilled from `is_remote`, with a hybrid pass over the text
afterwards. Everything on preferences defaults to empty, and empty means no
filter, so nobody's feed changes until they choose something.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_eligibility_filters"
down_revision: Union[str, None] = "0025_last_seen_at"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("work_mode", sa.String(length=10), nullable=True))
    op.create_index("ix_jobs_work_mode", "jobs", ["work_mode"])

    # Order matters: the hybrid pass runs second so it overrides, because a
    # listing saying both "remote" and "hybrid" means hybrid.
    op.execute("UPDATE jobs SET work_mode = CASE WHEN is_remote THEN 'remote' ELSE 'onsite' END")
    # LOWER(...) LIKE rather than ILIKE so the migration also runs on SQLite,
    # which is what a developer's throwaway database is.
    op.execute(
        "UPDATE jobs SET work_mode = 'hybrid' "
        "WHERE LOWER(location) LIKE '%hybrid%' OR LOWER(description) LIKE '%hybrid%'"
    )

    for column in (
        sa.Column("eligibility", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("work_modes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("title_keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("salary_min_annual", sa.Float(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("posted_within_days", sa.Integer(), nullable=True),
    ):
        op.add_column("user_preferences", column)


def downgrade() -> None:
    for name in (
        "posted_within_days", "salary_currency", "salary_min_annual",
        "title_keywords", "work_modes", "eligibility",
    ):
        op.drop_column("user_preferences", name)

    op.drop_index("ix_jobs_work_mode", table_name="jobs")
    op.drop_column("jobs", "work_mode")
