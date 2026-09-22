"""add disclaimer acceptance to user

Revision ID: c562b50913d5
Revises: 8a5934aa2a21
Create Date: 2026-07-07 22:33:22.633117

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c562b50913d5"
down_revision: Union[str, Sequence[str], None] = "8a5934aa2a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user", sa.Column("disclaimer_accepted_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user", "disclaimer_accepted_at")
