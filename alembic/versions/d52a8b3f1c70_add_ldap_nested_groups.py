"""add ldap nested_groups

Revision ID: d52a8b3f1c70
Revises: c41f9a7d2e60
Create Date: 2026-10-16 21:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d52a8b3f1c70"
down_revision: Union[str, Sequence[str], None] = "c41f9a7d2e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ldapsettingsmodel",
        sa.Column(
            "nested_groups", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ldapsettingsmodel", "nested_groups")
