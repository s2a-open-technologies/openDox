"""add user role field and oidc moderator_groups

Revision ID: d15162a50b79
Revises: c562b50913d5
Create Date: 2026-07-07 23:20:21.114573

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d15162a50b79"
down_revision: Union[str, Sequence[str], None] = "c562b50913d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Adds the ``role`` column, migrates existing ``is_superuser`` values to
    ``role='admin'``, then drops ``is_superuser``. Also adds the OIDC
    ``moderator_groups`` column.
    """
    # Add role column as nullable first so we can populate it from is_superuser.
    op.add_column(
        "user", sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )
    op.create_index(op.f("ix_user_role"), "user", ["role"], unique=False)

    # Migrate: admins (is_superuser=True) → role='admin', others → role='user'.
    op.execute("UPDATE \"user\" SET role = 'admin' WHERE is_superuser = true")
    op.execute("UPDATE \"user\" SET role = 'user' WHERE role IS NULL")

    # Now make it NOT NULL and drop the old column.
    op.alter_column(
        "user", "role", existing_type=sqlmodel.sql.sqltypes.AutoString(), nullable=False
    )
    op.drop_column("user", "is_superuser")

    # OIDC moderator_groups.
    op.add_column(
        "oidcsettingsmodel",
        sa.Column(
            "moderator_groups",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Restore is_superuser from role before dropping the column.
    op.add_column(
        "user",
        sa.Column(
            "is_superuser",
            sa.BOOLEAN(),
            autoincrement=False,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute("UPDATE \"user\" SET is_superuser = true WHERE role = 'admin'")

    op.drop_index(op.f("ix_user_role"), table_name="user")
    op.drop_column("user", "role")

    op.drop_column("oidcsettingsmodel", "moderator_groups")
