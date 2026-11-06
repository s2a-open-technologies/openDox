"""Built-in "Standard" category and admin-chosen default category

Revision ID: c3f8a1d5e7b2
Revises: b9e3f1a7c624
Create Date: 2026-11-06 10:00:00.000000

- ``categories.is_builtin``: the category shipped with openDox. Its name,
  description and system prompt cannot be changed or deleted through the
  API (docs/zweckbestimmung.md §6).
- ``categories.is_default``: the global category preselected for everyone,
  chosen by an admin/moderator. None set → the built-in one.
- The global seed category "Allgemein" becomes the built-in "Standard";
  if it was deleted, "Standard" is created with the current prompt.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c3f8a1d5e7b2"
down_revision: Union[str, Sequence[str], None] = "b9e3f1a7c624"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STANDARD_NAME = "Standard"
OLD_NAME = "Allgemein"
STANDARD_DESCRIPTION = "Allgemeine Dokumentation ohne spezialisierten Fokus."

# Prompt of "Allgemein" as last set by migration 3ad5334b1d34.
STANDARD_PROMPT = (
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

_categories = sa.table(
    "categories",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("system_prompt", sa.String),
    sa.column("llm_enabled", sa.Boolean),
    sa.column("llm_override_enabled", sa.Boolean),
    sa.column("user_id", sa.Integer),
    sa.column("is_builtin", sa.Boolean),
    sa.column("is_default", sa.Boolean),
)


def upgrade() -> None:
    """Add the flags and turn "Allgemein" into the built-in "Standard"."""
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    bind = op.get_bind()
    allgemein_id = bind.execute(
        sa.select(_categories.c.id)
        .where(_categories.c.name == OLD_NAME, _categories.c.user_id.is_(None))
        .order_by(_categories.c.id)
        .limit(1)
    ).scalar()
    if allgemein_id is not None:
        bind.execute(
            _categories.update()
            .where(_categories.c.id == allgemein_id)
            .values(name=STANDARD_NAME, is_builtin=True)
        )
    else:
        bind.execute(
            _categories.insert().values(
                name=STANDARD_NAME,
                description=STANDARD_DESCRIPTION,
                system_prompt=STANDARD_PROMPT,
                llm_enabled=True,
                llm_override_enabled=False,
                user_id=None,
                is_builtin=True,
                is_default=False,
            )
        )


def downgrade() -> None:
    """Rename "Standard" back to "Allgemein" and drop the flags."""
    bind = op.get_bind()
    bind.execute(
        _categories.update()
        .where(_categories.c.is_builtin.is_(True))
        .values(name=OLD_NAME)
    )
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("is_default")
        batch_op.drop_column("is_builtin")
