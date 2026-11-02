"""Optional LLM step (global and per category)

Revision ID: a4d7e2c9b513
Revises: c6a9d3e7f2b4
Create Date: 2026-11-02 12:00:00.000000

- ``llmsettingsmodel.llm_enabled``: master switch, off = transcription only.
- ``categories.llm_enabled``: whether recordings of the category get an LLM
  summary. Both default to on, so existing installations behave as before.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a4d7e2c9b513"
down_revision: Union[str, Sequence[str], None] = "c6a9d3e7f2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the LLM switches."""
    op.add_column(
        "llmsettingsmodel",
        sa.Column(
            "llm_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "llm_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    """Drop the LLM switches."""
    op.drop_column("categories", "llm_enabled")
    op.drop_column("llmsettingsmodel", "llm_enabled")
