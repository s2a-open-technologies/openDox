# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Primary reference

@AGENTS.md is the detailed developer guide for this repo — dev commands, entrypoints, architecture (two-stage ASR, PII sanitizer pipeline, app versioning, ROOT_PATH sub-path deployment, settings cache, session store, field encryption), Docker layout, environment variables, gotchas, and Python/frontend style rules. Read it before making non-trivial changes; it is kept up to date and this file does not repeat it.

openDox is a medical transcription platform (AGPL-3.0-or-later): record audio → transcribe (Whisper/Parakeet) → optionally sanitize PII → summarize via LLM, organized by medical category. **Not a certified medical device** ("Kein Medizinprodukt") — this disclaimer must stay in the recording dialog and transcript view.
