"""set live_backend default to parakeet

Revision ID: a5818ca7103b
Revises: f32c00dfb13b
Create Date: 2026-06-12 15:27:49.330969

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a5818ca7103b"
down_revision: Union[str, Sequence[str], None] = "f32c00dfb13b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update existing whisper settings to use Parakeet as live backend.

    The model default changed from 'api' to 'parakeet', but the seed data
    in the initial migration inserted 'api'. This aligns existing rows.
    """
    op.execute(
        "UPDATE whispersettingsmodel SET live_backend = 'parakeet' WHERE live_backend = 'api'"
    )


def downgrade() -> None:
    """Revert live_backend to 'api' (Whisper) for existing rows."""
    op.execute(
        "UPDATE whispersettingsmodel SET live_backend = 'api' WHERE live_backend = 'parakeet'"
    )