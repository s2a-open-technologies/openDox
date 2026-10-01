"""Add client settings (desktop-client policy)

Revision ID: c5e9a2d4f7b1
Revises: d7a1c3e95b26
Create Date: 2026-10-01 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision: str = "c5e9a2d4f7b1"
down_revision: Union[str, Sequence[str], None] = "d7a1c3e95b26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create clientsettingsmodel — global policy fetched by the desktop client."""
    op.create_table(
        "clientsettingsmodel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "clipboard_exclude_from_history",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "clipboard_clear_after_seconds",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column(
            "insert_allowlist",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "dictation_mic_mode",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="hold",
        ),
        sa.Column("live_view", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop clientsettingsmodel."""
    op.drop_table("clientsettingsmodel")
