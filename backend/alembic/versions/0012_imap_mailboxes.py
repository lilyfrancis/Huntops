"""read alert mailboxes over IMAP instead of the Gmail API

Revision ID: 0012_imap_mailboxes
Revises: 0011_paystack
Create Date: 2026-09-06

Alert mailboxes are the operator's own accounts, so there was never anyone to
ask for consent — OAuth bought nothing but a Google review process, a per-seat
Workspace bill and a token that expires. IMAP needs a host and a password.

The table is dropped and recreated rather than migrated column by column.
Nothing carries over: OAuth tokens cannot become IMAP passwords, and the rows
hold no data worth preserving beyond configuration an operator retypes once.
Ingested jobs are untouched — they live in `jobs` and are what actually matters.

`email_sync_runs.mailbox_id` is dropped and re-added because its foreign key
points at the table being replaced. Historical run rows are kept; they simply
lose the mailbox link, which is the honest outcome since those mailboxes are
gone.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_imap_mailboxes"
down_revision: Union[str, None] = "0011_paystack"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _create_email_sync_run_link() -> None:
    op.add_column("email_sync_runs", sa.Column("mailbox_id", sa.Uuid(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_email_sync_runs_mailbox_id", "email_sync_runs", "alert_mailboxes",
        ["mailbox_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_email_sync_runs_mailbox_id", "email_sync_runs", ["mailbox_id"])


def _drop_email_sync_run_link() -> None:
    op.drop_index("ix_email_sync_runs_mailbox_id", table_name="email_sync_runs")
    op.drop_constraint("fk_email_sync_runs_mailbox_id", "email_sync_runs", type_="foreignkey")
    op.drop_column("email_sync_runs", "mailbox_id")


def upgrade() -> None:
    _drop_email_sync_run_link()

    op.drop_index("ix_alert_mailboxes_market", table_name="alert_mailboxes")
    op.drop_index("ix_alert_mailboxes_email_address", table_name="alert_mailboxes")
    op.drop_table("alert_mailboxes")

    op.create_table(
        "alert_mailboxes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=100), nullable=False),
        sa.Column("lanes", sa.JSON(), nullable=False),
        sa.Column("imap_host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False),
        sa.Column("imap_username", sa.String(length=255), nullable=False),
        sa.Column("imap_password_encrypted", sa.String(length=2000), nullable=False),
        sa.Column("imap_use_ssl", sa.Boolean(), nullable=False),
        sa.Column("imap_folder", sa.String(length=255), nullable=False),
        # BigInteger: IMAP UIDs are 32-bit unsigned, which overflows a signed
        # 32-bit column on a long-lived mailbox.
        sa.Column("last_seen_uid", sa.BigInteger(), nullable=True),
        sa.Column("uid_validity", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("added_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
    )
    op.create_index("ix_alert_mailboxes_email_address", "alert_mailboxes", ["email_address"], unique=True)
    op.create_index("ix_alert_mailboxes_market", "alert_mailboxes", ["market"])

    _create_email_sync_run_link()


def downgrade() -> None:
    _drop_email_sync_run_link()

    op.drop_index("ix_alert_mailboxes_market", table_name="alert_mailboxes")
    op.drop_index("ix_alert_mailboxes_email_address", table_name="alert_mailboxes")
    op.drop_table("alert_mailboxes")

    op.create_table(
        "alert_mailboxes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=100), nullable=False),
        sa.Column("lanes", sa.JSON(), nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=2000), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=2000), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("label_id", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("connected_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
    )
    op.create_index("ix_alert_mailboxes_email_address", "alert_mailboxes", ["email_address"], unique=True)
    op.create_index("ix_alert_mailboxes_market", "alert_mailboxes", ["market"])

    _create_email_sync_run_link()
