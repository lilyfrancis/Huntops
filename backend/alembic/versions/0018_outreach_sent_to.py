"""record the address an outreach was actually sent to

Revision ID: 0018_outreach_sent_to
Revises: 0017_regional_senders
Create Date: 2026-09-20

The recipient was only ever derivable from the linked Apollo contact, so a
pitch sent to an address the user supplied themselves recorded no recipient
at all — the page said "sent" and could not say to whom. That is the one
fact you want weeks later when a reply arrives, or does not.

Stored at send time rather than read back through the contact, because the
address used is the truth even when it differs from whatever Apollo found.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_outreach_sent_to"
down_revision: Union[str, None] = "0017_regional_senders"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("outreach", sa.Column("sent_to_email", sa.String(length=255), nullable=True))

    # Backfill what can be known: rows already sent, where the Apollo contact
    # is still linked and still has an address. Anything else stays null,
    # which is honest — we genuinely do not know where those went.
    op.execute(
        """
        UPDATE outreach
           SET sent_to_email = rc.email
          FROM recruiter_contacts rc
         WHERE outreach.recruiter_contact_id = rc.id
           AND outreach.status = 'sent'
           AND rc.email IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("outreach", "sent_to_email")
