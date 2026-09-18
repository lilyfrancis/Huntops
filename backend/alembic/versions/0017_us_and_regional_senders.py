"""add US job boards and widen the Nigeria and Gulf allowlists

Revision ID: 0017_regional_senders
Revises: 0016_whatsapp
Create Date: 2026-09-18

The seeded allowlist covered UK, Canada, Gulf and Nigeria with dedicated
boards, and the US with nothing — a US mailbox would have caught only the
five global aggregators, quietly missing most of its own market's supply.

Added idempotently: an operator may already have added some of these by
hand in Admin, and a unique index makes a blind insert fail the migration.
"""

import uuid as _uuid
from datetime import datetime, timezone as _tz
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_regional_senders"
down_revision: Union[str, None] = "0016_whatsapp"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

ADDED = [
    # The gap this migration exists for.
    ("monster.com", "USA"), ("dice.com", "USA"), ("simplyhired.com", "USA"),
    ("careerbuilder.com", "USA"), ("builtin.com", "USA"), ("wellfound.com", "USA"),
    ("usajobs.gov", "USA"),
    # Aggregators that carry real volume in several markets at once, so they
    # are labelled Global rather than pinned to one.
    ("talent.com", "Global"), ("jooble.org", "Global"), ("careerjet.com", "Global"),
    ("ngcareers.com", "Nigeria"), ("jobgurus.com.ng", "Nigeria"),
    ("monstergulf.com", "Gulf"), ("laimoon.com", "Gulf"), ("careerjet.ae", "Gulf"),
]

# Employer-side mail on domains now allowed. These are notifications to a
# company that someone applied to *their* posting — they match the allowlist,
# cost an AI call, and can be misread as a vacancy that does not exist.
ADDED_EXCLUDES = "noreply@monster.com,employer@monster.com,noreply@dice.com"


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(_tz.utc)

    existing = {row[0] for row in bind.execute(sa.text("SELECT domain FROM alert_senders"))}
    rows = [
        {"id": _uuid.uuid4(), "domain": domain, "note": note, "added_by_id": None, "created_at": now}
        for domain, note in ADDED
        if domain not in existing
    ]
    if rows:
        senders = sa.table(
            "alert_senders",
            sa.column("id", sa.Uuid(as_uuid=True)),
            sa.column("domain", sa.String),
            sa.column("note", sa.String),
            sa.column("added_by_id", sa.Uuid(as_uuid=True)),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(senders, rows)


def downgrade() -> None:
    bind = op.get_bind()
    # Only the ones this migration could have inserted, and only where nobody
    # has since claimed them: a domain with added_by_id set was added by an
    # operator in Admin and is not ours to remove.
    bind.execute(
        sa.text(
            "DELETE FROM alert_senders WHERE domain = ANY(:domains) AND added_by_id IS NULL"
        ),
        {"domains": [domain for domain, _ in ADDED]},
    )
