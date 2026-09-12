"""move the job-alert sender allowlist into the database

Revision ID: 0015_alert_senders
Revises: 0014_mailbox_folders
Create Date: 2026-09-12

Opening a market means meeting job boards nobody anticipated. As an
environment variable, adding one was an SSH session, an edit and a container
restart — a developer in the loop for what is really an operations task, and
the difference between a market working and silently producing nothing.

Seeded with the current defaults so behaviour is unchanged on upgrade.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_alert_senders"
down_revision: Union[str, None] = "0014_mailbox_folders"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

SEED = [
    ("linkedin.com", "Global"), ("indeed.com", "Global"), ("glassdoor.com", "Global"),
    ("ziprecruiter.com", "Global"), ("theladders.com", "Global"),
    ("reed.co.uk", "UK"), ("totaljobs.com", "UK"), ("cv-library.co.uk", "UK"),
    ("jobsite.co.uk", "UK"), ("adzuna.co.uk", "UK"),
    ("workopolis.com", "Canada"), ("jobbank.gc.ca", "Canada"), ("eluta.ca", "Canada"),
    ("jobillico.com", "Canada"),
    ("bayt.com", "Gulf"), ("gulftalent.com", "Gulf"), ("naukrigulf.com", "Gulf"),
    ("dubizzle.com", "Gulf"),
    ("jobberman.com", "Nigeria"), ("myjobmag.com", "Nigeria"), ("hotnigerianjobs.com", "Nigeria"),
]


def upgrade() -> None:
    senders = op.create_table(
        "alert_senders",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("note", sa.String(length=100), nullable=True),
        sa.Column("added_by_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_senders_domain", "alert_senders", ["domain"], unique=True)

    # Seeded here rather than lazily on first read: an empty allowlist means
    # every mailbox silently ingests nothing, which is the worst possible
    # state to leave a deployment in between the migration and its first use.
    import uuid as _uuid
    from datetime import datetime, timezone as _tz

    now = datetime.now(_tz.utc)
    op.bulk_insert(senders, [
        {"id": _uuid.uuid4(), "domain": domain, "note": note, "added_by_id": None, "created_at": now}
        for domain, note in SEED
    ])


def downgrade() -> None:
    op.drop_index("ix_alert_senders_domain", table_name="alert_senders")
    op.drop_table("alert_senders")
