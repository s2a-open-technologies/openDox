"""clarify placeholder rule to not conflict with EntityGuard tokens

Revision ID: a599665d9034
Revises: 86e25cdcd621
Create Date: 2026-07-06 22:46:11.751970

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a599665d9034'
down_revision: Union[str, Sequence[str], None] = '86e25cdcd621'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Migration 86e25cdcd621 told the LLM to never use bracket placeholders. That
# directly contradicts sanitizing_service._PRESERVE_TOKENS_INSTRUCTION, which is
# appended to this same prompt whenever the EntityGuard PII sanitizer is active
# and tells the LLM the opposite: keep [PERSON]/[LOCATION]-style tokens exactly
# as-is. This migration narrows the rule to only forbid *inventing new*
# placeholders for missing information, while explicitly carving out existing
# EntityGuard tokens that must be preserved.
OLD_PLACEHOLDER_RULE = (
    "Verwende niemals Platzhalter in eckigen Klammern (z. B. [PERSON], [DATUM], "
    "[WERT]) oder Musterformulierungen. Fehlt eine Angabe, lasse den betroffenen "
    "Satz oder ganzen Abschnitt komplett weg, anstatt eine Lücke zu markieren."
)

NEW_PLACEHOLDER_RULE = (
    "Erfinde niemals neue Platzhalter in eckigen Klammern für fehlende "
    "Informationen (z. B. schreibe nicht \"[DATUM]\" oder \"[WERT]\", wenn etwas "
    "nicht diktiert wurde) - lasse den betroffenen Satz oder Abschnitt "
    "stattdessen komplett weg. Kommen im Text bereits Platzhalter wie [PERSON] "
    "oder [LOCATION] vor (aus der PII-Anonymisierung), übernimm diese unverändert."
)


def _swap_rule(prompt: str) -> str:
    return prompt.replace(OLD_PLACEHOLDER_RULE, NEW_PLACEHOLDER_RULE)


CATEGORY_IDS = (1, 2, 3, 4)


def _apply(swap) -> None:
    conn = op.get_bind()
    for cat_id in CATEGORY_IDS:
        row = conn.execute(
            sa.text("SELECT system_prompt FROM categories WHERE id = :id"),
            {"id": cat_id},
        ).fetchone()
        if row is None:
            continue
        conn.execute(
            sa.text("UPDATE categories SET system_prompt = :prompt WHERE id = :id"),
            {"id": cat_id, "prompt": swap(row[0])},
        )


def upgrade() -> None:
    """Upgrade schema."""
    _apply(_swap_rule)


def downgrade() -> None:
    """Downgrade schema."""
    _apply(lambda p: p.replace(NEW_PLACEHOLDER_RULE, OLD_PLACEHOLDER_RULE))
