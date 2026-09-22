"""encrypt record title, ldap bind password, oidc client secret.

Revision ID: 7e968ca8ac3f
Revises: dfba80abfe0c
Create Date: 2026-08-02 23:39:24.853090

No schema change is needed here: EncryptedString wraps String/VARCHAR, so
the underlying column type is unchanged — only how the app reads/writes it.
What this migration actually needs to do is re-encrypt the *existing*
plaintext values in these three columns, since new writes will already be
Fernet-encrypted (via EncryptedString) but old rows were written before
that column started encrypting.

Idempotent: uses the same decrypt()-round-trip check the app already relies
on elsewhere (decrypt(value) == value means Fernet couldn't decrypt it, i.e.
it's still plaintext) — safe to re-run, and a no-op if ENCRYPTION_KEY isn't
set (encrypt()/decrypt() pass values through unchanged in that case, same
as the rest of the app).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from backend.components.security.field_encryption import decrypt, encrypt

# revision identifiers, used by Alembic.
revision: str = "7e968ca8ac3f"
down_revision: Union[str, Sequence[str], None] = "dfba80abfe0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _encrypt_existing_values(
    table_name: str, id_column: str, value_column: str
) -> None:
    """Re-encrypt any not-yet-encrypted values in table_name.value_column."""
    bind = op.get_bind()
    table = sa.table(
        table_name,
        sa.column(id_column, sa.Integer),
        sa.column(value_column, sa.String),
    )
    rows = bind.execute(sa.select(table.c[id_column], table.c[value_column])).fetchall()
    for row_id, value in rows:
        if not value:
            continue
        if decrypt(value) != value:
            # Already a valid Fernet token for the current key — leave as-is.
            continue
        bind.execute(
            table.update()
            .where(table.c[id_column] == row_id)
            .values({value_column: encrypt(value)})
        )


def upgrade() -> None:
    """Upgrade schema."""
    _encrypt_existing_values("record", "id", "title")
    _encrypt_existing_values("ldapsettingsmodel", "id", "bind_user_password")
    _encrypt_existing_values("oidcsettingsmodel", "id", "client_secret")


def downgrade() -> None:
    """Downgrade schema.

    Not reversed: decrypting back to plaintext on downgrade would re-expose
    data this migration exists to protect. If you need to roll back the
    EncryptedString column change itself, do so in code/model only — the
    already-encrypted values in the DB remain valid ciphertext and continue
    to work once the column is EncryptedString again.
    """
