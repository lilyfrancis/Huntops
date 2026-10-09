"""accounts that are exempt from credit charging

Revision ID: 0023_unlimited_credits
Revises: 0022_whatsapp_opt_in
Create Date: 2026-10-09

The operator needs to use the product without buying from themselves, and
support needs to reproduce a paid flow without spending a customer's balance.

A flag rather than a very large balance. A balance runs out eventually — at
the worst possible moment, with no warning — and while it lasts it reads in
the ledger exactly as though somebody paid for it, which quietly corrupts
every usage and revenue figure drawn from those rows.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_unlimited_credits"
down_revision: Union[str, None] = "0022_whatsapp_opt_in"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("unlimited_credits", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "unlimited_credits")
