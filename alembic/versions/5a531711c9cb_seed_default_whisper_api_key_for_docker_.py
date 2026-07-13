"""seed default whisper api key for docker deployment.

Revision ID: 5a531711c9cb
Revises: afc120622bb8
Create Date: 2026-07-13 09:07:40.334345

docker-compose.yml no longer passes WHISPER_API_KEY to the app container
(only to the whisper service itself) — that env var was only ever a
fallback for whispersettingsmodel.live_api_key/final_api_key when the DB
columns are empty. Without it, a fresh deployment's app can't authenticate
against the whisper container, which still requires the same key. Seed the
matching default here instead, guarded to never overwrite a key an operator
already configured via the Admin UI.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "5a531711c9cb"
down_revision: Union[str, Sequence[str], None] = "afc120622bb8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed live_api_key/final_api_key with the demo default, if unset."""
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_api_key = 'loc-123' "
        "WHERE id = 1 AND (live_api_key IS NULL OR live_api_key = '')"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET final_api_key = 'loc-123' "
        "WHERE id = 1 AND (final_api_key IS NULL OR final_api_key = '')"
    )


def downgrade() -> None:
    """Clear live_api_key/final_api_key, but only if still the demo default."""
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET live_api_key = NULL "
        "WHERE id = 1 AND live_api_key = 'loc-123'"
    )
    op.execute(
        "UPDATE whispersettingsmodel "
        "SET final_api_key = NULL "
        "WHERE id = 1 AND final_api_key = 'loc-123'"
    )
