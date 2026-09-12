"""deliver the digest over WhatsApp as well as email

Revision ID: 0016_whatsapp
Revises: 0015_alert_senders
Create Date: 2026-09-12

Email open rates for a daily digest are poor in the markets this serves. In
Nigeria and the Gulf, WhatsApp is where people read — and a digest nobody
opens is the whole feature wasted.

`digest_channel` defaults to email, which is the only channel every user has
by definition; WhatsApp needs a number they may never give us. Server default
so rows written by the running release, which does not know this column, still
satisfy NOT NULL during the deploy.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_whatsapp"
down_revision: Union[str, None] = "0015_alert_senders"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("whatsapp_number", sa.String(length=20), nullable=True))
    op.add_column(
        "user_preferences",
        sa.Column("digest_channel", sa.String(length=20), nullable=False, server_default="email"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "digest_channel")
    op.drop_column("users", "whatsapp_number")
