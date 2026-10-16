"""filter by seniority

Revision ID: 0027_seniority_filter
Revises: 0026_eligibility_filters
Create Date: 2026-10-16

"Engineer" and "Senior Engineer" are the same role at two levels, and
somebody who wants one does not want the other. Job families cannot express
that and neither can a title keyword — "engineer" matches both — so a feed
of "Senior Backend Manager" roles had no setting that would have stopped it.

Empty means no filter, as everywhere else here, so no existing feed changes.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_seniority_filter"
down_revision: Union[str, None] = "0026_eligibility_filters"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("experience_levels", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "experience_levels")
