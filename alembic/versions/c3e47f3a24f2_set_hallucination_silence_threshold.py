"""set hallucination_silence_threshold default to 2.0

Revision ID: c3e47f3a24f2
Revises: 68077d2430d7
Create Date: 2026-06-12

Activates hallucination suppression for near-live chunked transcription.
The parameter is only effective when word_timestamps=True in the Whisper
server (also added in this release).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c3e47f3a24f2"
down_revision: Union[str, Sequence[str], None] = "68077d2430d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET hallucination_silence_threshold = 2.0 "
        "WHERE hallucination_silence_threshold IS NULL"
    )


def downgrade() -> None:
    op.execute("UPDATE whispersettingsmodel SET hallucination_silence_threshold = NULL")
