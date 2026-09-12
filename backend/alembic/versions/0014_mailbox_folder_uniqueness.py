"""let one mail account serve several markets through folders

Revision ID: 0014_mailbox_folders
Revises: 0013_pref_locations
Create Date: 2026-09-12

A market's jobs are tagged from the mailbox they arrived through, which is what
makes the market a fact rather than a guess about a free-text location string.
That is worth keeping — but it does not require a separate mail *account* per
market, only a separate folder.

Uniqueness moves from the address alone to (address, folder), so one account
can back four markets: route each market's alerts into its own folder at the
mail host, and each folder becomes a mailbox here with its own market, its own
UID cursor and its own failure state.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_mailbox_folders"
down_revision: Union[str, None] = "0013_pref_locations"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_index("ix_alert_mailboxes_email_address", table_name="alert_mailboxes")
    op.create_index("ix_alert_mailboxes_email_address", "alert_mailboxes", ["email_address"])
    op.create_unique_constraint(
        "uq_alert_mailbox_address_folder", "alert_mailboxes", ["email_address", "imap_folder"]
    )


def downgrade() -> None:
    # Reverting needs the address to be unique again, which it may no longer
    # be. Keep one row per address so the downgrade cannot fail on data created
    # since the upgrade.
    #
    # Ordered on (created_at, id), not created_at alone: two folders added in
    # the same second — or the same INSERT — share a timestamp, so neither is
    # "older", nothing is deleted, and the unique index then fails to build.
    # The id breaks the tie and makes the ordering total.
    op.execute(
        """
        DELETE FROM alert_mailboxes a
        USING alert_mailboxes b
        WHERE a.email_address = b.email_address
          AND (a.created_at, a.id) < (b.created_at, b.id)
        """
    )
    op.drop_constraint("uq_alert_mailbox_address_folder", "alert_mailboxes", type_="unique")
    op.drop_index("ix_alert_mailboxes_email_address", table_name="alert_mailboxes")
    op.create_index("ix_alert_mailboxes_email_address", "alert_mailboxes", ["email_address"], unique=True)
