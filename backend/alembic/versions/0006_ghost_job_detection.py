"""ghost job detection fields

Revision ID: 0006_ghost_detection
Revises: 0005_candidate_info
Create Date: 2026-08-31
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ghost_detection"
down_revision: Union[str, None] = "0005_candidate_info"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("ghost_score", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("ghost_flags", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("ghost_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_ghost_score", "jobs", ["ghost_score"])

    # Backfill to an empty list so the column can be NOT NULL, matching the model.
    op.execute("UPDATE jobs SET ghost_flags = '[]'")
    op.alter_column("jobs", "ghost_flags", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_ghost_score", table_name="jobs")
    op.drop_column("jobs", "ghost_checked_at")
    op.drop_column("jobs", "ghost_flags")
    op.drop_column("jobs", "ghost_score")
