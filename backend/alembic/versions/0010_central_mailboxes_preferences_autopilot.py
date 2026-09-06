"""central alert mailboxes, user preferences, autopilot

Revision ID: 0010_central_supply
Revises: 0009_dedupe_uniques
Create Date: 2026-09-06

Re-points the product's supply side. Job alerts used to arrive through each
user's own connected Gmail; they now arrive through a small set of
admin-owned mailboxes, each tagged with the market it covers, and every user
draws from that shared pool filtered by the preferences they chose at signup.

Three things change in the schema:

1. `alert_mailboxes` — the operator's inboxes. New table.
2. `email_sync_runs` becomes mailbox-scoped. `user_id` is made nullable rather
   than dropped, so the rows written when users mined their own inboxes stay
   readable on the ops page instead of being deleted with the feature.
3. `user_preferences` and `autopilot_actions` — what each user asked for, and
   the receipt for anything acted on in their name.

`jobs.market` records which market's mailbox a listing came through. Existing
rows are left NULL on purpose: they came from the global API sources, which
are remote-first and belong to every market, and the feed filter treats NULL
as exactly that.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_central_supply"
down_revision: Union[str, None] = "0009_dedupe_uniques"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
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

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_markets", sa.JSON(), nullable=False),
        sa.Column("lanes", sa.JSON(), nullable=False),
        sa.Column("job_types", sa.JSON(), nullable=False),
        sa.Column("remote_only", sa.Boolean(), nullable=False),
        sa.Column("autopilot_apply_enabled", sa.Boolean(), nullable=False),
        sa.Column("autopilot_apply_threshold", sa.Integer(), nullable=False),
        sa.Column("autopilot_outreach_enabled", sa.Boolean(), nullable=False),
        sa.Column("autopilot_outreach_threshold", sa.Integer(), nullable=False),
        sa.Column("autopilot_daily_cap", sa.Integer(), nullable=False),
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=True)

    op.create_table(
        "autopilot_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_autopilot_actions_user_id", "autopilot_actions", ["user_id"])
    op.create_index("ix_autopilot_actions_job_id", "autopilot_actions", ["job_id"])
    op.create_index("ix_autopilot_actions_created_at", "autopilot_actions", ["created_at"])

    op.add_column("jobs", sa.Column("market", sa.String(length=100), nullable=True))
    op.create_index("ix_jobs_market", "jobs", ["market"])

    op.add_column("email_sync_runs", sa.Column("mailbox_id", sa.Uuid(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_email_sync_runs_mailbox_id", "email_sync_runs", "alert_mailboxes",
        ["mailbox_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_email_sync_runs_mailbox_id", "email_sync_runs", ["mailbox_id"])
    op.alter_column("email_sync_runs", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    # Rows written since the upgrade have no user_id — there is no user to
    # attribute an operator's mailbox to. Delete them rather than fail the
    # NOT NULL, since a mailbox run is meaningless once mailboxes are gone.
    op.execute("DELETE FROM email_sync_runs WHERE user_id IS NULL")
    op.alter_column("email_sync_runs", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_index("ix_email_sync_runs_mailbox_id", table_name="email_sync_runs")
    op.drop_constraint("fk_email_sync_runs_mailbox_id", "email_sync_runs", type_="foreignkey")
    op.drop_column("email_sync_runs", "mailbox_id")

    op.drop_index("ix_jobs_market", table_name="jobs")
    op.drop_column("jobs", "market")

    op.drop_index("ix_autopilot_actions_created_at", table_name="autopilot_actions")
    op.drop_index("ix_autopilot_actions_job_id", table_name="autopilot_actions")
    op.drop_index("ix_autopilot_actions_user_id", table_name="autopilot_actions")
    op.drop_table("autopilot_actions")

    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")

    op.drop_index("ix_alert_mailboxes_market", table_name="alert_mailboxes")
    op.drop_index("ix_alert_mailboxes_email_address", table_name="alert_mailboxes")
    op.drop_table("alert_mailboxes")
