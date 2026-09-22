"""add ldap group mapping fields

Revision ID: dfba80abfe0c
Revises: a373ca8ebc23
Create Date: 2026-08-02 20:15:06.484123

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dfba80abfe0c"
down_revision: Union[str, Sequence[str], None] = "a373ca8ebc23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ldapsettingsmodel",
        sa.Column("allowed_groups", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "ldapsettingsmodel",
        sa.Column("admin_groups", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "ldapsettingsmodel",
        sa.Column(
            "moderator_groups", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ldapsettingsmodel", "moderator_groups")
    op.drop_column("ldapsettingsmodel", "admin_groups")
    op.drop_column("ldapsettingsmodel", "allowed_groups")
