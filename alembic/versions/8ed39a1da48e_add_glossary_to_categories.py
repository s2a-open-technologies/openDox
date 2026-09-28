"""Add glossary to categories

Revision ID: 8ed39a1da48e
Revises: d4a1f9c3e2b7
Create Date: 2026-09-28 17:22:54.684612

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8ed39a1da48e"
down_revision: Union[str, Sequence[str], None] = "d4a1f9c3e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add categories.glossary and backfill it from whisper_prompt.

    whisper_prompt used to double as the term-correction glossary source;
    it is now Whisper-only (avoids the 224-token initial_prompt limit
    silently truncating glossary terms). Backfilling preserves today's
    correction behavior for existing categories.
    """
    op.add_column("categories", sa.Column("glossary", sa.Text(), nullable=True))
    op.execute(
        "UPDATE categories SET glossary = whisper_prompt "
        "WHERE whisper_prompt IS NOT NULL"
    )


def downgrade() -> None:
    """Drop categories.glossary."""
    op.drop_column("categories", "glossary")
