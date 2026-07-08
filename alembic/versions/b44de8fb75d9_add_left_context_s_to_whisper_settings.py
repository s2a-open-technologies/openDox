"""add left_context_s to whisper settings

Revision ID: b44de8fb75d9
Revises: c562b50913d5
Create Date: 2026-07-07 23:34:27.343754

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b44de8fb75d9'
down_revision: Union[str, Sequence[str], None] = 'c562b50913d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'whispersettingsmodel',
        sa.Column('left_context_s', sa.Float(), nullable=False, server_default='0.0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whispersettingsmodel', 'left_context_s')
