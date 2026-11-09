"""Translation fields on records

Revision ID: e5b1c8d3a9f7
Revises: d7a2e9c4f1b6
Create Date: 2026-11-06 19:00:00.000000

- ``source_language``: dictation language; NULL = the instance language.
- ``translation_language``: instance language the text was translated into.
- ``translation`` / ``translation_segments``: translated text and the
  sentence pairs (JSON), both encrypted like ``content``.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5b1c8d3a9f7"
down_revision: Union[str, Sequence[str], None] = "d7a2e9c4f1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the translation columns."""
    with op.batch_alter_table("record") as batch_op:
        batch_op.add_column(sa.Column("source_language", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("translation_language", sa.String(), nullable=True)
        )
        batch_op.add_column(sa.Column("translation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("translation_segments", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop the translation columns."""
    with op.batch_alter_table("record") as batch_op:
        batch_op.drop_column("translation_segments")
        batch_op.drop_column("translation")
        batch_op.drop_column("translation_language")
        batch_op.drop_column("source_language")
