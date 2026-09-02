"""drop unique constraints duplicated by unique indexes

Revision ID: 0009_dedupe_uniques
Revises: 0008_negotiation
Create Date: 2026-08-31

The models declare `unique=True, index=True` on these columns, which SQLAlchemy
renders as a UNIQUE INDEX (ix_<table>_<col>). Migrations 0002-0004 also added a
standalone UNIQUE CONSTRAINT on the same column, so Postgres ended up enforcing
the same rule twice.

Uniqueness was never wrong — both objects enforce it identically — but the
duplicate costs an extra index write on every insert, and it made
`alembic revision --autogenerate` permanently report a phantom difference
between the models and the migrated schema. A diff that is always dirty is a
diff nobody reads, so this removes the redundant constraints and leaves the
unique indexes the models actually describe.

Found by running the full chain against a real PostgreSQL and diffing the
result against the models.
"""

from typing import Union

from alembic import op

revision: str = "0009_dedupe_uniques"
down_revision: Union[str, None] = "0008_negotiation"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# (table, constraint name) — Postgres' default naming for a column-level UNIQUE.
_REDUNDANT = [
    ("resumes", "resumes_user_id_key"),
    ("gmail_connections", "gmail_connections_user_id_key"),
    ("recruiter_contacts", "recruiter_contacts_job_id_key"),
]


def upgrade() -> None:
    for table, constraint in _REDUNDANT:
        # IF EXISTS: a database built by create_all rather than by this chain
        # never had these constraints in the first place.
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")


def downgrade() -> None:
    for table, constraint in _REDUNDANT:
        column = "job_id" if table == "recruiter_contacts" else "user_id"
        op.create_unique_constraint(constraint, table, [column])
