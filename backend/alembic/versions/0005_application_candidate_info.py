"""denormalize candidate name/email onto applications

Revision ID: 0005_candidate_info
Revises: 0004_phase4
Create Date: 2026-08-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_candidate_info"
down_revision: Union[str, None] = "0004_phase4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("candidate_name", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("candidate_email", sa.String(255), nullable=True))

    # Backfill from users for any pre-existing rows, then enforce NOT NULL.
    op.execute(
        """
        UPDATE applications
        SET candidate_name = users.full_name, candidate_email = users.email
        FROM users
        WHERE applications.candidate_id = users.id
        """
    )
    op.alter_column("applications", "candidate_name", nullable=False)
    op.alter_column("applications", "candidate_email", nullable=False)


def downgrade() -> None:
    op.drop_column("applications", "candidate_email")
    op.drop_column("applications", "candidate_name")
