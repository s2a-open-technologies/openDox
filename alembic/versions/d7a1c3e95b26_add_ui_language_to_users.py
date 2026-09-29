"""Add ui_language to users

Revision ID: d7a1c3e95b26
Revises: b4d2f8a71c90
Create Date: 2026-09-29 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d7a1c3e95b26"
down_revision: Union[str, Sequence[str], None] = "b4d2f8a71c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user.ui_language — each user's preferred UI language."""
    op.add_column("user", sa.Column("ui_language", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop user.ui_language."""
    op.drop_column("user", "ui_language")
