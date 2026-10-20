"""dictionaries replace free-text glossaries; drop seed categories

Revision ID: f8c2d4a6b1e3
Revises: d52a8b3f1c70
Create Date: 2026-10-20 21:00:00.000000

- New tables ``dictionary`` and ``categorydictionarylink``.
- Every non-empty ``categories.glossary`` becomes a dictionary named after
  its category (same scope: global or the category owner's), attached to it.
- Every non-empty ``user.personal_glossary`` becomes the personal dictionary
  "Mein Wörterbuch", attached to all of that user's own categories (a
  dictionary now only takes effect through a category).
- Both free-text columns are dropped.
- The seed categories Kardiologie, Orthopädie and Gynäkologie are deleted;
  recordings using them move to "Allgemein" (or no category if it is gone).

Dictionary terms are stored encrypted (``EncryptedString``); the glossary
values are read through ``decrypt`` since ``personal_glossary`` was encrypted
and ``glossary`` was not (``decrypt`` returns non-tokens unchanged).
"""

import re
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from backend.components.security.field_encryption import decrypt, encrypt

revision: str = "f8c2d4a6b1e3"
down_revision: Union[str, Sequence[str], None] = "d52a8b3f1c70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REMOVED_SEED_CATEGORIES = ("Kardiologie", "Orthopädie", "Gynäkologie")
_PERSONAL_DICTIONARY_NAME = "Mein Wörterbuch"

_categories = sa.table(
    "categories",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("user_id", sa.Integer),
    sa.column("glossary", sa.Text),
)
_users = sa.table(
    "user",
    sa.column("id", sa.Integer),
    sa.column("personal_glossary", sa.Text),
)
_records = sa.table(
    "record",
    sa.column("id", sa.Integer),
    sa.column("category_id", sa.Integer),
)
_dictionary = sa.table(
    "dictionary",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("user_id", sa.Integer),
    sa.column("terms", sa.String),
    sa.column("term_count", sa.Integer),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
_links = sa.table(
    "categorydictionarylink",
    sa.column("category_id", sa.Integer),
    sa.column("dictionary_id", sa.Integer),
)


def _split_legacy(text: str | None) -> list[str]:
    """Old parse_glossary(): comma/semicolon/newline, >= 3 chars, deduped."""
    seen: set[str] = set()
    terms: list[str] = []
    for raw in re.split(r"[,;\n]+", text or ""):
        term = raw.strip()
        if len(term) < 3 or term.lower() in seen:
            continue
        seen.add(term.lower())
        terms.append(term[:200])
    return terms


def _insert_dictionary(bind, name: str, user_id, terms: list[str]) -> int:
    return bind.execute(
        _dictionary.insert()
        .values(
            name=name,
            user_id=user_id,
            terms=encrypt("\n".join(terms)),
            term_count=len(terms),
            updated_at=datetime.now(timezone.utc),
        )
        .returning(_dictionary.c.id)
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dictionary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("terms", sa.String(), nullable=False),
        sa.Column("term_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dictionary_user_id", "dictionary", ["user_id"])
    op.create_table(
        "categorydictionarylink",
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("dictionary_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dictionary_id"], ["dictionary.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("category_id", "dictionary_id"),
    )

    bind = op.get_bind()
    categories = bind.execute(
        sa.select(
            _categories.c.id,
            _categories.c.name,
            _categories.c.user_id,
            _categories.c.glossary,
        )
    ).fetchall()

    for cat_id, cat_name, cat_user_id, glossary in categories:
        terms = _split_legacy(decrypt(glossary) if glossary else None)
        if terms:
            dictionary_id = _insert_dictionary(bind, cat_name, cat_user_id, terms)
            bind.execute(
                _links.insert().values(category_id=cat_id, dictionary_id=dictionary_id)
            )

    users = bind.execute(
        sa.select(_users.c.id, _users.c.personal_glossary).where(
            _users.c.personal_glossary.is_not(None)
        )
    ).fetchall()
    for user_id, personal_glossary in users:
        terms = _split_legacy(decrypt(personal_glossary))
        if not terms:
            continue
        dictionary_id = _insert_dictionary(
            bind, _PERSONAL_DICTIONARY_NAME, user_id, terms
        )
        for cat_id, _name, cat_user_id, _g in categories:
            if cat_user_id == user_id:
                bind.execute(
                    _links.insert().values(
                        category_id=cat_id, dictionary_id=dictionary_id
                    )
                )

    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("glossary")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("personal_glossary")

    # Seed categories other than "Allgemein": recordings move to Allgemein.
    allgemein_id = bind.execute(
        sa.select(_categories.c.id)
        .where(_categories.c.name == "Allgemein", _categories.c.user_id.is_(None))
        .order_by(_categories.c.id)
        .limit(1)
    ).scalar()
    removed_ids = [
        row[0]
        for row in bind.execute(
            sa.select(_categories.c.id).where(
                _categories.c.name.in_(_REMOVED_SEED_CATEGORIES),
                _categories.c.user_id.is_(None),
            )
        )
    ]
    if removed_ids:
        bind.execute(
            _records.update()
            .where(_records.c.category_id.in_(removed_ids))
            .values(category_id=allgemein_id)
        )
        bind.execute(_links.delete().where(_links.c.category_id.in_(removed_ids)))
        bind.execute(_categories.delete().where(_categories.c.id.in_(removed_ids)))


def downgrade() -> None:
    """Downgrade schema.

    Restores the free-text columns from the dictionaries (one term per line,
    which the old comma/semicolon/newline parser reads fine). The deleted
    seed categories are not recreated.
    """
    op.add_column("categories", sa.Column("glossary", sa.Text(), nullable=True))
    op.add_column("user", sa.Column("personal_glossary", sa.Text(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            _links.c.category_id,
            _dictionary.c.terms,
        ).select_from(
            _links.join(_dictionary, _links.c.dictionary_id == _dictionary.c.id)
        )
    ).fetchall()
    by_category: dict[int, list[str]] = {}
    for cat_id, terms in rows:
        by_category.setdefault(cat_id, []).append(decrypt(terms))
    for cat_id, parts in by_category.items():
        bind.execute(
            _categories.update()
            .where(_categories.c.id == cat_id)
            .values(glossary="\n".join(p for p in parts if p))
        )

    personal = bind.execute(
        sa.select(_dictionary.c.user_id, _dictionary.c.terms).where(
            _dictionary.c.user_id.is_not(None)
        )
    ).fetchall()
    by_user: dict[int, list[str]] = {}
    for user_id, terms in personal:
        by_user.setdefault(user_id, []).append(decrypt(terms))
    for user_id, parts in by_user.items():
        bind.execute(
            _users.update()
            .where(_users.c.id == user_id)
            .values(personal_glossary=encrypt("\n".join(p for p in parts if p)))
        )

    op.drop_table("categorydictionarylink")
    op.drop_index("ix_dictionary_user_id", table_name="dictionary")
    op.drop_table("dictionary")
