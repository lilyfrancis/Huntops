"""initial schema — users, jobs, applications, credit_ledger

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = postgresql.ENUM("job_seeker", "employer", "admin", name="user_role", create_type=False)
subscription_tier = postgresql.ENUM("free", "pro", "elite", name="subscription_tier", create_type=False)
job_status = postgresql.ENUM("pending", "active", "rejected", "closed", name="job_status", create_type=False)
job_type = postgresql.ENUM("full_time", "part_time", "contract", "internship", name="job_type", create_type=False)
experience_level = postgresql.ENUM("entry", "mid", "senior", "lead", "executive", name="experience_level", create_type=False)
application_status = postgresql.ENUM(
    "pending", "reviewed", "interviewing", "offered", "rejected", "withdrawn",
    name="application_status", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (user_role, subscription_tier, job_status, job_type, experience_level, application_status):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("subscription_tier", subscription_tier, nullable=False, server_default="free"),
        sa.Column("ai_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("employer_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employer_name", sa.String(255), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("salary_range", sa.String(100), nullable=True),
        sa.Column("job_type", job_type, nullable=False),
        sa.Column("experience_level", experience_level, nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("application_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(50), nullable=False, server_default="internal"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_employer_id", "jobs", ["employer_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("status", application_status, nullable=False, server_default="pending"),
        sa.Column("ai_match_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),
    )
    op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])


def downgrade() -> None:
    op.drop_table("credit_ledger")
    op.drop_table("applications")
    op.drop_table("jobs")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_type in (application_status, experience_level, job_type, job_status, subscription_tier, user_role):
        enum_type.drop(bind, checkfirst=True)
