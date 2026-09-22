"""set overlap_s to 0 to prevent Whisper repetition at chunk boundaries

Revision ID: 68077d2430d7
Revises: a65412656c1b
Create Date: 2026-06-12

Audio overlap combined with chunked live transcription caused Whisper to
transcribe the same audio twice (last N seconds of chunk A = first N seconds
of chunk B).  The fix: no overlap.  The rolling prompt (active when
overlap_s == 0) handles context at chunk boundaries via text instead.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "68077d2430d7"
down_revision: Union[str, Sequence[str], None] = "59f52cbb0b66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE whispersettingsmodel SET overlap_s = 0")


def downgrade() -> None:
    op.execute("UPDATE whispersettingsmodel SET overlap_s = 0.5")
