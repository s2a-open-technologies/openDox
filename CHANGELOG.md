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

## [0.10.5] — 2026-10-21

### Added

- `docs/asr-vergleich.md`: measured comparison of Whisper large-v3 and large-v3-turbo (int8, int8_float16, float16), Parakeet TDT 0.6B v3 (FP32/int8, GPU/CPU) and the term correction on synthetic dictations, with a recommendation and the limits of the measurement.

## [0.10.4] — 2026-10-20

### Security

- Recordings are now private to their owner, also towards admins. Previously the `admin` role could read, download, change and delete any user's recordings through the API (`GET /record/{id}`, `/record/{id}/audio`, `/list-records/{user_id}`, …) and attach to another user's recording WebSocket; the web UI never offered this. Retrying failed transcriptions stays admin-only and shows no transcript content.

### Added

- User manual (`docs/handbuch/benutzer/`) with a build script (`scripts/build_handbuch.sh`, Pandoc → DOCX/PDF/XWiki). The PDF is attached to every GitHub Release.
- Dictionaries for the medical term correction: named term lists, typed in or uploaded as `.txt`/`.csv` (one term per line, commas inside a term kept — e.g. the ICD catalog), and attached to categories. Admins/moderators manage global ones (Administration → Wörterbücher), every user their own (Profil → Meine Wörterbücher, private, also towards admins). Term correction is now fast with catalog-sized lists (`rapidfuzz.process.extractOne` instead of a per-term loop).
- Parakeet CPU image (`PARAKEET_DEVICE=cpu`, `cpu-*` tags) uses the int8-quantized model (~0.7 GB instead of ~2.5 GB, faster on CPU). Controlled by `PARAKEET_QUANTIZATION`; the GPU image stays on FP32.

### Changed

- The free-text fields "Korrektur-Glossar" (per category) and "Mein Wörterbuch" (per user) are replaced by dictionaries; the migration converts them. A dictionary only takes effect in the categories it is attached to: a personal dictionary no longer applies to every recording automatically, only in the user's own categories (it is attached to all existing ones during the migration).

### Removed

- The seed categories Kardiologie, Orthopädie and Gynäkologie, also from existing installations; recordings using them move to "Allgemein".
- `GET`/`PUT /api/v1/settings/my-dictionary/` (replaced by `/api/v1/settings/dictionaries/`).

### Fixed

- "Neue Aufnahme" from the transcript view and the upload dialog now preselect "Allgemein" instead of no category.
- Term correction no longer rewrites correct words. It compared only the Kölner Phonetik codes, which drop vowels, so error-free text was "corrected" with unrelated terms (measured: "Notaufnahme" → "Metformin", "Indikation" → "Appendektomie"; 16 wrong replacements in a clean dictation with just 27 terms). A replacement now also needs a similar spelling, a similar length and a matching word count, and correctly spelled terms stay untouched including inflected forms. On the benchmark dictations the correction now lowers the word error rate by 2–3 points for every ASR model with zero wrong replacements, instead of leaving it unchanged.
- A failed processing (e.g. the LLM step timing out) kept showing "Fehler" in the transcript view forever, even after the summary was regenerated successfully. Regenerating now resolves the failed task; the view shows what failed and what helps. The audio kept for the admin retry becomes the download audio when audio download is enabled, otherwise it is deleted.
- Parakeet loaded its ASR model twice (once for the live WebSocket, once for `/v1/audio/transcriptions`), roughly doubling its (V)RAM use. Both now share one instance. `PARAKEET_MODEL` now also applies to live transcription, which previously ignored it.

## [0.10.3] — 2026-10-17

### Fixed

- Whisper server: every transcription failed with `unexpected keyword argument 'metadata_errors'` on a fresh image build. `faster-whisper` 1.2.x passes that argument to `av.open()`, which PyAV 19 no longer accepts. The server now decodes audio itself via ffmpeg (`_decode_audio()`), so it no longer depends on the installed `av` version.

## [0.10.2] — 2026-10-16

### Changed

- Dialogs no longer fly in sideways when opening; buttons and other clickable elements show the pointer cursor; the recording orb is smoother and uses the openDox cyan; the client install path in the distribution hint is `%ProgramFiles%\openDox`.
- LDAP: new option "Resolve nested groups" (Active Directory, off by default) so members of sub-groups of the configured groups may log in too.
- LDAP and OIDC logins are now fail closed: only members of an allowed, admin or moderator group may log in; with no group configured nobody can. OIDC gained an `allowed_groups` setting (migration included). Local users are unaffected. **Upgrade note:** set the allowed groups before updating, otherwise LDAP/OIDC users are locked out.
- The Parakeet GPU image is built on `nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04` (Python 3.12, **NVIDIA driver >= 580 on the host**) instead of CUDA 12.4.1 / Ubuntu 22.04: `onnxruntime-gpu >= 1.29` (needed for the arm64 build) requires Python >= 3.11 and is linked against CUDA 13, so the image could neither be built nor use the GPU with the old base. The Whisper GPU image is unchanged.
- The Docker images published by `docker-publish.yml` carry OCI labels and annotations (source repository, license, vendor, version, description), so the GHCR packages link to this repository. One failing image no longer cancels the others (`fail-fast: false`).

## [0.10.1] — 2026-10-15

### Changed
- Copyright holder of all source files, `REUSE.toml` and the README is now **S2A Open Technologies gGmbH** (rights transferred); Christopher Abanilla remains the author (`AUTHORS`). The license (AGPL-3.0-or-later) is unchanged.
- Contact address for security reports, the code of conduct and the author entry is now `christopher.abanilla@s2a-ot.digital`.

## [0.10.0] — 2026-10-15

### Added
- Several app instances can run side by side (see `docs/scaling.md`: nothing extra on one node, an nginx `hash` on `session_id` across nodes):
  - Settings changes reach every instance within `SETTINGS_CACHE_TTL_S` (default 30 s).
  - The login rate limit counts in Redis instead of per process.
  - Periodic jobs run on one instance per tick (Redis leader lock).
  - Concurrent starts no longer collide on migrations or the key rotation (PostgreSQL advisory locks).
  - The startup cleanup no longer deletes recordings that other instances are still writing.
  - Audio of a failed transcription goes straight to S3 (if configured), so any instance can retry it.
  - `TRUSTED_PROXY_IPS` now also accepts CIDR ranges.
- Resuming a recording on an app instance that does not hold its earlier audio is now refused with a clear error (`recording_audio_unavailable`, WebSocket close 1011) instead of silently continuing in a new, empty file.
- Final Whisper transcription now removes silence client-side before the server call (Silero VAD via `onnxruntime`, `vad_segmenter.py`): only speech is sent, in chunks of at most 28 s, in parallel and with a connection-error retry. It is always on and works the same against every Whisper server — vLLM hallucinated text on silence, looped on a `prompt` (WER 9 % -> 36 %) and rejected uploads over 25 MB. The pause length is `vad_min_silence_ms`; the "Qualität" settings tab is now always visible. If any chunk fails, no partial transcript is returned.

### Fixed
- A recording session rebuilt after the session store lost it (server restart without Redis, Redis data lost) no longer empties the PCM file of that recording: the audio already on disk is kept and appended to (`pcm_file.open_session_audio()`; a half-written sample at the end is cut off).

### Security
- `python-jose` (unmaintained, unpatched algorithm-confusion advisory) replaced by `PyJWT[crypto]` for local JWTs and OIDC id_token verification; invalid id_token signatures now return 502 instead of an unhandled error. `ecdsa` and `rsa` drop out as transitive dependencies.
- Locked transitive packages updated for open advisories (urllib3, anyio, pyasn1, starlette, langsmith, mako); frontend `http-cache-semantics` fixed.
- `decode_token()` no longer prints the token payload to stdout.

### Changed
- Frontend: `react-router-dom` 6 replaced by `react-router` 7 (fixes the open react-router advisory).
- Frontend: Tailwind CSS 3 -> 4 (CSS-first config in `src/index.css`, `tailwind.config.ts` removed, `tailwindcss-animate` -> `tw-animate-css`, `tailwind-merge` 3); removed the unused `lovable-tagger` dev plugin. `npm audit` is clean.

### Removed
- Near-live Whisper (`live_backend = "api"`: fixed chunks, overlap, LLM smoothing) — live text is Parakeet-only. Removes `chunk_correction_service.py`, `text_dedup.py`, the `chunk_length_s`/`overlap_s`/`left_context_s`/`live_beam_size`/`live_api_model` settings (migration `955c92f50534`; rows with `live_backend = 'api'` become `'disabled'`) and the matching admin fields. Old settings backups still restore; the removed fields are ignored.
- Unused, stale `requirements.txt` (pip freeze); `pyproject.toml` + `uv.lock` are the only dependency sources.

## [0.9.0] — 2026-10-08

### Changed

- **`ENCRYPTION_KEY` ist Pflicht.** Ohne einen gültigen Fernet-Key startet die
  App nicht mehr (`EncryptionKeyError`, kritischer Log-Eintrag), statt wie
  bisher mit einer Warnung im Klartext zu speichern. **Beim Update muss der Key
  gesetzt sein** (`.env` bzw. Docker-Secret `opendox_encryption_key`); bei
  `docker-compose.yml` bricht `docker compose up` ohne die Variable ab.
  Bereits im Klartext gespeicherte Altzeilen bleiben lesbar, werden aber nicht
  automatisch nachverschlüsselt. Der Health-Check „Verschlüsselung“ kennt den
  Status `disabled` nicht mehr.

- **Zeitstempel sind jetzt timezone-aware (UTC).** Das Backend schreibt
  `datetime.now(timezone.utc)` statt des naiven `utcnow()`; Voraussetzung für
  `sqlmodel` ≥ 0.0.47, dessen Datetime-Spalten naive Werte ablehnen. Migration
  `e3b7c1a95d42` wandelt `task.created_at`/`updated_at` und
  `user.disclaimer_accepted_at` unter PostgreSQL in `timestamptz` um (bestehende
  Werte gelten als UTC); SQLite bleibt unverändert. `sqlmodel` auf 0.0.48.
- **`pyproject.toml` pinnt nur noch direkte Abhängigkeiten.** Transitive Pakete
  stehen nur noch in `uv.lock`; die bisherigen exakten Pins führten bei
  Dependabot-Gruppen-PRs zu unauflösbaren Kombinationen.

- **Log-Zeilen im uvicorn-Format** (`INFO:     …`, farbig im Terminal) und
  Logger tragen den Namen ihres Moduls statt immer des Logger-Hilfsmoduls.
- **Abhängigkeiten aktualisiert** (FastAPI 0.142, langchain 1.4, openai 3,
  cryptography 50, ruff 0.16, Frontend-Minor-Updates). Dependabot hält npm- und
  Node-Majors sowie `onnxruntime-gpu` ≥ 1.30 (keine arm64-Wheels) zurück.
- **Parakeet-Live braucht eine GPU.** Die Doku sagt jetzt klar, dass das
  Streaming auf der CPU nicht echtzeitfähig ist; ohne GPU `live_backend` auf
  „disabled“ stellen oder Clients mit `?live=0` verbinden.

### Removed

- **`POST /api/v1/auth/register`.** Der Endpunkt war ohne Login erreichbar und
  legte ein aktives Konto mit Rolle `user` an. Konten legt jetzt ausschließlich
  ein Admin an (`POST /api/v1/auth/users`) oder sie entstehen beim ersten
  LDAP-/OIDC-Login. Das Frontend hat den Endpunkt nicht benutzt.

### Fixed

- **Key-Rotation deckt alle verschlüsselten Spalten ab.** Bisher wurden nur
  `record.content`/`summarize`/`pii_mapping` umverschlüsselt; `record.title`,
  `user.personal_glossary`, das LDAP-Bind-Passwort und das OIDC-Client-Secret
  blieben unter dem alten Key und waren nach einer Rotation nicht mehr lesbar.
  Ein Test prüft, dass neue `EncryptedString`-Spalten nicht vergessen werden.
  Wer bereits rotiert hat, muss diese vier Felder neu eingeben bzw. ihre Werte
  neu setzen.

## [0.8.3] — 2026-10-08

### Added

- **Admin → Clients: Desktop-Client verteilen und zentral einstellen** —
  Download-Links auf die Installer des openDox-Clients (neuestes GitHub-Release,
  `releases/latest/download/…`; der Server speichert keine Installer), eine
  fertige `settings.json` mit der Adresse dieses Servers und ausgefüllte
  Intune-/SCCM-Befehle (`GET /api/v1/settings/client-distribution/`, Admin und
  Demo-Viewer).
- **Client-Richtlinie** — Live-Ansicht, Diktiermikro-Modus, Zwischenablage
  (aus Verlauf heraushalten, Leeren nach N Sekunden) und Allow-Liste der
  Zielprogramme gelten global für alle Clients dieses Servers und haben Vorrang
  vor deren lokaler `settings.json`. Neue Tabelle `clientsettingsmodel`
  (Migration `c5e9a2d4f7b1`); `GET /api/v1/settings/client-config/` ist bewusst
  ohne Login abrufbar (der Client braucht sie vor der Anmeldung, der Inhalt ist
  nicht geheim), `PUT` nur für Admins.
- **Env-Variablen `CLIENT_SERVER_URL`** (Server-Adresse in der Client-
  `settings.json`, Standard: aus der Anfrage des Admins abgeleitet, inkl.
  `ROOT_PATH`) und **`CLIENT_DOWNLOAD_BASE_URL`** (Quelle der Installer-Links).
- **WebSocket `/ws/record?live=0`** — Clients ohne Live-Ansicht (openDox-Client)
  können die Live-Transkription pro Aufnahme abschalten: das Audio wird nur
  aufgezeichnet, kein Parakeet-Stream und keine Live-Inferenz; die
  Transkription nach dem Stop läuft unverändert. Ohne Parameter bleibt alles
  wie bisher.
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

### Security

- **Einstellungs-Endpunkte gaben Geheimnisse ohne Anmeldung heraus.** `GET /api/v1/settings/`
  `llm-settings/`, `ldap-settings/`, `oidc-settings/` und `whisper-settings/` waren ohne Login
  erreichbar und lieferten LLM-/Sanitizer-/ASR-API-Keys, das LDAP-Bind-Passwort und das
  OIDC-Client-Secret. Jetzt: `llm-`, `ldap-` und `oidc-settings` nur für Admin (Demo-Viewer
  sehen sie ohne die Geheimnisse), `whisper-settings` bleibt öffentlich (die Recorder brauchen
  `live_backend` vor dem Login), enthält die API-Keys aber nur noch für Admins. **Wer eine Instanz
  aus dem Netz erreichbar betrieben hat, sollte diese Zugangsdaten rotieren.**

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

[Unreleased]: https://github.com/daemolition/openDox/compare/v0.10.5...HEAD
[0.10.5]: https://github.com/daemolition/openDox/compare/v0.10.4...v0.10.5
[0.10.4]: https://github.com/daemolition/openDox/compare/v0.10.3...v0.10.4
[0.10.3]: https://github.com/daemolition/openDox/compare/v0.10.2...v0.10.3
[0.10.2]: https://github.com/daemolition/openDox/compare/v0.10.1...v0.10.2
[0.10.1]: https://github.com/daemolition/openDox/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/daemolition/openDox/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/daemolition/openDox/compare/v0.8.3...v0.9.0
[0.8.3]: https://github.com/daemolition/openDox/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/daemolition/openDox/compare/v0.1.0...v0.8.2
[0.8.0]: https://github.com/daemolition/openDox/compare/v0.1.0...v0.8.0
[0.1.0]: https://github.com/daemolition/openDox/releases/tag/v0.1.0