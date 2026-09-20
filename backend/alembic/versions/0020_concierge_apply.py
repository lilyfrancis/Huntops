"""apply on the user's behalf to sites we cannot submit to

Revision ID: 0020_concierge
Revises: 0019_app_drafts
Create Date: 2026-09-21

External listings live behind someone else's form, so the product could
only ever hand the user a link and let them do the rigorous part by hand —
which is the thing it exists to remove. A user can now ask HuntOps to file
it, and an admin does so under an address created for that person.

concierge_status is separate from status on purpose: one is how far *we*
have got, the other is what the *employer* has done, and they move
independently.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_concierge"
down_revision: Union[str, None] = "0019_app_drafts"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

CONCIERGE_STATUS = sa.Enum("queued", "submitted", "blocked", name="concierge_status")


def upgrade() -> None:
    CONCIERGE_STATUS.create(op.get_bind(), checkfirst=True)

    op.add_column("applications", sa.Column("is_concierge", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("applications", sa.Column("concierge_status", CONCIERGE_STATUS, nullable=True))
    op.add_column("applications", sa.Column("concierge_note", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "applications",
        sa.Column("handled_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    # The queue reads "everything still waiting", across all users, on every
    # page load. Without this that is a full scan of every application ever.
    op.create_index(
        "ix_applications_concierge_queue",
        "applications",
        ["concierge_status"],
        postgresql_where=sa.text("is_concierge"),
    )

    op.add_column("users", sa.Column("concierge_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "concierge_email")
    op.drop_index("ix_applications_concierge_queue", table_name="applications")
    op.drop_column("applications", "handled_by_id")
    op.drop_column("applications", "submitted_at")
    op.drop_column("applications", "concierge_note")
    op.drop_column("applications", "concierge_status")
    op.drop_column("applications", "is_concierge")
    CONCIERGE_STATUS.drop(op.get_bind(), checkfirst=True)
