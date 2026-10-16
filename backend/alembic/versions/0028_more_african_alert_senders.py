"""widen the allowlist where the Nigerian supply actually comes from

Revision ID: 0028_african_senders
Revises: 0027_seniority_filter
Create Date: 2026-10-16

An alert from a sender that is not on this list is skipped before the
extractor sees it — which is correct, since the mailbox is the operator's own
and carries ordinary mail too, but it means a missing domain looks exactly
like "the product is not pulling my alerts".

indeedemail.com is the one that matters most: Indeed sends a good deal of its
alert mail from there rather than from indeed.com, and indeed.com being
allowlisted does nothing for it. The rest are the African and Gulf boards
that carry real volume and were not listed.

Added idempotently, as in 0017: an operator may already have added some by
hand in Admin, and the unique index would fail a blind insert. Every one of
these can also be added in Admin → Integrations without a deploy — the sync
run names the domains it skipped, so an alert that is being missed says so.
"""

import uuid as _uuid
from datetime import datetime, timezone as _tz
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_african_senders"
down_revision: Union[str, None] = "0027_seniority_filter"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

ADDED = [
    # Indeed's own alert mail, which indeed.com does not cover.
    ("indeedemail.com", "Global"),
    ("glassdoor.co.uk", "UK"),
    # Nigeria and West Africa.
    ("jobzilla.ng", "Nigeria"),
    ("joblistghana.com", "Ghana"),
    # Ringier's African network — Jobberman's sister sites, same alert format.
    ("brightermonday.co.ke", "Kenya"),
    ("brightermonday.co.ug", "Uganda"),
    ("fuzu.com", "Africa"),
    ("careers24.com", "South Africa"),
]


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
    # Only where nobody has since claimed them: a domain with added_by_id set
    # was added by an operator in Admin and is not ours to remove.
    bind.execute(
        sa.text("DELETE FROM alert_senders WHERE domain = ANY(:domains) AND added_by_id IS NULL"),
        {"domains": [domain for domain, _ in ADDED]},
    )
