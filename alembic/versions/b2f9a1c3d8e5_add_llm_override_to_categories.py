"""add llm override fields to categories

Revision ID: b2f9a1c3d8e5
Revises: 431daad54f38
Create Date: 2026-06-12

Per-category LLM override: optional model, endpoint, key, temperature and
max_tokens. llm_override_enabled (default False) acts as a switch — when False
the global LLM settings are used regardless of the other fields.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2f9a1c3d8e5"
down_revision: Union[str, Sequence[str], None] = "a5818ca7103b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column(
            "llm_override_enabled", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "categories",
        sa.Column("llm_model", sa.String(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("llm_api_endpoint", sa.String(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("llm_api_key", sa.String(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("llm_temperature", sa.Float(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("llm_max_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("categories", "llm_max_tokens")
    op.drop_column("categories", "llm_temperature")
    op.drop_column("categories", "llm_api_key")
    op.drop_column("categories", "llm_api_endpoint")
    op.drop_column("categories", "llm_model")
    op.drop_column("categories", "llm_override_enabled")
