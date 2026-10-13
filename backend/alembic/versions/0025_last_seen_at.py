"""record when an account was last in use

Revision ID: 0025_last_seen_at
Revises: 0024_multiple_resumes
Create Date: 2026-10-13

The morning run scored jobs for every job seeker who had ever registered. A
dormant account costs exactly as much as the best customer and reads none of
it, so the bill grew with sign-ups rather than with use.

Left null on every existing row, and null is treated as active. Backfilling
it with `created_at` would mark anyone who signed up more than three weeks
ago as dormant on the morning this deploys — including people using the
product daily, who would simply stop receiving their digest with no
explanation. They each stamp the column the next time they sign in.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_last_seen_at"
down_revision: Union[str, None] = "0024_multiple_resumes"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
