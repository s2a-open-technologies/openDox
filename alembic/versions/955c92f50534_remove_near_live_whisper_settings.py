"""remove near-live whisper settings

The fixed-chunk "near-live" Whisper path (live_backend = "api") was removed;
Parakeet streaming is the only live transcription. Drop the settings that only
that path used and turn rows that still selected it into "disabled" (a Parakeet
endpoint is not guaranteed to exist on every deployment).

Revision ID: 955c92f50534
Revises: e3b7c1a95d42
Create Date: 2026-10-15 20:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "955c92f50534"
down_revision: Union[str, Sequence[str], None] = "e3b7c1a95d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "whispersettingsmodel"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            f"UPDATE {TABLE} SET live_backend = 'disabled' WHERE live_backend = 'api'"
        )
    )
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column("chunk_length_s")
        batch.drop_column("overlap_s")
        batch.drop_column("left_context_s")
        batch.drop_column("live_beam_size")
        batch.drop_column("live_api_model")


def downgrade() -> None:
    """Downgrade schema (columns come back with their old defaults)."""
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(
            sa.Column(
                "chunk_length_s", sa.Integer(), nullable=False, server_default="3"
            )
        )
        batch.add_column(
            sa.Column("overlap_s", sa.Float(), nullable=False, server_default="0.0")
        )
        batch.add_column(
            sa.Column(
                "left_context_s", sa.Float(), nullable=False, server_default="1.0"
            )
        )
        batch.add_column(
            sa.Column(
                "live_beam_size", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch.add_column(sa.Column("live_api_model", sa.String(), nullable=True))
