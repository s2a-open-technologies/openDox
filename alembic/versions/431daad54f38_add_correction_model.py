"""add correction_model to llm settings

Revision ID: 431daad54f38
Revises: c3e47f3a24f2
Create Date: 2026-06-12

Dedicated model for near-live chunk correction, independent of the main
summarisation LLM. NULL = fall back to llm_model.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "431daad54f38"
down_revision: Union[str, Sequence[str], None] = "c3e47f3a24f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llmsettingsmodel",
        sa.Column("correction_model", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llmsettingsmodel", "correction_model")
