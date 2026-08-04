"""strip redundant placeholder rule from category prompts

Revision ID: 32b7beec3704
Revises: f17f875a3eed
Create Date: 2026-08-03 20:19:44.577769

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32b7beec3704"
down_revision: Union[str, Sequence[str], None] = "f17f875a3eed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The placeholder-hallucination rule is now appended unconditionally in code
# (SummarizeModel.generate_response()) to every prompt regardless of source —
# an admin creating a new category via the UI has no way of knowing to write
# it themselves, so it can't live only in prompt text. Strips it out of the
# 4 seeded categories' stored system_prompt, leaving a single source of
# truth (code) instead of copies that could drift out of sync.
RULE_LINE = (
    "- Erfinde niemals neue Platzhalter in eckigen Klammern für fehlende "
    'Informationen (z. B. schreibe nicht "[DATUM]" oder "[WERT]", wenn etwas '
    "nicht diktiert wurde) - lasse den betroffenen Satz oder Abschnitt "
    "stattdessen komplett weg. Kommen im Text bereits Platzhalter wie "
    "[PERSON] oder [LOCATION] vor (aus der PII-Anonymisierung), übernimm "
    "diese unverändert.\n"
)

# The bullet immediately preceding RULE_LINE in each category — differs per
# category, so it doubles as a unique reinsertion anchor for downgrade().
ANCHOR = {
    1: (
        "- Erfinde keine Informationen, Fakten oder Details, die nicht im "
        "Diktat genannt wurden.\n"
    ),
    2: (
        "- Erfinde keine Diagnosen, Werte oder apparativen Befunde, die nicht "
        "diktiert wurden.\n"
    ),
    3: (
        "- Erfinde keine Befunde, Diagnosen oder Messwerte (z. B. Bewegungsumfang, "
        "Kraftgrade), die nicht diktiert wurden.\n"
    ),
    4: (
        "- Erfinde keine Befunde, Diagnosen oder Werte (z. B. Zyklusangaben, "
        "Schwangerschaftswoche, Tastbefunde), die nicht diktiert wurden.\n"
    ),
}


def _apply(swap) -> None:
    conn = op.get_bind()
    for cat_id in ANCHOR:
        row = conn.execute(
            sa.text("SELECT system_prompt FROM categories WHERE id = :id"),
            {"id": cat_id},
        ).fetchone()
        if row is None:
            continue
        conn.execute(
            sa.text("UPDATE categories SET system_prompt = :prompt WHERE id = :id"),
            {"id": cat_id, "prompt": swap(cat_id, row[0])},
        )


def upgrade() -> None:
    """Upgrade schema."""
    _apply(lambda _cat_id, prompt: prompt.replace(RULE_LINE, ""))


def downgrade() -> None:
    """Downgrade schema."""
    _apply(
        lambda cat_id, prompt: prompt.replace(
            ANCHOR[cat_id], ANCHOR[cat_id] + RULE_LINE
        )
    )
