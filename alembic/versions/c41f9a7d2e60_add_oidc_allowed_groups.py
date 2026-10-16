"""add oidc allowed_groups

Revision ID: c41f9a7d2e60
Revises: 955c92f50534
Create Date: 2026-10-16 20:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c41f9a7d2e60"
down_revision: Union[str, Sequence[str], None] = "955c92f50534"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "oidcsettingsmodel",
        sa.Column("allowed_groups", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("oidcsettingsmodel", "allowed_groups")
