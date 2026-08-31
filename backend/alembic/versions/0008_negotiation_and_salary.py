"""negotiation coach + normalized salary columns

Revision ID: 0008_negotiation
Revises: 0007_interviews
Create Date: 2026-08-31
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import Uuid

revision: str = "0008_negotiation"
down_revision: Union[str, None] = "0007_interviews"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("salary_annual_min", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("salary_annual_max", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("salary_currency", sa.String(3), nullable=True))
    op.create_index("ix_jobs_salary_currency", "jobs", ["salary_currency"])

    op.create_table(
        "negotiation_reviews",
        sa.Column("id", Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_title", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("base_salary", sa.Float(), nullable=False),
        sa.Column("equity", sa.Text(), nullable=True),
        sa.Column("other_terms", sa.Text(), nullable=True),
        sa.Column("has_competing_offer", sa.Boolean(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("levers", sa.JSON(), nullable=False),
        sa.Column("counter_script", sa.Text(), nullable=False),
        sa.Column("if_they_say_no", sa.Text(), nullable=False),
        sa.Column("watch_outs", sa.JSON(), nullable=False),
        sa.Column("benchmark", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_negotiation_reviews_user_id", "negotiation_reviews", ["user_id"])
    op.create_index("ix_negotiation_reviews_created_at", "negotiation_reviews", ["created_at"])

    # Existing rows keep null salary columns. They are backfilled by
    # `python -m app.scripts.backfill_salaries`, which re-parses salary_range —
    # doing it here would mean reimplementing the parser in SQL.


def downgrade() -> None:
    op.drop_index("ix_negotiation_reviews_created_at", table_name="negotiation_reviews")
    op.drop_index("ix_negotiation_reviews_user_id", table_name="negotiation_reviews")
    op.drop_table("negotiation_reviews")
    op.drop_index("ix_jobs_salary_currency", table_name="jobs")
    op.drop_column("jobs", "salary_currency")
    op.drop_column("jobs", "salary_annual_max")
    op.drop_column("jobs", "salary_annual_min")
