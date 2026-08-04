"""narrow allgemein category to punctuation-only cleanup

Revision ID: 3ad5334b1d34
Revises: 32b7beec3704
Create Date: 2026-08-03 23:22:29.300116

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ad5334b1d34"
down_revision: Union[str, Sequence[str], None] = "32b7beec3704"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The "Allgemein" category still tried to do too much (remove filler words,
# correct grammar, restructure into paragraphs) — narrowed further to only
# fix punctuation (periods/commas) and leave everything else, including very
# short/fragmentary text, untouched. Also explicitly forbids the model from
# commenting when there's little/nothing to do, instead of just passing the
# text through unchanged.
NEW_PROMPT = (
    "Du bist ein Assistent, der ausschließlich die Zeichensetzung eines "
    "deutschen Diktat-Transkripts korrigiert.\n\n"
    "Aufgabe:\n"
    "- Setze und korrigiere ausschließlich Punkte und Kommas, damit der "
    "Text lesbar ist.\n"
    "- Verändere sonst nichts am Text: keine Wortwahl, keine Grammatik, "
    "keine Umformulierung, keine Kürzung, keine Gliederung in Absätze, "
    "keine Entfernung von Füllwörtern oder Nebenbemerkungen.\n"
    "- Erfinde keine Informationen, Fakten oder Details, die nicht im "
    "Diktat genannt wurden.\n"
    "- Ist der Text sehr kurz oder fragmentarisch, lasse ihn unverändert "
    "und gib ihn exakt wie erhalten zurück.\n"
    "- Kommentiere niemals, dass der Text leer, zu kurz oder inhaltsleer "
    "sei. Gib keine Einleitung, Erklärung oder Meta-Kommentare aus — "
    "ausschließlich den resultierenden Text."
)

# Previous prompt (from migration f17f875a3eed), so this migration is reversible.
OLD_PROMPT = (
    "Du bist ein Assistent zur Bereinigung und Strukturierung von Diktaten. "
    "Du erhältst die Rohtranskription eines deutschen Audio-Diktats — der "
    "Inhalt kann, muss aber nicht medizinischer Natur sein.\n\n"
    "Aufgabe:\n"
    "- Entferne Füllwörter, Wiederholungen, Versprecher und gesprochene "
    'Korrekturen (z. B. "nein, streich das") und übernimm nur die final '
    "gemeinte Aussage.\n"
    "- Korrigiere Grammatik und Zeichensetzung, ohne den inhaltlichen Sinn "
    "zu verändern.\n"
    "- Erfinde keine Informationen, Fakten oder Details, die nicht im "
    "Diktat genannt wurden.\n"
    "- Ignoriere Nebenbemerkungen und Meta-Kommentare des Diktierenden, die "
    "nicht Teil des eigentlichen Inhalts sind (z. B. Testansagen, "
    "Kommentare über die Software oder Aufnahme, Selbstgespräche, "
    "unzusammenhängende Zahlen ohne erkennbaren Bezug).\n"
    "- Übernimm Zahlen, Maßeinheiten und Werte exakt wie diktiert.\n"
    "- Strukturiere den Text sinnvoll entsprechend seinem tatsächlichen "
    "Inhalt in Absätze — erzwinge keine medizinische Gliederung (z. B. "
    "Anamnese/Befund/Beurteilung/Prozedere), wenn der Inhalt das nicht "
    "hergibt.\n"
    "- Schreibe in vollständigen, klaren deutschen Sätzen.\n\n"
    "Gib ausschließlich den fertigen Text aus, ohne Einleitung, "
    "Meta-Kommentare oder Wiederholung dieser Anweisung."
)


def _set_prompt(prompt: str) -> None:
    op.execute(
        sa.text(
            "UPDATE categories SET system_prompt = :prompt WHERE id = 1"
        ).bindparams(prompt=prompt)
    )


def upgrade() -> None:
    """Upgrade schema."""
    _set_prompt(NEW_PROMPT)


def downgrade() -> None:
    """Downgrade schema."""
    _set_prompt(OLD_PROMPT)
