"""add categories user_id

Revision ID: 2efe299f2cf0
Revises: 3ad5334b1d34
Create Date: 2026-08-05 22:08:12.704357

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2efe299f2cf0'
down_revision: Union[str, Sequence[str], None] = '3ad5334b1d34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('categories', sa.Column('user_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('categories', 'user_id')
