"""record when a user first messaged the business number

Revision ID: 0022_whatsapp_opt_in
Revises: 0021_job_unlocks
Create Date: 2026-09-25

Meta drops a marketing template to anyone who has never engaged with the
business. The send is accepted with a 200 and `message_status: accepted`, and
the message then never arrives — there is no error on the sending side at all.
The daily digest is classified as marketing, and Meta refused Utility for it on
review, so this is not a category we can argue our way out of.

That makes "has this person messaged us?" a fact the product has to know: it
decides whether WhatsApp can reach them, and it is the difference between a
digest that arrives and one that vanishes. Recorded from the inbound webhook
rather than from a click on our own button, because a click proves only that
the link was opened.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_whatsapp_opt_in"
down_revision: Union[str, None] = "0021_job_unlocks"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("whatsapp_opted_in_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "whatsapp_opted_in_at")
