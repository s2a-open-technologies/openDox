"""Fix PK sequences after explicit-id seed data (user, categories, languages).

The initial migration (07e587f2292a) seeded the ``user``, ``categories`` and
``languages`` tables with hardcoded, explicit ``id`` values via raw
``INSERT ... VALUES (:id, ...) ON CONFLICT (id) DO NOTHING`` statements. On
PostgreSQL, inserting an explicit primary key value does NOT advance the
table's identity/serial sequence — only inserts that let the column default
to ``nextval()`` do. The sequences were therefore left at their initial
state while rows with ids 1..N already existed, so the first
application-level insert into one of these tables (e.g. creating a new
category via the Admin UI) reuses an already-taken id and raises
``UniqueViolation: duplicate key value violates unique constraint``.

Resyncs each affected sequence to MAX(id) + 1. No-op on SQLite, which has no
separate sequence object and isn't affected by this bug.

Revision ID: e23441c9a5e4
Revises: 629e6bed3208
Create Date: 2026-07-31 23:33:04.659566

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e23441c9a5e4'
down_revision: Union[str, Sequence[str], None] = '629e6bed3208'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables seeded with explicit, hardcoded ids in 07e587f2292a. "user" is a
# reserved word in PostgreSQL and must stay quoted in FROM clauses.
_AFFECTED_TABLES = ['"user"', "categories", "languages"]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table in _AFFECTED_TABLES:
        bare_name = table.strip('"')
        conn.execute(
            sa.text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{bare_name}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                    false
                )
                """
            )
        )


def downgrade() -> None:
    """No-op: resyncing a sequence forward isn't meaningfully reversible."""
    pass
