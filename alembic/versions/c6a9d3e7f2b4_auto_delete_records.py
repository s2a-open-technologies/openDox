"""Automatic deletion of old records

Revision ID: c6a9d3e7f2b4
Revises: b8e4c2f6a1d9
Create Date: 2026-10-28 18:00:00.000000

- ``audiosettingsmodel.auto_delete_enabled``/``auto_delete_days``: global
  maximum retention (off by default, 365 days).
- ``user.auto_delete_days``: a user's own, shorter retention (NULL = none).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c6a9d3e7f2b4"
down_revision: Union[str, Sequence[str], None] = "b8e4c2f6a1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the retention columns."""
    op.add_column(
        "audiosettingsmodel",
        sa.Column(
            "auto_delete_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "audiosettingsmodel",
        sa.Column(
            "auto_delete_days", sa.Integer(), nullable=False, server_default="365"
        ),
    )
    op.add_column("user", sa.Column("auto_delete_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Drop the retention columns."""
    op.drop_column("user", "auto_delete_days")
    op.drop_column("audiosettingsmodel", "auto_delete_days")
    op.drop_column("audiosettingsmodel", "auto_delete_enabled")
