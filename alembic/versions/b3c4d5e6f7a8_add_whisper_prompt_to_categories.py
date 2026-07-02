"""Add whisper_prompt to categories

Revision ID: b3c4d5e6f7a8
Revises: 0c0d79e460c9
Create Date: 2026-07-02 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "0c0d79e460c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("whisper_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("categories", "whisper_prompt")
