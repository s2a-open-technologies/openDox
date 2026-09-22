"""merge left_context_s and user role heads

Revision ID: c96a01a8533f
Revises: b44de8fb75d9, d15162a50b79
Create Date: 2026-07-08 22:16:08.091329

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "c96a01a8533f"
down_revision: Union[str, Sequence[str], None] = ("b44de8fb75d9", "d15162a50b79")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
