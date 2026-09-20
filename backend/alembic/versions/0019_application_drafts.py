"""tailored cover letters and résumé bullets, per job

Revision ID: 0019_app_drafts
Revises: 0018_outreach_sent_to
Create Date: 2026-09-21

Auto-apply created applications with cover_letter NULL, so the product
decided a role was worth applying to and then sent the weakest possible
application. Drafts live in their own table rather than on `applications`
because they exist before one does — the point is reading and editing what
will be sent — and because a draft outlives a withdrawn application.

`applications.tailored_bullets` records what actually went with a
submission, which is not the same thing as the current draft: the draft can
be edited afterwards, and what was sent must not change retroactively.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_app_drafts"
down_revision: Union[str, None] = "0018_outreach_sent_to"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "application_drafts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cover_letter", sa.Text(), nullable=False, server_default=""),
        sa.Column("bullets", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_application_drafts_user_id", "application_drafts", ["user_id"])
    op.create_index("ix_application_drafts_job_id", "application_drafts", ["job_id"])
    op.create_unique_constraint(
        "uq_application_draft_user_job", "application_drafts", ["user_id", "job_id"]
    )

    op.add_column(
        "applications",
        sa.Column("tailored_bullets", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("applications", "tailored_bullets")
    op.drop_constraint("uq_application_draft_user_job", "application_drafts", type_="unique")
    op.drop_index("ix_application_drafts_job_id", table_name="application_drafts")
    op.drop_index("ix_application_drafts_user_id", table_name="application_drafts")
    op.drop_table("application_drafts")
