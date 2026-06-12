"""add whisper anti-hallucination tuning params

Revision ID: a65412656c1b
Revises: 799c91e33c3a
Create Date: 2026-06-12

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a65412656c1b"
down_revision: Union[str, Sequence[str], None] = "799c91e33c3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, type, server_default) — server_default is a string literal for SQL
_COLUMNS = [
    ("temperature", sa.Float(), "0.0"),
    ("vad_filter", sa.Boolean(), "1"),
    ("vad_min_silence_ms", sa.Integer(), "500"),
    ("condition_on_previous_text", sa.Boolean(), "0"),
    ("no_speech_threshold", sa.Float(), "0.6"),
    ("compression_ratio_threshold", sa.Float(), "2.4"),
    ("log_prob_threshold", sa.Float(), "-1.0"),
    ("live_beam_size", sa.Integer(), "1"),
    ("final_beam_size", sa.Integer(), "5"),
]


def upgrade() -> None:
    """Upgrade schema."""
    for name, coltype, default in _COLUMNS:
        op.add_column(
            "whispersettingsmodel",
            sa.Column(name, coltype, nullable=False, server_default=default),
        )
    # Nullable float — no server default
    op.add_column(
        "whispersettingsmodel",
        sa.Column("hallucination_silence_threshold", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    for name in (
        "hallucination_silence_threshold",
        "final_beam_size",
        "live_beam_size",
        "log_prob_threshold",
        "compression_ratio_threshold",
        "no_speech_threshold",
        "condition_on_previous_text",
        "vad_min_silence_ms",
        "vad_filter",
        "temperature",
    ):
        op.drop_column("whispersettingsmodel", name)
