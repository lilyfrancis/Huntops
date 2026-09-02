"""phase 4 — autopilot outreach: recruiter contacts, outreach, user positioning

Revision ID: 0004_phase4
Revises: 0003_phase3
Create Date: 2026-08-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase4"
down_revision: Union[str, None] = "0003_phase3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

outreach_status = postgresql.ENUM("sent", "draft_no_contact", "failed", name="outreach_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    outreach_status.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("positioning_statement", sa.String(500), nullable=True))

    op.create_table(
        "recruiter_contacts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("apollo_person_id", sa.String(100), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("email_status", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recruiter_contacts_job_id", "recruiter_contacts", ["job_id"], unique=True)

    op.create_table(
        "outreach",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recruiter_contact_id", sa.Uuid(as_uuid=True), sa.ForeignKey("recruiter_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email_subject", sa.Text(), nullable=True),
        sa.Column("email_body", sa.Text(), nullable=True),
        sa.Column("linkedin_msg", sa.Text(), nullable=True),
        sa.Column("cv_bullets", sa.JSON(), nullable=False),
        sa.Column("status", outreach_status, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "job_id", name="uq_outreach_user_job"),
    )
    op.create_index("ix_outreach_user_id", "outreach", ["user_id"])
    op.create_index("ix_outreach_job_id", "outreach", ["job_id"])


def downgrade() -> None:
    op.drop_table("outreach")
    op.drop_table("recruiter_contacts")
    op.drop_column("users", "positioning_statement")

    bind = op.get_bind()
    outreach_status.drop(bind, checkfirst=True)
