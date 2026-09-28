"""Add personal_glossary to users

Revision ID: 47c0c6553a62
Revises: 8ed39a1da48e
Create Date: 2026-09-28 17:23:06.310951

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "47c0c6553a62"
down_revision: Union[str, Sequence[str], None] = "8ed39a1da48e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user.personal_glossary — each user's private correction glossary."""
    op.add_column("user", sa.Column("personal_glossary", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop user.personal_glossary."""
    op.drop_column("user", "personal_glossary")
