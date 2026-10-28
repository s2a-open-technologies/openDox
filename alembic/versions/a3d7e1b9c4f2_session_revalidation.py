"""Session renewal: idle timeout setting, login source per user

Revision ID: a3d7e1b9c4f2
Revises: f8c2d4a6b1e3
Create Date: 2026-10-23 12:00:00.000000

- New table ``sessionsettingsmodel`` (web UI idle timeout, one row).
- ``user.auth_source`` (local/ldap/oidc): users with a password hash are
  local, everyone else stays NULL until their next login sets it.
- ``user.idp_refresh_token`` (encrypted): the OIDC provider's refresh token,
  used to re-check the account when a session is renewed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision: str = "a3d7e1b9c4f2"
down_revision: Union[str, Sequence[str], None] = "f8c2d4a6b1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sessionsettingsmodel and add the login-source columns to user."""
    op.create_table(
        "sessionsettingsmodel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "idle_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "user",
        sa.Column("auth_source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column("user", sa.Column("idp_refresh_token", sa.String(), nullable=True))
    op.execute(
        "UPDATE \"user\" SET auth_source = 'local' "
        "WHERE hashed_password IS NOT NULL AND hashed_password <> ''"
    )


def downgrade() -> None:
    """Drop the login-source columns and sessionsettingsmodel."""
    op.drop_column("user", "idp_refresh_token")
    op.drop_column("user", "auth_source")
    op.drop_table("sessionsettingsmodel")
