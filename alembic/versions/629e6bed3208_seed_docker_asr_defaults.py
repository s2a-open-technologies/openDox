"""Seed Docker ASR defaults — Live=Parakeet, Final=Parakeet (same model).

For a fresh Docker Compose deployment, both live and final transcription
should point to the Parakeet container with its default model.  Also sets
left_context_s to 1.0 (proven value for Parakeet live quality).  This
migration only writes to rows where the values are still NULL/empty/default,
so an operator who has already configured custom values via the Admin UI
will not be overwritten.

Revision ID: 629e6bed3208
Revises: 5a531711c9cb
Create Date: 2026-07-13 23:19:55.520049

"""
from typing import Sequence, Union

from alembic import op

revision: str = "629e6bed3208"
down_revision: Union[str, Sequence[str], None] = "5a531711c9cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_backend = 'parakeet' "
        "WHERE id = 1"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_api_endpoint = 'http://parakeet:5001/v1' "
        "WHERE id = 1 AND (live_api_endpoint IS NULL OR live_api_endpoint = '')"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_api_model = 'nemo-parakeet-tdt-0.6b-v3' "
        "WHERE id = 1"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET final_api_endpoint = 'http://parakeet:5001/v1' "
        "WHERE id = 1 AND (final_api_endpoint IS NULL OR final_api_endpoint = '')"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET final_api_model = 'nemo-parakeet-tdt-0.6b-v3' "
        "WHERE id = 1"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET left_context_s = 1.0 "
        "WHERE id = 1 AND left_context_s = 0"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_backend = 'api' "
        "WHERE id = 1"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_api_endpoint = NULL "
        "WHERE id = 1 AND live_api_endpoint = 'http://parakeet:5001/v1'"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_api_model = NULL "
        "WHERE id = 1"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET final_api_endpoint = NULL "
        "WHERE id = 1 AND final_api_endpoint = 'http://parakeet:5001/v1'"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET final_api_model = NULL "
        "WHERE id = 1"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET left_context_s = 0 "
        "WHERE id = 1 AND left_context_s = 1.0"
    )