"""add auto-archive settings to audio settings

Revision ID: b4d2f8a71c90
Revises: 47c0c6553a62
Create Date: 2026-09-29 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d2f8a71c90"
down_revision: Union[str, Sequence[str], None] = "47c0c6553a62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auto-archiving of old records to the audio settings singleton."""
    op.add_column(
        "audiosettingsmodel",
        sa.Column(
            "auto_archive_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "audiosettingsmodel",
        sa.Column(
            "auto_archive_days",
            sa.Integer(),
            nullable=False,
            server_default="90",
        ),
    )


def downgrade() -> None:
    """Drop the auto-archiving settings columns."""
    op.drop_column("audiosettingsmodel", "auto_archive_days")
    op.drop_column("audiosettingsmodel", "auto_archive_enabled")
