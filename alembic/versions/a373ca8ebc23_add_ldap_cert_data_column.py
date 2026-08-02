"""add ldap cert_data column

Revision ID: a373ca8ebc23
Revises: 90f1609b79ba
Create Date: 2026-08-02 19:34:33.677609

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a373ca8ebc23'
down_revision: Union[str, Sequence[str], None] = '90f1609b79ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ldapsettingsmodel',
        sa.Column('cert_data', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ldapsettingsmodel', 'cert_data')
