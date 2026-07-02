"""Seed default Docker service endpoints and model names

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-02 00:02:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set Parakeet and Whisper endpoints in whisper settings
    op.execute(sa.text("""
        UPDATE whispersettingsmodel SET
            live_api_endpoint  = 'http://parakeet:5001/v1',
            live_api_model     = 'nemo-parakeet-tdt-0.6b-v3',
            final_api_endpoint = 'http://whisper:5002/v1',
            final_api_model    = 'whisper-1'
        WHERE id = 1
    """))

    # Insert default LLM settings (Ollama on host via Docker DNS)
    op.execute(sa.text("""
        INSERT INTO llmsettingsmodel
            (id, llm_api_endpoint, llm_api_key, llm_model,
             llm_temperature, llm_max_tokens, correction_model,
             sanitizer_enabled, sanitizer_endpoint, sanitizer_api_key, sanitizer_department)
        VALUES
            (1, 'http://host.docker.internal:11434/v1', NULL, 'medgemma-4b-it:Q4_K_M',
             0.2, 2048, NULL,
             false, NULL, NULL, 'standard')
        ON CONFLICT (id) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE whispersettingsmodel SET
            live_api_endpoint  = NULL,
            live_api_model     = 'whisper-1',
            final_api_endpoint = NULL,
            final_api_model    = 'whisper-1'
        WHERE id = 1
    """))
    op.execute(sa.text("DELETE FROM llmsettingsmodel WHERE id = 1"))
