"""Make datetime columns timezone-aware (timestamptz) on PostgreSQL

Revision ID: e3b7c1a95d42
Revises: c5e9a2d4f7b1
Create Date: 2026-10-08 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e3b7c1a95d42"
down_revision: Union[str, Sequence[str], None] = "c5e9a2d4f7b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs whose values were written as naive UTC.
_COLUMNS = (
    ("task", "created_at"),
    ("task", "updated_at"),
    ("user", "disclaimer_accepted_at"),
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Interpret existing naive timestamps as UTC and store them as timestamptz.

    SQLite has no timezone support and keeps its naive column; sqlmodel's
    UTCDateTime reads those back as UTC, so nothing to do there.
    """
    if not _is_postgres():
        return
    for table, column in _COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
            f"TYPE TIMESTAMP WITH TIME ZONE USING \"{column}\" AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    """Convert back to naive UTC timestamps."""
    if not _is_postgres():
        return
    for table, column in _COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
            f"TYPE TIMESTAMP WITHOUT TIME ZONE USING \"{column}\" AT TIME ZONE 'UTC'"
        )
