# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Primary reference

@AGENTS.md is the detailed developer guide for this repo — dev commands, entrypoints, architecture (two-stage ASR, ROOT_PATH sub-path deployment, settings cache, session store, field encryption), Docker layout, environment variables, gotchas, and Python style rules. Read it before making non-trivial changes; it is kept up to date and this file does not repeat it.

openDox is a medical transcription platform (AGPL-3.0-or-later): record audio → transcribe (Whisper/Parakeet) → optionally sanitize PII → summarize via LLM, organized by medical category. **Not a certified medical device** ("Kein Medizinprodukt") — this disclaimer must stay in the recording dialog and transcript view.

## PII Sanitizer (EntityGuard) pipeline

Not yet documented in AGENTS.md. See `docs/pii.md` for the full flow diagram. Summary:

1. `background_transcription_service.py` runs Whisper on the full audio using the category's `whisper_prompt`, producing `record.content` (real names, encrypted at rest).
2. If the sanitizer is enabled (`sanitizing_service.py`), the text is POSTed to the configured sanitizer endpoint (full URL, e.g. an external EntityGuard instance), which returns `sanitized_text` (names replaced with per-occurrence tokens like `[PERSON_1]`) and preferably a `mapping` dict (`{PERSON_1: "Müller", ...}`) directly.
3. If the backend doesn't return `mapping`, `_extract_mapping()` falls back to a word-level `difflib.SequenceMatcher` diff between original and sanitized text — best-effort, skips (and logs) ambiguous adjacent tokens rather than risk a wrong attribution. Either way the result is stored encrypted in `record.pii_mapping`.
4. The LLM only ever sees `sanitized_text` plus a `PRESERVE_TOKENS_INSTRUCTION`, producing `summary_anonymized`.
5. `reinject()` string-replaces tokens back to real names using `entity_mapping`, producing the final `record.summarize` (real names, encrypted).

Configured via Admin UI → LLM settings → PII-Sanitizer. See `docs/pii.md` for the full response contract.

## Deployment gotcha: Apache reverse proxy + WebSocket

If live transcription drops after 1-2 sentences behind an Apache reverse proxy, `mod_proxy_wstunnel` is likely not loaded — `mod_proxy_http` lets the WS upgrade through but breaks on binary audio frames. Fix: `a2enmod proxy_wstunnel` and ensure the WS `ProxyPass` rule for `/api/v1/records/ws/record` is declared *before* the catch-all `ProxyPass /`. See `bugfix.md` for the full writeup, including a noted `Recorder.tsx` resilience gap (`ws.onclose` is currently a no-op).
