# Parakeet left-context for live transcription

## Problem

Live transcription splits recorded audio into fixed-length chunks
(`chunk_length_s`) and transcribes each chunk independently via
`get_live_asr().transcribe(...)`. For Whisper, chunks can overlap
(`overlap_s`) — the tail of one chunk is re-read at the start of the next,
giving the model some acoustic lead-in, and the re-transcribed overlap
region is cleaned up by the batch LLM correction step
(`chunk_correction_service.py`).

Parakeet gets none of this: `record.py` forces `bytes_per_overlap = 0`
whenever `live_backend == "parakeet"`, and Parakeet's live text is sent to
the frontend directly with no LLM correction pass (per AGENTS.md, Parakeet
already outputs clean punctuation). So every Parakeet chunk starts "cold" —
no acoustic context from what came immediately before — which can hurt
accuracy for words that land right at a chunk boundary.

The `onnx-asr` library (which wraps the Parakeet ONNX model) has no native
streaming/context parameter — `recognize()` only takes a whole waveform and
returns text for all of it (confirmed against the library's source:
`load_model()` returns a `TextResultsAsrAdapter`, and `recognize()`'s only
audio-shaping options are `sample_rate`/`channel`). So "left-context" has to
be built on our side, not toggled on in the library.

## Goal

Give Parakeet's live transcription some acoustic look-back audio per chunk,
configurable per deployment, without duplicating text in the live
transcript shown to the user.

## Non-goals

- Whisper is out of scope — it already has `overlap_s` plus an LLM
  correction pass that absorbs the duplication; this feature targets the
  gap that's specific to Parakeet (which has neither).
- No changes to `parakeet_server` itself. The server is a stateless
  OpenAI-compatible endpoint that transcribes whatever audio it's given;
  left-context is purely a matter of what audio `record.py` sends it.
- No word-level timestamp adoption in this iteration (see "Alternatives
  considered").

## Design

### 1. Configuration

Add `left_context_s: float = Field(default=0.0)` to `WhisperSettingsModel`
(`backend/components/models/settings_model.py`), next to `chunk_length_s`
and `overlap_s`. `0.0` (disabled) is the default — this is an opt-in tuning
knob, not a behavior change for existing deployments until an admin sets it.

`frontend/src/components/settings/WhisperConfig.tsx`: add a `left_context_s`
number input to the Live tab, shown only when
`config.live_backend === 'parakeet'` — the mirror image of the existing
`overlap_s` field, which is only shown when `config.live_backend !==
'parakeet'` (line ~247 today). Same styling/pattern as the existing
`chunk_length_s`/`overlap_s` inputs. Add a help-text hint recommending
`0.5–2s` — a much larger value than the chunk length multiplies the audio
re-transcribed per cycle (see "Tuning guidance" below) without a
proportional accuracy benefit, but it isn't enforced; the field stays
otherwise unbounded, matching `chunk_length_s`/`overlap_s` today.

Needs an Alembic migration (`alembic revision --autogenerate`) for the new
column, same pattern as recent single-column additions in this repo.

### 2. Extending the audio slice sent to Parakeet

In `record.py`'s live-ASR loop (where `bytes_per_chunk`/`bytes_per_overlap`
are computed today, ~line 340-366):

```python
bytes_per_left_context = 0
if settings.live_backend == "parakeet":
    bytes_per_left_context = int(settings.left_context_s * 16000 * 4)

read_start = max(0, local_last_index - bytes_per_left_context)
with open(local_audio_path, "rb") as _f:
    _f.seek(read_start)
    audio_slice = _f.read(bytes_per_left_context + bytes_per_chunk)
```

`local_last_index` (where the *next* chunk will start) still advances by
exactly `bytes_per_chunk` as it does today — left-context is purely extra
look-back audio read in addition to the normal chunk, not audio that gets
"consumed" or re-emitted as its own chunk later. On the first chunk of a
session, `local_last_index == 0`, so `read_start` clamps to `0` and the
call degrades to today's behavior (no context available yet) — no special
first-chunk handling needed.

`backend.transcribe(audio=audio_slice, ...)` is called with this extended
slice instead of the bare chunk. Everything downstream of that call
(normalization, logging) stays the same.

### 3. Text dedup

New helper, `backend/components/modules/text_dedup.py`:

```python
def merge_overlapping_text(existing: str, new_text: str) -> str:
    """Append new_text to existing, trimming any leading words that
    duplicate the tail of existing (word-level, case-insensitive match).

    Used to reconcile a re-transcribed left-context region: `new_text` is
    the model's output for [left-context audio + new chunk], and its
    leading words are expected to re-say some of what's already in
    `existing`. Returns `existing` with only the non-overlapping suffix of
    `new_text` appended.
    """
```

Algorithm: word-tokenize both strings. Find the longest `k` such that the
last `k` words of `existing` case-insensitively match the first `k` words
of `new_text` (try `k` from `min(len(existing_words), len(new_words))` down
to `0`). Append `new_text`'s words from index `k` onward. `k == 0` (no
overlap found) means append the whole thing — this is exactly today's
behavior, so a session with `left_context_s == 0` (no context audio sent)
is unaffected: `new_text` never contains re-said words in the first place,
so the matcher naturally finds `k == 0`.

Call site (`record.py`, where `local_live_text` is currently built via
straight concatenation for the Parakeet path): route through
`merge_overlapping_text(local_live_text, result_text)` instead of
`local_live_text + " " + result_text`.

## Data flow

```text
disk PCM file
  │  read [last_index - left_context_bytes, last_index + chunk_bytes)
  ▼
audio_slice (context + new chunk)
  │  backend.transcribe(...)  → parakeet_server /v1/audio/transcriptions
  ▼
result_text (re-says some of the context, then the new part)
  │  merge_overlapping_text(local_live_text, result_text)
  ▼
local_live_text (context duplication trimmed)  → sent to frontend
```

## Tuning guidance

`left_context_s` and `chunk_length_s` are independent settings — nothing
stops an admin from setting, say, `chunk_length_s=2` with
`left_context_s=10`. That combination works mechanically but is a bad
trade: every cycle re-sends `left_context_s + chunk_length_s` seconds of
audio (12s here) to transcribe just `chunk_length_s` seconds of *new*
audio, so Parakeet (CPU-bound per AGENTS.md) does far more work per cycle
than the chunk interval accounts for, risking the live transcript falling
behind real time. It also makes the word-overlap dedup *less* reliable, not
more: a larger context window gives the model more room to re-transcribe
the already-emitted region with slightly different wording, which is
exactly what the longest-common-word-overlap match in `merge_overlapping_text`
depends on staying stable. The UI help text should nudge toward `0.5–2s`
(see "Configuration" above) but this isn't enforced in code.

`last_index` itself never moves backward — it advances by `bytes_per_chunk`
exactly as today, so left-context can't cause chunks to be skipped or
double-consumed.

## Error handling

- `left_context_s <= 0` (default): `bytes_per_left_context == 0`,
  `read_start == local_last_index`, identical to current behavior.
- `left_context_s` larger than the audio written so far: clamped to `0` via
  `max(0, ...)`, same as the first-chunk case.
- Dedup finds no overlap (`k == 0`): whole `result_text` is appended, same
  as today.
- Dedup matches "too much" (e.g. legitimately repeated words at the
  boundary, like someone saying "the the"): worst case is a dropped
  duplicate word that was actually intended twice — a minor transcription
  quality edge case, not a crash risk, and acceptable for a live-preview
  transcript (the final Whisper pass, unaffected by this change, is what
  gets encrypted and stored).

## Testing

No automated test framework in this repo. Verify via:
1. A standalone script exercising `merge_overlapping_text()` directly with
   representative before/after string pairs (full overlap, partial
   overlap, no overlap, empty inputs).
2. Manual live-recording smoke test with Parakeet selected and
   `left_context_s` set to e.g. `1.0`: confirm the live transcript doesn't
   show obviously duplicated phrases at chunk boundaries, and confirm
   `left_context_s = 0` reproduces today's output byte-for-byte (same
   `local_live_text` as before this change).

## Alternatives considered

**Word-level timestamps** (`TimestampedResultsAsrAdapter`, confirmed to
exist in `onnx-asr`'s source): would let us hard-cut words by time instead
of guessing via text overlap — more precise, no risk of the "too much
overlap" edge case above. Rejected for this iteration: requires switching
the loaded model's adapter type, unverified compatibility with the pinned
`onnx-asr>=0.11.0` + `nemo-parakeet-tdt-0.6b-v3` combination, and unknown
performance impact of `need_logprobs="yes"`. Worth revisiting if the
text-overlap heuristic proves unreliable in practice.
