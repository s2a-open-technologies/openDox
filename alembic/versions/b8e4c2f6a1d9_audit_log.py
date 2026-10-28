"""Admin audit log

Revision ID: b8e4c2f6a1d9
Revises: a3d7e1b9c4f2
Create Date: 2026-10-28 12:00:00.000000

New table ``auditevent``: privileged actions and security events (failed
logins, denied requests). Append-only from the app's side, pruned after
``AUDIT_RETENTION_DAYS``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision: str = "b8e4c2f6a1d9"
down_revision: Union[str, Sequence[str], None] = "a3d7e1b9c4f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create auditevent with its lookup indexes."""
    op.create_table(
        "auditevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("actor_role", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("outcome", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auditevent_timestamp", "auditevent", ["timestamp"])
    op.create_index("ix_auditevent_actor_user_id", "auditevent", ["actor_user_id"])
    op.create_index("ix_auditevent_action", "auditevent", ["action"])


def downgrade() -> None:
    """Drop auditevent."""
    op.drop_index("ix_auditevent_action", table_name="auditevent")
    op.drop_index("ix_auditevent_actor_user_id", table_name="auditevent")
    op.drop_index("ix_auditevent_timestamp", table_name="auditevent")
    op.drop_table("auditevent")
