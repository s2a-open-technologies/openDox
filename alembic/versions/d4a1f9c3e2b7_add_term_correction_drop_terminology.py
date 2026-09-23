"""add term correction settings, drop unused terminology table

Revision ID: d4a1f9c3e2b7
Revises: 77f57080cf5f
Create Date: 2026-09-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a1f9c3e2b7"
down_revision: Union[str, Sequence[str], None] = "77f57080cf5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "whispersettingsmodel",
        sa.Column(
            "term_correction_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "whispersettingsmodel",
        sa.Column(
            "term_correction_threshold",
            sa.Float(),
            nullable=False,
            server_default="85.0",
        ),
    )
    op.drop_table("terminology")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "terminology",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("official_text", sa.String(), nullable=False),
        sa.Column("custom_alias", sa.String(), nullable=True),
        sa.Column(
            "is_protected", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("year", sa.Integer(), nullable=False, server_default="2026"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_terminology_code"), "terminology", ["code"], unique=True)
    op.create_index(op.f("ix_terminology_type"), "terminology", ["type"], unique=False)

    op.drop_column("whispersettingsmodel", "term_correction_threshold")
    op.drop_column("whispersettingsmodel", "term_correction_enabled")
