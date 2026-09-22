"""remove sanitizer department column

Revision ID: 4b1126aae6b2
Revises: a599665d9034
Create Date: 2026-07-07 00:11:51.907496

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b1126aae6b2"
down_revision: Union[str, Sequence[str], None] = "a599665d9034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("llmsettingsmodel", "sanitizer_department")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "llmsettingsmodel",
        sa.Column(
            "sanitizer_department", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
    )
