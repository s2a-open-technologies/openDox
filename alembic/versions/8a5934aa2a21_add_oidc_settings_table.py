"""add oidc settings table

Revision ID: 8a5934aa2a21
Revises: 9713c0c8535c
Create Date: 2026-07-07 22:10:56.652404

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8a5934aa2a21'
down_revision: Union[str, Sequence[str], None] = '9713c0c8535c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('oidcsettingsmodel',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('provider_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('client_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('client_secret', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('scopes', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_claim', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('admin_groups', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('username_claim', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('oidcsettingsmodel')
