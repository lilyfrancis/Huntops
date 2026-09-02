"""phase 2 — aggregation, resumes, job matching

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-08-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase2"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

job_lane = postgresql.ENUM(
    "engineering", "product", "design", "gtm", "revops", "marketing", "sales",
    "automation", "operations", "leadership", "customer_success", "finance", "hr", "other",
    name="job_lane",
    # The explicit .create(bind, checkfirst=True) below owns creation; without
    # this, add_column/create_table emits a second CREATE TYPE and the
    # migration dies with "type already exists" on a fresh Postgres.
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    job_lane.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("home_market", sa.String(100), nullable=True))

    op.add_column("jobs", sa.Column("source_url", sa.String(1000), nullable=True))
    op.add_column("jobs", sa.Column("lane", job_lane, nullable=True))
    op.add_column("jobs", sa.Column("is_remote", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("jobs", sa.Column("restricted_to", sa.String(100), nullable=True))
    op.create_unique_constraint("uq_jobs_source_url", "jobs", ["source_url"])
    op.create_index("ix_jobs_lane", "jobs", ["lane"])

    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parsed_skills", sa.JSON(), nullable=False),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("education", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("achievements", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"], unique=True)

    op.create_table(
        "job_matches",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fit_score", sa.Float(), nullable=False),
        sa.Column("skills_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("experience_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("geo_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("geo_boost_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_match_user_job"),
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("job_matches")
    op.drop_table("resumes")

    op.drop_constraint("uq_jobs_source_url", "jobs", type_="unique")
    op.drop_index("ix_jobs_lane", table_name="jobs")
    op.drop_column("jobs", "restricted_to")
    op.drop_column("jobs", "is_remote")
    op.drop_column("jobs", "lane")
    op.drop_column("jobs", "source_url")

    op.drop_column("users", "home_market")

    bind = op.get_bind()
    job_lane.drop(bind, checkfirst=True)
