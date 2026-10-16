"""choose which supply pipeline to draw from

Revision ID: 0029_source_preference
Revises: 0028_african_senders
Create Date: 2026-10-16

Measured on the live pool: 9,204 active jobs, 7 of which came from the alert
mailboxes. The other 9,197 are the six global board APIs, which are
remote-first and hire mostly out of the US and Europe.

At that ratio a Nigerian user's own market is statistically invisible no
matter how well the other filters work — eligibility can exclude every
US-only listing and the Nigerian supply is still outnumbered more than a
thousand to one, sorted below jobs with higher fit scores, and never reached.
Filtering cannot surface supply; only choosing the pipeline can.

Empty means both, like every other list on this table, so no existing feed
changes.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_source_preference"
down_revision: Union[str, None] = "0028_african_senders"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("sources", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "sources")
