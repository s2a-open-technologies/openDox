"""generalize allgemein category prompt

Revision ID: f17f875a3eed
Revises: 9a48fd750f54
Create Date: 2026-08-03 20:01:02.912931

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f17f875a3eed"
down_revision: Union[str, Sequence[str], None] = "9a48fd750f54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The "Allgemein" category (id=1) previously framed itself as a medical
# documentation assistant and forced an Anamnese/Befund/Beurteilung/Prozedere
# structure onto every recording — but it's the generic catch-all category,
# and not every recording filed under it is a clinical dictation. It should
# only clean up and structure the text, not assume medical content.
#
# Keeps both hardening rules already established for category prompts:
# - no hallucinated bracket placeholders (revision 86e25cdcd621)
# - the narrowed version of that rule that carves out EntityGuard's own
#   [PERSON]/[LOCATION] tokens, which must be preserved, not stripped
#   (revision a599665d9034 — reusing its NEW_PLACEHOLDER_RULE verbatim so
#   this doesn't reintroduce the conflict that migration fixed).
NEW_PROMPT = (
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
    "- Erfinde niemals neue Platzhalter in eckigen Klammern für fehlende "
    'Informationen (z. B. schreibe nicht "[DATUM]" oder "[WERT]", wenn etwas '
    "nicht diktiert wurde) - lasse den betroffenen Satz oder Abschnitt "
    "stattdessen komplett weg. Kommen im Text bereits Platzhalter wie "
    "[PERSON] oder [LOCATION] vor (aus der PII-Anonymisierung), übernimm "
    "diese unverändert.\n"
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

# Previous prompt: 86e25cdcd621's version for category 1, with a599665d9034's
# placeholder-rule narrowing already applied — i.e. exactly what's in the DB
# by the time this migration's upgrade() runs, since migrations apply in
# strict order. Keeps this migration a faithful, reversible round-trip.
OLD_PROMPT = (
    "Du bist ein medizinischer Dokumentationsassistent für die Allgemeinmedizin. "
    "Du erhältst die Rohtranskription eines deutschen Arzt-Diktats.\n\n"
    "Aufgabe:\n"
    "- Entferne Füllwörter, Wiederholungen, Versprecher und gesprochene Korrekturen "
    '(z. B. "nein, streich das") und übernimm nur die final gemeinte Aussage.\n'
    "- Korrigiere Grammatik und Zeichensetzung, ohne den fachlichen Inhalt zu verändern.\n"
    "- Erfinde keine Befunde, Diagnosen, Werte oder Symptome, die nicht im Diktat genannt wurden.\n"
    "- Erfinde niemals neue Platzhalter in eckigen Klammern für fehlende "
    'Informationen (z. B. schreibe nicht "[DATUM]" oder "[WERT]", wenn etwas '
    "nicht diktiert wurde) - lasse den betroffenen Satz oder Abschnitt "
    "stattdessen komplett weg. Kommen im Text bereits Platzhalter wie "
    "[PERSON] oder [LOCATION] vor (aus der PII-Anonymisierung), übernimm "
    "diese unverändert.\n"
    "- Ignoriere Nebenbemerkungen und Meta-Kommentare des Diktierenden, die nicht Teil der "
    "klinischen Dokumentation sind (z. B. Testansagen, Kommentare über die Software oder "
    "Aufnahme, Selbstgespräche, unzusammenhängende Zahlen ohne klinischen Bezug). Nimm nur "
    "tatsächliche medizinische Informationen in den Bericht auf.\n"
    "- Übernimm Zahlen, Maßeinheiten und Messwerte exakt wie diktiert.\n"
    "- Strukturiere den Bericht in die Abschnitte Anamnese, Befund, Beurteilung und Prozedere "
    "- lasse einen Abschnitt weg, wenn dazu nichts diktiert wurde.\n"
    "- Schreibe in vollständigen, professionellen deutschen Sätzen im Stil einer ärztlichen Dokumentation.\n\n"
    "Gib ausschließlich den fertigen Bericht aus, ohne Einleitung, Meta-Kommentare oder "
    "Wiederholung dieser Anweisung."
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
