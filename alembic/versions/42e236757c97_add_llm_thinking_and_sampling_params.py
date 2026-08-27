"""add llm thinking and sampling params

Revision ID: 42e236757c97
Revises: 2efe299f2cf0
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42e236757c97'
down_revision: Union[str, Sequence[str], None] = '2efe299f2cf0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for table in ("llmsettingsmodel", "categories"):
        op.add_column(table, sa.Column("llm_top_p", sa.Float(), nullable=True))
        op.add_column(
            table, sa.Column("llm_frequency_penalty", sa.Float(), nullable=True)
        )
        op.add_column(
            table, sa.Column("llm_enable_thinking", sa.Boolean(), nullable=True)
        )

    # Seed sensible summarization defaults on the global LLM settings row
    # only (id=1) — reasoning/"thinking" models (MedGemma, Qwen3,
    # DeepSeek-R1-style) can hang or take far too long during summarization,
    # so thinking is disabled out of the box. Category overrides stay NULL
    # (= inherit the global value) and are intentionally not seeded here.
    # Guarded so an already-configured value is never overwritten.
    op.execute(sa.text(
        "UPDATE llmsettingsmodel SET llm_top_p = 0.9 "
        "WHERE id = 1 AND llm_top_p IS NULL"
    ))
    op.execute(sa.text(
        "UPDATE llmsettingsmodel SET llm_frequency_penalty = 0.3 "
        "WHERE id = 1 AND llm_frequency_penalty IS NULL"
    ))
    op.execute(sa.text(
        "UPDATE llmsettingsmodel SET llm_enable_thinking = false "
        "WHERE id = 1 AND llm_enable_thinking IS NULL"
    ))


def downgrade() -> None:
    """Downgrade schema."""
    for table in ("llmsettingsmodel", "categories"):
        op.drop_column(table, "llm_enable_thinking")
        op.drop_column(table, "llm_frequency_penalty")
        op.drop_column(table, "llm_top_p")
