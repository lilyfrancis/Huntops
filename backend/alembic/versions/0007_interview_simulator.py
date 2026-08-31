"""mock interview simulator

Revision ID: 0007_interviews
Revises: 0006_ghost_detection
Create Date: 2026-08-31
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import Uuid

revision: str = "0007_interviews"
down_revision: Union[str, None] = "0006_ghost_detection"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role_title", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("in_progress", "completed", name="interview_status"),
            nullable=False,
        ),
        sa.Column("average_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("next_steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"])
    op.create_index("ix_interview_sessions_job_id", "interview_sessions", ["job_id"])
    op.create_index("ix_interview_sessions_created_at", "interview_sessions", ["created_at"])

    op.create_table(
        "interview_turns",
        sa.Column("id", Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            Uuid(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("improvements", sa.JSON(), nullable=False),
        sa.Column("model_answer", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interview_turns_session_id", "interview_turns", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_turns_session_id", table_name="interview_turns")
    op.drop_table("interview_turns")
    op.drop_index("ix_interview_sessions_created_at", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_job_id", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_user_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
    sa.Enum(name="interview_status").drop(op.get_bind(), checkfirst=True)
