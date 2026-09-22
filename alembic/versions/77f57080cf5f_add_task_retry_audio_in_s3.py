"""add task retry_audio_in_s3

Revision ID: 77f57080cf5f
Revises: 42e236757c97
Create Date: 2026-09-22 12:39:43.986484

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77f57080cf5f"
down_revision: Union[str, Sequence[str], None] = "42e236757c97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "task",
        sa.Column(
            "retry_audio_in_s3",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("task", "retry_audio_in_s3", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("task", "retry_audio_in_s3")
