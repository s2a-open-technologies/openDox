# Changelog

All notable changes to openDox are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions are bumped via `python scripts/bump_version.py` (patches/minor/major)
and tagged in git (`--commit` flag), which also moves this file's
`[Unreleased]` section under the new version heading. Pushing the resulting
`vX.Y.Z` tag triggers `.github/workflows/release.yml`, which attaches that
section as the GitHub Release notes.

## [Unreleased]

### Added

- **Mehrsprachige Oberfläche (Deutsch/English)** — komplette UI über
  `i18next`/`react-i18next`; Übersetzungen als JSON unter
  `frontend/src/i18n/locales/<lang>/`, weitere Sprachen brauchen nur einen
  neuen Ordner (siehe AGENTS.md → "i18n"). Ein Test stellt sicher, dass alle
  Sprachen dieselben Schlüssel und Platzhalter haben.
- **Profil-Dialog** (`ProfileModal.tsx`) statt Einzel-Einträgen im Nutzermenü:
  Sprache, Mein Wörterbuch, Meine Kategorien und Design (Hell/Dunkel).
- **UI-Sprache pro Nutzer** — `User.ui_language` (Migration
  `d7a1c3e95b26`), `GET`/`PUT /api/v1/settings/my-language/`, zusätzlich in
  `/auth/me`.
- **Übersetzbare API-Fehler** — häufige Fehlermeldungen des Backends liefern
  jetzt `detail: {code, message, params}` (`api_error()`); das Frontend
  übersetzt sie über `errors.json`.

### Changed

- Nutzermenü: "Profil" und (für Admin/Moderator/Demo-Viewer) "Administration"
  ersetzen die Einträge "Design wechseln", "Meine Kategorien" und "Mein
  Wörterbuch". `MyCategoriesModal`/`MyDictionaryModal` entfallen.
- Zeitstempel in der Aufnahmeliste werden je nach Sprache formatiert
  (ohne Sekunden).
- Hinweistext zum Schwellenwert der Fachbegriff-Korrektur nennt jetzt das
  Feld "Korrektur-Glossar" statt "Whisper-Prompt".
- Fehlerantworten mit `detail` sind bei den umgestellten Fällen ein Objekt
  statt eines Strings (API-Clients, die `detail` als Text lesen, nutzen
  `detail.message`).

## [0.8.2] — 2026-09-29

### Added

- **Auto-Archivierung von Transkriptionen** — admin-konfigurierbar als
  **eigene Card** unter Admin-UI → Audio (zwischen Audio-Download und
  "Fehlgeschlagene Transkriptionen", `AutoArchiveConfig.tsx`): Schalter
  plus **frei wählbare Frist in Tagen** (Input-Feld, ganze Zahl 1–3650
  mit Inline-Fehlerhinweis und gesperrtem Speichern-Button bei
  ungültigem Wert; Server-Validierung auf `PUT /settings/audio-settings/`
  mit 422 als Rückfallebene). Standard 90, ab Werk aus.
  - **Funktionsweise**: Zeitgesteuertes Pendant zum "Archivieren"-Eintrag im
    Hamburger-Menü — der Hintergrunddienst setzt `Record.archived = True`
    für jede Aufnahme, deren Uhrzeit-Timestamp älter als die Frist ist. Die
    Aufnahme verschwindet aus **Aktuell** und taucht im **Archiv**-Tab
    (Datumsgruppierung) wieder auf; Inhalte bleiben unangetastet.
  - **Scheduler**: Neuer Lifespan-Loop in `run.py` (alle 6 h), der
    `auto_archive_service.auto_archive_old_records()` aufruft. Settings
    werden pro Tick neu gelesen — Umschalten/Frist-Änderung greift ohne
    Neustart.
  - **Robustheit**: pro Datensatz eigene DB-Session (ein Fehler blockiert
    den Restlauf nicht, nur Warn-Log), unparsbare Timestamps werden
    übersprungen, bereits archivierte Datensätze bleiben unangetastet —
    manuelles Wiederherstellen bleibt dauerhaft wirksam.
  - **Schema/Daten**: neue DB-Migration `b4d2f8a71c90` (Spalten mit
    Server-Defaults) auf `AudioSettingsModel`; die neuen Felder laufen
    automatisch über das bestehende Settings-Backup/Restore
    (Audio-Sektion) mit.
  - **Tests**: 10 neue Backend-Tests
    (`tests/services/test_auto_archive_service.py` — Parsing, Schwellwerte,
    Fehlerisolierung), 6 neue Frontend-Tests für die eigene
    `AutoArchiveConfig`-Card (Laden, freie Tages-Eingabe + Range-Gate,
    Persist-on-Save, Speicherfehler, readOnly) + aktualisierte
    `AdminModal`-Stub-Erwartung.

### Fixed

- **Admin-UI: "Audio"-Reiter umbenannt** in **"Archivierung"** (Navi-Label +
  Inhalts-Überschrift, Archiv-Icon statt Download-Icon) — der Reiter enthält
  Audio-Download, Auto-Archivierung und fehlgeschlagene Transkriptionen;
  "Audio" war mittlerweile irreführend. Reiter-Struktur/intern
  (`case 'audio'`) unverändert, nur Label/Icon/Überschrift.
- **Archiv-Übersicht: Layout** — Die Tagesliste stand ohne Karte direkt auf
  dem grauen Dashboard-Hintergrund (`bg-muted/30`). Beide Zustände
  (Tagesliste + "Wählen Sie links ein Datum"-Prompt) liegen jetzt auf
  weißem `bg-background` wie TranscriptView, die Tagesliste in einer
  vollbreiten `Card` (Header mit Zurück-Button/Datumslabel/Anzahl auf
  `bg-muted/50`, Zeilen darunter) — gleicher Card-Stil wie
  Recorder/Transkript-Ansicht.
- **Archiv-CI: 4 zeitabhängige Tests repariert** (3 × `Sidebar.test.tsx`,
  1 × `ArchiveDayList.test.tsx`) — rot seit dem Tag nach dem Feature-Commit:
  der `Date.now()`-Spy, den die Tests nutzten, wirkt nicht auf
  `new Date()` in `formatDateLabel()` (`lib/archive.ts`) — die „Heute"/
  „Gestern"-Erwartungen hielten nur am Commit-Tag 2026-09-23. Jetzt frieren
  die Tests die Uhr mit `vi.setSystemTime()` ein (echte Timer — Fake-Timer
  hängen Radix/userEvent-Interaktionen in jsdom auf) plus globaler
  `vi.unstubAllGlobals()`-Reset in `src/test/setup.ts`, damit die
  eingefrorene Uhr nicht in andere Test-Files leakt.

## [0.8.0] — 2026-09-28

### Added

- Personal dictionary: every user gets a private, per-user correction
  glossary ("Mein Wörterbuch", `UserDropdown.tsx` →
  `MyDictionaryModal.tsx`/`PersonalDictionary.tsx`,
  `GET`/`PUT /api/v1/settings/my-dictionary/`) that applies at final
  transcription regardless of which category was selected for the
  recording — merged with that category's glossary
  (`_build_correction_glossary()` in
  `background_transcription_service.py`). Deliberately never exposed to
  admins through any endpoint or schema, unlike personal categories.
- `Categories.glossary`: the term-correction glossary source is now a
  dedicated field, split off from `whisper_prompt`. `whisper_prompt` is
  only ever sent to Whisper as `initial_prompt`, which faster-whisper
  truncates to the last 224 tokens with no length check or warning —
  combining it with an arbitrarily long glossary risked silently dropping
  whichever part landed at the front. `glossary` has no such limit. A
  migration backfills `glossary = whisper_prompt` for existing categories
  so current term-correction behavior is preserved. New
  "Korrektur-Glossar" textarea in `CategorySettings.tsx`, independent of
  the existing "Transkriptions-Hint (Whisper)" field.
- Redis session-store auto-reconnect: when the app process starts while Redis
  is still down (single-container restart race — `depends_on` only orders
  initial compose creation), the in-memory fallback is no longer permanent.
  The services-health check (`/api/v1/settings/services-health/`) and the
  `/api/ready` readiness probe now trigger a live reconnect whenever
  `REDIS_URL` is configured but the active store is in-memory, swapping in a
  fresh `RedisSessionStore` at runtime via a mutable proxy
  (`backend/components/services/session_store.py`, 7 new tests in
  `tests/services/test_session_store_reconnect.py`).
- Voluntary SBOM generation in the Docker publish workflow: CycloneDX JSON
  SBOMs per published image variant (pinned to the exact manifest digest,
  `anchore/sbom-action`), plus `provenance`/`sbom` attestations on the
  build step. Deliberately voluntary — CRA obligations don't apply to
  non-commercial AGPL v3 OSS; the artifacts serve audit/procurement
  evidence instead.
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

- Parakeet GPU image: `onnxruntime-gpu>=1.29.0` in
  `parakeet_server/requirements.gpu.txt` — aarch64 wheels only exist from
  1.29.0, so the arm64 half of the multi-arch build failed with "No matching
  distribution found" while the amd64 half built fine.
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
- **Documentation**: `SECURITY.md` (incl. Art. 32 measures table,
  vulnerability disclosure policy), `docs/data-mapping.md` (DSGVO/Art. 30
  starting point with flowchart), `docs/pii.md`, `docs/CONTRIBUTING.md`,
  audit checklist (`docs/audit-checklist-opendox.md`).
- **Testing**: 19 backend test files (pytest: security, auth/RBAC, OIDC,
  LDAP, services, records API), 31 frontend test files (vitest colocated).
- **Licensing**: full AGPL-3.0-or-later text in `LICENSE`, SPDX headers in
  all source files, REUSE spec compliance (`REUSE.toml`, `reuse lint` green).

[Unreleased]: https://github.com/daemolition/openDox/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/daemolition/openDox/compare/v0.1.0...v0.8.2
[0.8.0]: https://github.com/daemolition/openDox/compare/v0.1.0...v0.8.0
[0.1.0]: https://github.com/daemolition/openDox/releases/tag/v0.1.0