"""per-user city/region filter within a market

Revision ID: 0013_pref_locations
Revises: 0012_imap_mailboxes
Create Date: 2026-09-12

Alert mailboxes are subscribed country-wide, because supply has to be broad —
you cannot subscribe to a city nobody has asked for yet. Narrowing therefore
belongs to the user, and until now there was nowhere to put it: someone who
only wants Toronto had to take the whole of Canada.

Server default '[]' so rows written by the running release, which does not
know this column, still satisfy NOT NULL during the deploy.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_pref_locations"
down_revision: Union[str, None] = "0012_imap_mailboxes"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("locations", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "locations")
