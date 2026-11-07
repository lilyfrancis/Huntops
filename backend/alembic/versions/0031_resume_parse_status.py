"""keep a CV even when the model cannot read it

Revision ID: 0031_parse_status
Revises: 0030_backfill_geo
Create Date: 2026-11-07

Parsing is the one step of uploading a CV that costs an API call, and it was
the only step that could refuse the upload. An account out of credit — or a
provider outage — turned a new user's very first action into a 502 and no
CV, and without a CV there are no matches, so the product was dead on
arrival for everyone who signed up during it.

Browsing, unlocking and applying never needed the parse. Those are the parts
that earn the money that buys the credit, so they must not be behind it.

Existing rows are "parsed": they got through when parsing worked, and
marking them pending would queue a re-read of every CV on the system the
next time the catch-up runs.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_parse_status"
down_revision: Union[str, None] = "0030_backfill_geo"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column("parse_status", sa.String(length=10), nullable=False, server_default="parsed"),
    )


def downgrade() -> None:
    op.drop_column("resumes", "parse_status")
