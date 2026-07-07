# Parakeet Left-Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Parakeet's live transcription an admin-configurable amount of
acoustic look-back audio per chunk (`left_context_s`), without duplicating
text in the live transcript shown to the user.

**Architecture:** A new `left_context_s` column on `WhisperSettingsModel`
controls how much extra audio (read from *before* the current chunk's start
offset) gets prepended to the audio sent to Parakeet each cycle.
`record.py`'s live-ASR loop already tracks a byte offset per session
(`local_last_index`) — left-context only changes what's *read* for
transcription, not that offset's advancement. A new word-level dedup
helper (`merge_overlapping_text`) reconciles the model's output, which now
re-says part of the context audio, against the already-emitted live text.

**Tech Stack:** Python 3.12, FastAPI, SQLModel/Alembic, React/TypeScript.
No test framework in this repo (confirmed in AGENTS.md) — verification
steps use standalone scripts and direct DB/API round-trips instead of
pytest.

## Global Constraints

- `left_context_s` applies to Parakeet only (`live_backend == "parakeet"`).
  Whisper's existing `overlap_s` mechanism is untouched.
- Default `0.0` (disabled) — must not change behavior for any existing
  deployment until an admin opts in.
- No changes to `parakeet_server/` — left-context is caller-side only.
- `chunk_length_s` and `left_context_s` stay independent, unbounded knobs
  (matches `chunk_length_s`/`overlap_s` today) — no hard validation, only a
  UI help-text hint recommending `0.5–2s`.
- Design doc: `docs/superpowers/specs/2026-07-07-parakeet-left-context-design.md`
  — refer back to it for the full rationale (already approved).

---

### Task 1: `left_context_s` setting — model, migration, route wiring

**Files:**
- Modify: `backend/components/models/settings_model.py:40-41`
- Create: `alembic/versions/<new_revision>_add_left_context_to_whisper_settings.py`
- Modify: `backend/views/settings_api/settings_routes.py:113-115`

**Interfaces:**
- Produces: `WhisperSettingsModel.left_context_s: float` (default `0.0`),
  readable via `get_settings().left_context_s` (used by Task 3) and
  round-trips through `GET`/`PUT /api/v1/settings/whisper-settings/`
  (used by Task 4's frontend).

- [ ] **Step 1: Add the field to the model**

Edit `backend/components/models/settings_model.py`, right after the
existing `overlap_s` line:

```python
    language: str = Field(default="de")
    chunk_length_s: int = Field(default=3)
    overlap_s: float = Field(default=0.0)
    left_context_s: float = Field(default=0.0)
```

- [ ] **Step 2: Generate the migration**

Run: `cd /home/crizz/python/project_red && python -m alembic revision --autogenerate -m "add left_context_s to whisper settings"`

Expected: a new file `alembic/versions/<hash>_add_left_context_s_to_whisper_settings.py`
is created. Autogenerate in this repo also tends to pick up unrelated
pre-existing type drift (e.g. `categories.whisper_prompt`, `record.pii_mapping`)
— **do not include those in this migration**. Open the generated file and
trim `upgrade()`/`downgrade()` down to only the new column, e.g.:

```python
"""add left_context_s to whisper settings

Revision ID: <hash>
Revises: c562b50913d5
Create Date: <generated>

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '<hash>'
down_revision: Union[str, Sequence[str], None] = 'c562b50913d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'whispersettingsmodel',
        sa.Column('left_context_s', sa.Float(), nullable=False, server_default='0.0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whispersettingsmodel', 'left_context_s')
```

(`server_default='0.0'` matters here — unlike the nullable columns added in
prior migrations this session, `left_context_s` is `nullable=False` on the
model, so existing rows need a default value at migration time or the
`ALTER TABLE ADD COLUMN` will fail against a non-empty table.)

- [ ] **Step 3: Apply and round-trip the migration**

Run: `python -m alembic upgrade head`
Expected: `Running upgrade c562b50913d5 -> <hash>, add left_context_s to whisper settings`

Run:
```bash
python -m alembic downgrade -1 && python -m alembic upgrade head
```
Expected: both steps complete with no errors (proves `downgrade()` is
correct, not just `upgrade()`).

- [ ] **Step 4: Wire the field into the settings PUT route**

Edit `backend/views/settings_api/settings_routes.py`, right after the
existing `settings.overlap_s = settings_in.overlap_s` line:

```python
    settings.language = settings_in.language
    settings.chunk_length_s = settings_in.chunk_length_s
    settings.overlap_s = settings_in.overlap_s
    settings.left_context_s = settings_in.left_context_s
```

- [ ] **Step 5: Verify persistence end-to-end**

Run:
```bash
python3 -c "
from backend.components.sql.sql_engine import get_session_factory
from backend.components.models.settings_model import WhisperSettingsModel
from sqlmodel import select

db = get_session_factory()()
settings = db.exec(select(WhisperSettingsModel)).first()
if not settings:
    settings = WhisperSettingsModel()
settings.left_context_s = 1.5
db.add(settings)
db.commit()

db2 = get_session_factory()()
reloaded = db2.exec(select(WhisperSettingsModel)).first()
assert reloaded.left_context_s == 1.5, reloaded.left_context_s
print('OK: left_context_s persisted as', reloaded.left_context_s)

# reset to default so later manual testing starts from a clean state
reloaded.left_context_s = 0.0
db2.add(reloaded)
db2.commit()
print('reset to 0.0')
"
```
Expected: prints `OK: left_context_s persisted as 1.5` then `reset to 0.0`,
no `AssertionError`.

- [ ] **Step 6: Lint and commit**

Run: `ruff check backend/components/models/settings_model.py backend/views/settings_api/settings_routes.py --select E,F,I`
Expected: `All checks passed!`

```bash
git add backend/components/models/settings_model.py \
        backend/views/settings_api/settings_routes.py \
        alembic/versions/*_add_left_context_s_to_whisper_settings.py
git commit -m "feat: add left_context_s setting for Parakeet live ASR"
```

---

### Task 2: `merge_overlapping_text()` dedup helper

**Files:**
- Create: `backend/components/modules/text_dedup.py`

**Interfaces:**
- Produces: `merge_overlapping_text(existing: str, new_text: str) -> str`
  (used by Task 3).

- [ ] **Step 1: Write the module with an inline self-test**

Create `backend/components/modules/text_dedup.py`:

```python
"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""


def merge_overlapping_text(existing: str, new_text: str) -> str:
    """Append new_text to existing, trimming any leading words in new_text
    that duplicate the tail of existing (word-level, case-insensitive).

    Used to reconcile a re-transcribed left-context region: new_text is a
    model's output for [left-context audio + new chunk], and its leading
    words are expected to re-say some of what's already in existing.

    Args:
        existing: Text already emitted (e.g. the live transcript so far).
        new_text: The model's latest output, which may re-say the tail of
            existing before its genuinely new content.

    Returns:
        existing with only the non-overlapping suffix of new_text appended.
        When no overlap is found, behaves exactly like
        `(existing + " " + new_text).strip()`.
    """
    if not existing:
        return new_text.strip()
    if not new_text:
        return existing

    existing_words = existing.split()
    new_words = new_text.split()
    max_k = min(len(existing_words), len(new_words))

    overlap = 0
    for k in range(max_k, 0, -1):
        existing_tail = [w.lower() for w in existing_words[-k:]]
        new_head = [w.lower() for w in new_words[:k]]
        if existing_tail == new_head:
            overlap = k
            break

    if overlap == 0:
        return (existing + " " + new_text).strip()

    remaining = " ".join(new_words[overlap:])
    if not remaining:
        return existing
    return (existing + " " + remaining).strip()


if __name__ == "__main__":
    cases = [
        # (existing, new_text, expected)
        ("", "hello world", "hello world"),
        ("hello world", "", "hello world"),
        ("Der Patient hat", "hat Kopfschmerzen", "Der Patient hat Kopfschmerzen"),
        ("Der Patient hat Kopfschmerzen", "Kopfschmerzen seit gestern",
         "Der Patient hat Kopfschmerzen seit gestern"),
        ("Der Patient", "Fieber und Husten", "Der Patient Fieber und Husten"),
        ("Der Patient HAT", "hat Kopfschmerzen", "Der Patient HAT Kopfschmerzen"),
        ("a b c", "a b c", "a b c"),
    ]
    failures = 0
    for existing, new_text, expected in cases:
        result = merge_overlapping_text(existing, new_text)
        status = "OK" if result == expected else "FAIL"
        if status == "FAIL":
            failures += 1
        print(f"[{status}] merge_overlapping_text({existing!r}, {new_text!r}) "
              f"= {result!r} (expected {expected!r})")
    if failures:
        raise SystemExit(f"{failures} of {len(cases)} cases failed")
    print(f"All {len(cases)} cases passed")
```

- [ ] **Step 2: Run the self-test and verify it passes**

Run: `python -m backend.components.modules.text_dedup`
Expected: 7 lines each starting `[OK]`, then `All 7 cases passed`, exit
code 0.

- [ ] **Step 3: Lint and commit**

Run: `ruff check backend/components/modules/text_dedup.py --select E,F,I`
Expected: `All checks passed!`

```bash
git add backend/components/modules/text_dedup.py
git commit -m "feat: add merge_overlapping_text dedup helper"
```

---

### Task 3: Wire left-context + dedup into the live-ASR loop

**Files:**
- Modify: `backend/views/record_api/record.py:18-30` (imports),
  `backend/views/record_api/record.py:336-403` (live-ASR block)

**Interfaces:**
- Consumes: `settings.left_context_s: float` (Task 1),
  `merge_overlapping_text(existing: str, new_text: str) -> str` (Task 2).

- [ ] **Step 1: Import the dedup helper**

In `backend/views/record_api/record.py`, add to the "Custom" import group
(near the other `backend.components...` imports, e.g. next to the
`OllamaModel` import around line 33):

```python
from backend.components.modules.text_dedup import merge_overlapping_text
```

- [ ] **Step 2: Extend the audio slice with left-context**

Replace the live-ASR block currently at
`backend/views/record_api/record.py:336-404`:

```python
                # Live ASR
                try:
                    backend = get_live_asr()

                    # chunk_length_s * 16000 samples/s * 4 bytes/sample (float32)
                    bytes_per_chunk = 3 * 16000 * 4  # default 3s chunks
                    bytes_per_overlap = 0
                    whisper_params = None
                    try:
                        from backend.components.services.settings_service import (
                            get_settings,
                            get_whisper_params,
                        )

                        settings = get_settings()
                        bytes_per_chunk = settings.chunk_length_s * 16000 * 4
                        bytes_per_overlap = int(settings.overlap_s * 16000 * 4)
                        if settings.live_backend == "parakeet":
                            bytes_per_overlap = 0
                        whisper_params = get_whisper_params(live=True)
                    except Exception:
                        pass

                    new_data_len = local_audio_size - local_last_index

                    if new_data_len >= bytes_per_chunk:
                        start = local_last_index
                        with open(local_audio_path, "rb") as _f:
                            _f.seek(start)
                            audio_slice = _f.read(bytes_per_chunk)
                        new_index = start + bytes_per_chunk - bytes_per_overlap

                        # Normalize quiet audio so Whisper doesn't hallucinate
                        # filler phrases instead of returning silence.
                        _pcm = np.frombuffer(audio_slice, dtype=np.float32)
                        audio_slice = normalize_quiet_pcm(_pcm).tobytes()

                        # Whisper tends to repeat text from the prompt, causing
                        # duplication in the live transcript. Skip the prompt.
                        _ = None  # live_prompt intentionally unused

                        logger.info(
                            "[ASR] chunk %.1fs | overlap %.1fs | params=%s",
                            len(audio_slice) / (16000 * 4),
                            bytes_per_overlap / (16000 * 4),
                            whisper_params,
                        )
                        # Transcribe in background thread (non-blocking)
                        result_text = await asyncio.to_thread(
                            backend.transcribe,
                            audio=audio_slice,
                            language="de",
                            prompt=None,
                            params=whisper_params,
                        )

                        # Always advance the index — even on empty result — so the
                        # same audio slice is never re-transcribed in the next loop.
                        local_last_index = new_index

                        if result_text:
                            local_live_text = (
                                local_live_text + " " + result_text
                            ).strip()
                            # Persist to Redis only after transcription (~every 3s)
                            session_store.set_live_state(
                                session_id, new_index, local_live_text
                            )
```

with:

```python
                # Live ASR
                try:
                    backend = get_live_asr()

                    # chunk_length_s * 16000 samples/s * 4 bytes/sample (float32)
                    bytes_per_chunk = 3 * 16000 * 4  # default 3s chunks
                    bytes_per_overlap = 0
                    bytes_per_left_context = 0
                    whisper_params = None
                    try:
                        from backend.components.services.settings_service import (
                            get_settings,
                            get_whisper_params,
                        )

                        settings = get_settings()
                        bytes_per_chunk = settings.chunk_length_s * 16000 * 4
                        bytes_per_overlap = int(settings.overlap_s * 16000 * 4)
                        if settings.live_backend == "parakeet":
                            bytes_per_overlap = 0
                            bytes_per_left_context = int(
                                settings.left_context_s * 16000 * 4
                            )
                        whisper_params = get_whisper_params(live=True)
                    except Exception:
                        pass

                    new_data_len = local_audio_size - local_last_index

                    if new_data_len >= bytes_per_chunk:
                        start = local_last_index
                        # Read some extra audio from before `start` as pure
                        # acoustic context for Parakeet — this does NOT move
                        # `start`/`new_index`, it's read-only look-back.
                        read_start = max(0, start - bytes_per_left_context)
                        with open(local_audio_path, "rb") as _f:
                            _f.seek(read_start)
                            audio_slice = _f.read((start - read_start) + bytes_per_chunk)
                        new_index = start + bytes_per_chunk - bytes_per_overlap

                        # Normalize quiet audio so Whisper doesn't hallucinate
                        # filler phrases instead of returning silence.
                        _pcm = np.frombuffer(audio_slice, dtype=np.float32)
                        audio_slice = normalize_quiet_pcm(_pcm).tobytes()

                        # Whisper tends to repeat text from the prompt, causing
                        # duplication in the live transcript. Skip the prompt.
                        _ = None  # live_prompt intentionally unused

                        logger.info(
                            "[ASR] chunk %.1fs | overlap %.1fs | left_context %.1fs | params=%s",
                            len(audio_slice) / (16000 * 4),
                            bytes_per_overlap / (16000 * 4),
                            bytes_per_left_context / (16000 * 4),
                            whisper_params,
                        )
                        # Transcribe in background thread (non-blocking)
                        result_text = await asyncio.to_thread(
                            backend.transcribe,
                            audio=audio_slice,
                            language="de",
                            prompt=None,
                            params=whisper_params,
                        )

                        # Always advance the index — even on empty result — so the
                        # same audio slice is never re-transcribed in the next loop.
                        local_last_index = new_index

                        if result_text:
                            local_live_text = merge_overlapping_text(
                                local_live_text, result_text
                            )
                            # Persist to Redis only after transcription (~every 3s)
                            session_store.set_live_state(
                                session_id, new_index, local_live_text
                            )
```

- [ ] **Step 3: Verify behavior is unchanged when left_context_s = 0**

`left_context_s` defaults to `0.0` (Task 1), so `bytes_per_left_context ==
0`, `read_start == start`, and `merge_overlapping_text` always takes its
`overlap == 0` branch — which returns `(existing + " " + new_text).strip()`,
byte-for-byte identical to the code being replaced. Confirm this by reading
the diff back and checking that when `bytes_per_left_context == 0`:
`(start - read_start) + bytes_per_chunk == bytes_per_chunk` (i.e. the read
length is unchanged from before this task).

Run:
```bash
python3 -c "
start = 96000
bytes_per_left_context = 0
read_start = max(0, start - bytes_per_left_context)
read_len = (start - read_start) + 48000
assert read_start == start
assert read_len == 48000
print('OK: left_context_s=0 reproduces today\'s read window exactly')
"
```
Expected: `OK: left_context_s=0 reproduces today's read window exactly`

- [ ] **Step 4: Lint and import-check**

Run: `ruff check backend/views/record_api/record.py --select E,F,I`
Expected: `All checks passed!` (pre-existing unrelated `E501` lines in this
file, if any, are not something this task introduces — only check the
lines this task touched if `ruff` reports anything).

Run: `python3 -c "from backend.views.record_api import record; print('import OK')"`
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add backend/views/record_api/record.py
git commit -m "feat: send left-context audio to Parakeet live ASR with dedup"
```

---

### Task 4: `left_context_s` field in the Whisper settings UI

**Files:**
- Modify: `frontend/src/components/settings/WhisperConfig.tsx:41-64` (interface),
  `:66-90` (initial state), `:92-116` (fetched state), `:238-257` (form fields)

**Interfaces:**
- Consumes: `left_context_s` from `GET /api/v1/settings/whisper-settings/`
  response, saved via `PUT` (both wired in Task 1).

- [ ] **Step 1: Add the field to the `WhisperSettings` interface**

In `frontend/src/components/settings/WhisperConfig.tsx`, right after
`overlap_s: number;` (line 52):

```typescript
    chunk_length_s: number;
    overlap_s: number;
    left_context_s: number;
```

- [ ] **Step 2: Add it to the initial state**

Right after `overlap_s: 0,` (line 79):

```typescript
        chunk_length_s: 3,
        overlap_s: 0,
        left_context_s: 0,
```

- [ ] **Step 3: Add it to the fetched-state mapping**

Right after `overlap_s: data.overlap_s ?? 0,` (line 107):

```typescript
                    chunk_length_s: data.chunk_length_s ?? 3,
                    overlap_s: data.overlap_s ?? 0,
                    left_context_s: data.left_context_s ?? 0,
```

- [ ] **Step 4: Add the form field**

Replace the chunk/overlap grid block (currently lines 238-257):

```tsx
                                    <div className={`grid gap-4 ${config.live_backend === 'parakeet' ? 'grid-cols-1' : 'grid-cols-2'}`}>
                                        <div className="space-y-2">
                                            <Label>Chunk-Länge (Sek.)</Label>
                                            <Input
                                                type="number" min={1} max={10}
                                                value={config.chunk_length_s}
                                                onChange={(e) => updateField('chunk_length_s', parseInt(e.target.value) || 3)}
                                            />
                                        </div>
                                        {config.live_backend !== 'parakeet' && (
                                            <div className="space-y-2">
                                                <Label>Überlappung (Sek.)</Label>
                                                <Input
                                                    type="number" min={0} max={2} step={0.5}
                                                    value={config.overlap_s}
                                                    onChange={(e) => updateField('overlap_s', parseFloat(e.target.value) || 0)}
                                                />
                                            </div>
                                        )}
                                    </div>
```

with:

```tsx
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Chunk-Länge (Sek.)</Label>
                                            <Input
                                                type="number" min={1} max={10}
                                                value={config.chunk_length_s}
                                                onChange={(e) => updateField('chunk_length_s', parseInt(e.target.value) || 3)}
                                            />
                                        </div>
                                        {config.live_backend !== 'parakeet' && (
                                            <div className="space-y-2">
                                                <Label>Überlappung (Sek.)</Label>
                                                <Input
                                                    type="number" min={0} max={2} step={0.5}
                                                    value={config.overlap_s}
                                                    onChange={(e) => updateField('overlap_s', parseFloat(e.target.value) || 0)}
                                                />
                                            </div>
                                        )}
                                        {config.live_backend === 'parakeet' && (
                                            <div className="space-y-2">
                                                <Label>Left-Context (Sek.)</Label>
                                                <Input
                                                    type="number" min={0} max={5} step={0.5}
                                                    value={config.left_context_s}
                                                    onChange={(e) => updateField('left_context_s', parseFloat(e.target.value) || 0)}
                                                />
                                                <p className="text-xs text-muted-foreground">
                                                    Akustischer Vorlauf pro Chunk, empfohlen: 0.5–2s. Deutlich mehr als die Chunk-Länge erhöht Latenz und macht die Deduplizierung unzuverlässiger, ohne die Genauigkeit proportional zu verbessern.
                                                </p>
                                            </div>
                                        )}
                                    </div>
```

(the `grid-cols-1 sm:grid-cols-2` change also fixes this block to follow
the mobile-responsive grid pattern documented in `AGENTS.md`'s Frontend
Conventions — it was already inconsistent with that convention before this
task, and now both branches populate 2 fields so the old
backend-conditional grid-cols made even less sense.)

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output (no errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/WhisperConfig.tsx
git commit -m "feat: add left_context_s field to Whisper settings UI"
```

---

### Task 5: Document the setting in AGENTS.md

**Files:**
- Modify: `AGENTS.md` (Two-Stage ASR section)

**Interfaces:** None (docs only).

- [ ] **Step 1: Add a bullet to the Two-Stage ASR section**

In `AGENTS.md`, under the existing `### Two-Stage ASR` section (near the
`chunk_correction_service.py` bullet), add:

```markdown
- `left_context_s` (Parakeet only, default `0.0`): extra acoustic look-back
  audio read from before each chunk's start and sent alongside it, purely
  as model context — `record.py`'s live-ASR loop trims the re-said portion
  of the model's output via `merge_overlapping_text()` (word-level dedup,
  `backend/components/modules/text_dedup.py`) before appending to the live
  transcript. `chunk_length_s`/`left_context_s` are independent; a
  `left_context_s` much larger than `chunk_length_s` multiplies the audio
  re-transcribed per cycle without a proportional accuracy gain (see
  `docs/superpowers/specs/2026-07-07-parakeet-left-context-design.md`).
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: document left_context_s in AGENTS.md"
```

---

### Task 6: Manual end-to-end smoke test

**Files:** None (verification only).

- [ ] **Step 1: Start the stack**

Run: `python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000` and,
separately, `cd frontend && npm run dev`. Ensure a Parakeet backend is
reachable (`PARAKEET_API_ENDPOINT` or the DB `live_api_endpoint` setting).

- [ ] **Step 2: Baseline with left_context_s = 0**

In Admin → Dienste → Whisper/ASR → Live tab, set backend to Parakeet,
leave "Left-Context (Sek.)" at `0`. Start a recording, speak a few
sentences, stop. Note the live transcript text exactly.

- [ ] **Step 3: Enable left-context and compare**

Set "Left-Context (Sek.)" to `1.0`, save. Start a new recording, speak the
same sentences again, stop.

Expected: no obviously duplicated phrases at chunk boundaries in the live
transcript (e.g. no "...Kopfschmerzen Kopfschmerzen seit..." artifacts).
Backend log lines (`[ASR] chunk ... | left_context 1.0s | ...`) confirm the
configured value is being applied.

- [ ] **Step 4: Reset to default**

Set "Left-Context (Sek.)" back to `0` in the admin UI (or leave at whatever
value the user prefers) and save, so the deployment isn't left mid-test.
