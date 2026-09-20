"""credits, not the plan, decide which listings a user sees in full

Revision ID: 0021_job_unlocks
Revises: 0020_concierge
Create Date: 2026-09-21

Locking by tier meant a paying Pro customer met a wall they could not pay
past, which is where churn comes from. Credits are now the only gate: every
plan sees as many listings as its balance covers, and a plan is how many
credits you get rather than a different set of walls.

An unlock is permanent. Charging again to re-read a listing someone already
paid for would make people afraid to click, which is the opposite of what a
paid unlock is for.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_job_unlocks"
down_revision: Union[str, None] = "0020_concierge"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "job_unlocks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_unlocks_user_id", "job_unlocks", ["user_id"])
    op.create_index("ix_job_unlocks_job_id", "job_unlocks", ["job_id"])
    op.create_unique_constraint("uq_job_unlock_user_job", "job_unlocks", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_constraint("uq_job_unlock_user_job", "job_unlocks", type_="unique")
    op.drop_index("ix_job_unlocks_job_id", table_name="job_unlocks")
    op.drop_index("ix_job_unlocks_user_id", table_name="job_unlocks")
    op.drop_table("job_unlocks")
