"""Translation settings and per-user release

Revision ID: d7a2e9c4f1b6
Revises: c3f8a1d5e7b2
Create Date: 2026-11-06 18:00:00.000000

- ``translationsettingsmodel``: dictation in another language, translated into
  the instance language. Off by default (operator decision,
  docs/zweckbestimmung.md); ``access`` "selected" limits it to released users.
- ``user.translation_allowed``: that per-user release.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "d7a2e9c4f1b6"
down_revision: Union[str, Sequence[str], None] = "c3f8a1d5e7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the settings table and the per-user release."""
    op.create_table(
        "translationsettingsmodel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "access",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="selected",
        ),
        sa.Column(
            "languages",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="ru,uk,pl,ro,bg,sr,ar",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "translation_allowed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    """Drop the per-user release and the settings table."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("translation_allowed")
    op.drop_table("translationsettingsmodel")
