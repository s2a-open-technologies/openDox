"""add ldap search_filter column

Revision ID: 9713c0c8535c
Revises: 4b1126aae6b2
Create Date: 2026-07-07 22:00:59.864710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9713c0c8535c'
down_revision: Union[str, Sequence[str], None] = '4b1126aae6b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ldapsettingsmodel', sa.Column('search_filter', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ldapsettingsmodel', 'search_filter')
