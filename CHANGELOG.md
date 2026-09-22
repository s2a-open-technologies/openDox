# Changelog

All notable changes to openDox are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions are bumped via `python scripts/bump_version.py` (patches/minor/major)
and tagged in git (`--commit` flag).

## [Unreleased]

### Added

- Rate-Limiting for the `/login` endpoint (sliding window, 5 requests/60s per
  client IP, HTTP 429 on exceed) with 10 pytest tests
  (`backend/components/services/rate_limiter.py`,
  `tests/auth/test_rate_limiter.py`).
- Frontend test coverage expanded to 31 test files (209 tests passing),
  including `ResizeObserver` global mock and fixed icon selectors
  (`lucide-ellipsis`).
- Governance files: `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, CI/CD pipeline
  (GitHub Actions), Dependabot configuration, and issue/PR templates.

### Fixed

- AdminModal tab-switch remount bug: React reused component state between
  structurally identical tabs, leaving sub-tabs inactive (`key` props added).
- TranscriptView: `aria-label` on the icon-only summary copy button
  (accessibility).

## [0.1.0] — 2026-09-22 (retroactive tag on current `master`)

First documented snapshot. openDox is a medical transcription platform:
record audio → transcribe (Whisper/Parakeet two-stage ASR) → optionally
sanitize PII (EntityGuard) → summarize via LLM, organized by medical
category. AGPL-3.0-or-later; not a certified medical device.

### Added (highlights since project start)

- **Two-stage ASR**: Parakeet (onnx-asr, VAD-segmented WebSocket streaming,
  Silero VAD) for live transcription; Whisper (faster-whisper) for final
  high-quality re-transcription. Standalone servers for both
  (`parakeet_server/`, `whisper_server/`), CPU/GPU Docker variants with
  process-wide concurrency caps
  (`PARAKEET_MAX_CONCURRENT_DECODES`, `WHISPER_MAX_CONCURRENT_TRANSCRIPTIONS`).
- **Authentication**: local DB (bcrypt), LDAP (group-based role mapping,
  AD-compatible, filter-injection-safe, RFC-4513 guard), OIDC/SSO
  (Authorization Code Flow with discovery, group→role mapping,
  auto-provisioning). Per-login role re-sync.
- **RBAC**: roles `admin`, `moderator`, `demo_viewer`, `user`, enforced via
  FastAPI dependencies.
- **Field encryption**: Fernet-based `EncryptedString` column type for
  patient data (`record.content`, `summarize`, `pii_mapping`, `title`),
  settings secrets, plus binary-safe encryption for audio in S3-compatible
  storage.
- **Automatic encryption-key rotation**: `EncryptionKeyState` fingerprint
  table, batched re-encryption at startup, resumable; surfaced in
  services-health; `docker-swarm.rotation.yml` overlay for live rotation.
- **PII sanitizer integration (EntityGuard)**: token-based pseudonymization
  with mapping fallback via `difflib` word-level diff, fail-closed behavior,
  token re-injection into final summaries.
- **Audio download (S3-compatible)**: ffmpeg encode (mp3/ogg/flac/wav),
  client-side encryption, stored via boto3 (Garage bundled as default);
  served via streaming download endpoint. Failed-transcription audio
  retention (`chunks/failed/`) with admin retry and automatic S3 archival
  after `FAILED_AUDIO_RETENTION_DAYS`.
- **LLM summarization**: per-category system prompts and Whisper
  `initial_prompt` vocabulary hints, per-category LLM backend override,
  anti-placeholder-hallucination instruction enforced in code, LLM sampling
  parameters (temperature, max tokens, thinking control).
- **Session store**: Redis (production) with in-memory fallback; stale
  session cleanup, startup crash recovery for PCM/WAV scratch files.
- **Settings**: admin UI (Whisper/ASR, LLM, LDAP, OIDC, categories,
  languages, terminology), JSON backup/restore, services-health endpoint,
  caching with invalidation.
- **Deployment**: Docker Compose (dev/demo, port 20000), Docker Swarm
  production stack with secrets, Garage object storage with idempotent
  init container, ROOT_PATH sub-path deployment support, version bump
  tooling (`scripts/bump_version.py`), license-check tooling
  (`scripts/check_licenses.py`, `THIRD_PARTY_NOTICES.md` generation).
- **Documentation**: `docs/SECURITY.md` (incl. Art. 32 measures table,
  vulnerability disclosure policy), `docs/data-mapping.md` (DSGVO/Art. 30
  starting point with flowchart), `docs/pii.md`, `docs/CONTRIBUTING.md`,
  audit checklist (`docs/audit-checklist-opendox.md`).
- **Testing**: 19 backend test files (pytest: security, auth/RBAC, OIDC,
  LDAP, services, records API), 31 frontend test files (vitest colocated).
- **Licensing**: full AGPL-3.0-or-later text in `LICENSE`, SPDX headers in
  all source files, REUSE spec compliance (`REUSE.toml`, `reuse lint` green).

[Unreleased]: https://github.com/daemolition/openDox/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/daemolition/openDox/releases/tag/v0.1.0