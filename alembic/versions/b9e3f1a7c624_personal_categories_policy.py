"""Operator switch for personal categories

Revision ID: b9e3f1a7c624
Revises: a4d7e2c9b513
Create Date: 2026-11-02 15:00:00.000000

- ``llmsettingsmodel.personal_categories_allowed``: whether users may create
  their own categories (own LLM prompts). Off by default, also for existing
  installations: such prompts bypass the operator's control over the
  intended purpose (docs/zweckbestimmung.md §6). Existing personal
  categories stay in the database but have no effect while it is off.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b9e3f1a7c624"
down_revision: Union[str, Sequence[str], None] = "a4d7e2c9b513"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the personal-categories switch."""
    op.add_column(
        "llmsettingsmodel",
        sa.Column(
            "personal_categories_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Drop the personal-categories switch."""
    op.drop_column("llmsettingsmodel", "personal_categories_allowed")
