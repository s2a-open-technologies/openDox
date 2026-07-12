# Automatic encryption-key rotation on container startup

## Problem

`ENCRYPTION_KEY` (Fernet, `backend/components/security/field_encryption.py`)
encrypts `Record.content`, `Record.summarize` and `Record.pii_mapping` at
rest. The key is loaded once at import time into a module-level `_fernet`
singleton. If an operator swaps `ENCRYPTION_KEY` for a new value (rotation
after a suspected compromise, employee departure, annual review — see
`docs/SECURITY.md`'s "Key Rotation" section), every previously-encrypted row
becomes unreadable: `decrypt()` catches `InvalidToken` and silently returns
the raw ciphertext string, so the app doesn't crash, it just serves garbled
data back to the user.

`docs/SECURITY.md:192` already claims "Fernet supports key rotation via
`MultiFernet`" and sketches a re-encryption migration script, but that
script is an unimplemented stub (`pass`). This spec makes key rotation
actually work, automatically, at container startup — matching the existing
pattern where `_run_alembic_migrations()` already runs unattended at boot
(`backend/run.py:170`).

## Goal

When an operator rotates `ENCRYPTION_KEY`, the app detects this on its next
startup and re-encrypts all existing encrypted data under the new key,
without requiring a manual migration step or downtime beyond the normal
container restart.

## Non-goals

- No live, in-app key rotation while the app is running — rotation is tied
  to a container restart, consistent with how the user described the
  requirement ("beim Start des Containers").
- `ENCRYPTION_KEY` / `ENCRYPTION_KEY_PREVIOUS` are **not** made UI-editable
  and are **not** stored in the database. This is a deliberate security
  boundary, not an oversight — see "Why env-only" below.
- No support for chaining more than one rotation at a time (i.e. no
  arbitrary-length key history / generalized `MultiFernet` list). One
  "current" + one "previous" key is enough to cover the described use case;
  multi-hop rotation would need `ENCRYPTION_KEY_PREVIOUS` updated once per
  historical key across multiple restarts, which is out of scope here.
- No automated test suite (none exists in this repo per AGENTS.md) — a
  manual verification procedure is included instead.

## Why env-only (not DB / not UI)

`ENCRYPTION_KEY` is the root secret protecting PHI at rest. Storing it (or
making it editable) in the database would put the key alongside the data it
protects — a DB dump/backup would then contain both, defeating the specific
threat model field-level encryption exists for (a leaked database without
server/filesystem access). This is also why the existing Settings
Backup/Restore feature (`GET /api/v1/settings/backup/`) already excludes the
`User` table (password hashes); putting the encryption key into a
DB-backed, UI-editable settings table would similarly leak it into that
JSON export. `ENCRYPTION_KEY` and the new `ENCRYPTION_KEY_PREVIOUS` stay
env-var / Docker-secret only, using the existing `env_or_file()` `_FILE`
convention. The admin UI only ever shows rotation *status*, never the key
value.

## Design

### 1. New table: `EncryptionKeyState`

`backend/components/models/encryption_key_state.py`, singleton table
following the existing settings-table pattern (e.g. `LlmSettingsModel`):

```python
class EncryptionKeyState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key_fingerprint: str  # SHA-256 hex digest of the active ENCRYPTION_KEY
```

Only a fingerprint is stored, never the key itself. Registered in
`backend/components/models/__init__.py` + `__all__` (required for Alembic
autogenerate per AGENTS.md), migration via
`alembic revision --autogenerate -m "add encryption_key_state"`.

### 2. New env var: `ENCRYPTION_KEY_PREVIOUS`

Read via the existing `env_or_file()` helper (so `ENCRYPTION_KEY_PREVIOUS_FILE`
works for Docker secrets too, matching `ENCRYPTION_KEY_FILE`). Only needs to
be set for the one restart that performs the rotation; can be removed from
the environment afterwards.

### 3. New module: `backend/components/security/key_rotation.py`

Keeps migration logic out of `field_encryption.py` (which stays pure
encrypt/decrypt utilities). Exposes one entry point:

```python
def run_key_rotation_if_needed(session_factory, logger) -> None: ...
```

Called from `backend/run.py:create_app()` immediately after
`_run_alembic_migrations(logger)` (the `EncryptionKeyState` table must
already exist).

**Startup logic:**

1. If `ENCRYPTION_KEY` is unset (encryption disabled) → return immediately.
2. Compute `fingerprint = sha256(current_key).hexdigest()`.
3. Load the single `EncryptionKeyState` row (if any):
   - **No row** (fresh install, or upgrading from a version predating this
     feature) → insert a row with the current fingerprint, return. This is
     a one-time baseline; it does not retroactively detect a rotation that
     already happened before this feature existed.
   - **Fingerprint matches** → return (no-op, single indexed row read —
     this is the steady-state cost paid on every normal restart).
   - **Fingerprint differs** → a key rotation is in progress, continue.
4. Read `ENCRYPTION_KEY_PREVIOUS`.
   - **Missing** → log a warning ("ENCRYPTION_KEY changed but
     ENCRYPTION_KEY_PREVIOUS is not set — existing encrypted data will stay
     unreadable until the previous key is supplied for a one-time
     migration"). Do **not** update the stored fingerprint (so the next
     restart re-attempts this check). Return — the app still starts
     normally (existing behavior for undecryptable rows is unchanged: they
     come back as ciphertext, not a crash).
   - **Present** → run the migration (step 4 below). On full completion,
     update `EncryptionKeyState.key_fingerprint` to the new fingerprint and
     log `"Encryption key rotation complete (N records re-encrypted)"`.

### 4. Migration algorithm

Operates on raw SQL over `record.content`, `record.summarize`,
`record.pii_mapping` — deliberately bypassing the SQLModel
`EncryptedString` type decorator. Reading through the ORM would trigger
`field_encryption.decrypt()` using the *new* key automatically, which
fails silently and returns ciphertext-as-is on `InvalidToken` — making
"real legacy plaintext" and "ciphertext under the old key" indistinguishable
at the Python level. Raw SQL avoids that ambiguity entirely.

Batched (500 rows per `OFFSET`/`LIMIT` page, one commit per batch — avoids
one giant transaction on large tables):

```python
def _migrate_value(raw: str | None, old_fernet: Fernet, new_fernet: Fernet) -> str | None:
    """Return new ciphertext to write, or None if the field needs no change."""
    if not raw:
        return None
    try:
        plaintext = old_fernet.decrypt(raw.encode())
    except InvalidToken:
        # Already migrated (decrypts under the new key) or legacy
        # plaintext from before encryption was enabled — leave untouched.
        return None
    return new_fernet.encrypt(plaintext).decode()
```

For each row, compute new values for all three columns; `UPDATE` only rows
where at least one column actually changed.

**Idempotency**: if the process is interrupted after some batches commit,
the fingerprint hasn't been updated yet, so the next startup retries. Rows
already re-encrypted under the new key fail to decrypt with the old key
(`InvalidToken`) and are skipped — no double-encryption, no data loss.

**Legacy plaintext** (rows from before `ENCRYPTION_KEY` was ever set) is
left untouched by the migration, exactly as `decrypt()`'s existing fallback
already tolerates; it gets encrypted the next time the row is written
through the normal ORM path.

### 5. Error handling

- Wrong `ENCRYPTION_KEY_PREVIOUS` (e.g. typo) → every row fails to decrypt
  with the old key → 0 rows migrated, fingerprint **not** updated, warning
  logged ("0 of N rows migrated — ENCRYPTION_KEY_PREVIOUS is likely
  incorrect"). App still starts; next restart retries.
- DB error mid-migration (e.g. connection drop) → already-committed batches
  stay migrated (idempotent), exception is logged, app still starts —
  consistent with `_run_alembic_migrations`'s existing pattern of logging
  migration failures rather than blocking startup.

### 6. Admin status (read-only)

Extend the existing `GET /api/v1/settings/services-health/` response
(`backend/views/settings_api/settings_routes.py:230`) with one more entry,
e.g.:

```json
{"encryption": {"status": "in_sync" | "rotation_pending" | "disabled"}}
```

`rotation_pending` only when the stored fingerprint doesn't match the
active key **and** the last rotation attempt had no `ENCRYPTION_KEY_PREVIOUS`
to work with. No new endpoint — this is one more field on the existing
health object. Frontend: render it alongside the other health rows in
`SystemSettings.tsx`, same pattern as the existing entries. The key value
itself is never exposed.

## Verification (manual — no test framework in this repo)

1. Start with `ENCRYPTION_KEY=A`, create a record with content, confirm the
   DB column is ciphertext.
2. Restart with `ENCRYPTION_KEY=B` (no `_PREVIOUS`) → warning logged, app
   runs, `GET /record/{id}` returns garbled content (unchanged existing
   behavior), `services-health` reports `rotation_pending`.
3. Restart with `ENCRYPTION_KEY=B`, `ENCRYPTION_KEY_PREVIOUS=A` → log shows
   "N re-encrypted", `GET /record/{id}` returns correct plaintext again,
   `services-health` reports `in_sync`.
4. Restart again with the same `B`/`A` → log shows 0 rows migrated
   (fingerprint already matched), no full-table scan performed.
5. Restart with a deliberately wrong `ENCRYPTION_KEY_PREVIOUS` → 0 rows
   migrated, warning logged, data stays garbled, fingerprint not updated so
   the next restart retries.
