"""several CVs per user, chosen by the job's family

Revision ID: 0024_multiple_resumes
Revises: 0023_unlimited_credits
Create Date: 2026-10-09

One CV cannot do two jobs. Somebody applying for engineering roles and sales
roles has two different stories to tell, and the product was tailoring both
from the same document — so the strongest thing it does, deciding a role is
worth applying to, was followed by a CV written for a different career.

`resumes.user_id` was unique. That constraint is dropped and three columns
added: a label the person writes, the job families the CV is for, and which
one is the fallback.

The existing row per user becomes that user's primary, labelled "My CV", with
no lanes claimed — so every current account behaves exactly as it did before
until somebody uploads a second one.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_multiple_resumes"
down_revision: Union[str, None] = "0023_unlimited_credits"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("label", sa.String(length=80), nullable=False, server_default="My CV"))
    op.add_column("resumes", sa.Column("lanes", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("resumes", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Every CV that exists today is its owner's only one, so it is the
    # fallback. Without this nobody has a primary and the selector falls
    # through to "most recent", which is the same answer today and the wrong
    # one the moment a second CV is uploaded.
    op.execute("UPDATE resumes SET is_primary = true")

    # The uniqueness lives in an index, not a table constraint: 0002 created
    # ix_resumes_user_id as unique, and 0009 already dropped the redundant
    # resumes_user_id_key. Dropping and recreating the index is the same
    # operation on PostgreSQL and SQLite, so there is nothing to branch on.
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])


def downgrade() -> None:
    # Only the newest CV per user can survive a return to one-per-user. The
    # others are deleted rather than silently reassigned, because a CV
    # attached to the wrong person is worse than a missing one.
    op.execute(
        "DELETE FROM resumes WHERE id NOT IN "
        "(SELECT id FROM (SELECT DISTINCT ON (user_id) id FROM resumes "
        " ORDER BY user_id, updated_at DESC) AS keep)"
        if op.get_bind().dialect.name == "postgresql"
        else "DELETE FROM resumes WHERE id NOT IN "
             "(SELECT id FROM resumes r2 WHERE r2.updated_at = "
             " (SELECT MAX(r3.updated_at) FROM resumes r3 WHERE r3.user_id = r2.user_id))"
    )
    op.drop_column("resumes", "is_primary")
    op.drop_column("resumes", "lanes")
    op.drop_column("resumes", "label")

    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"], unique=True)
