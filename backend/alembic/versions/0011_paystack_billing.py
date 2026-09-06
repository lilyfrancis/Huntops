"""switch billing columns from Stripe to Paystack

Revision ID: 0011_paystack
Revises: 0010_central_supply
Create Date: 2026-09-06

Renames rather than drop-and-add, so any subscription identifiers already on
the table survive the migration instead of being silently discarded.

`paystack_email_token` is new and has no Stripe equivalent: Paystack requires
it alongside the subscription code to cancel, and hands it out exactly once on
the subscription.create webhook. Existing rows get NULL — correct, since no
row can have a Paystack subscription yet.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_paystack"
down_revision: Union[str, None] = "0010_central_supply"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("users", "stripe_customer_id", new_column_name="paystack_customer_code")
    op.alter_column("users", "stripe_subscription_id", new_column_name="paystack_subscription_code")
    op.add_column("users", sa.Column("paystack_email_token", sa.String(length=255), nullable=True))

    # The index follows the column it was built on; renaming the column does
    # not rename the index, and an index called ix_users_stripe_customer_id on
    # a Paystack column is the kind of thing that misleads someone at 3am.
    op.execute("ALTER INDEX ix_users_stripe_customer_id RENAME TO ix_users_paystack_customer_code")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_users_paystack_customer_code RENAME TO ix_users_stripe_customer_id")
    op.drop_column("users", "paystack_email_token")
    op.alter_column("users", "paystack_subscription_code", new_column_name="stripe_subscription_id")
    op.alter_column("users", "paystack_customer_code", new_column_name="stripe_customer_id")
