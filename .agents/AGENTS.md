# AGENTS.md — openDox

Agent guide for the openDox repository. (Repo-root `AGENTS.md` and `CLAUDE.md` are symlinks to this `.agents/AGENTS.md` file — editing either edits both.)

# openDox: Agent Guide

Medical transcription platform (AGPL-3.0-or-later), Author: `Christopher Abanilla <christopher.abanilla@gmx.de>`: record audio → transcribe (Whisper/Parakeet) → optionally sanitize PII → summarize via LLM, organized by medical category.

**Not a certified medical device** ("Kein Medizinprodukt") — this disclaimer must stay in the recording dialog and transcript view, in the repo-level `DISCLAIMER.md`, and in the mandatory first-login acceptance gate (`DisclaimerGate.tsx`, gated on `User.disclaimer_accepted_at` in `App.tsx`'s `ProtectedRoute`) — never remove or make any of the three bypassable.

## Dev Commands

```bash
# Backend — dev server with hot reload (`uv run main.py` also works, without reload)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Frontend
cd frontend && npm run dev    # port 3000, proxies {ROOT_PATH}/api/ → localhost:5000

# DB migrations (run after any SQLModel change)
alembic revision --autogenerate -m "desc"
alembic upgrade head

# Lint (backend only, ruff config in pyproject.toml)
ruff check --fix .
ruff format .

# Frontend lint
cd frontend && npm run lint

# Full stack Docker (compose file is at repo root, not docker/)
# App publishes on host port 20000 (APP_PORT), container 5000 → http://localhost:20000
docker compose up --build

# Bump the app version (syncs pyproject.toml + frontend/package.json + lockfile)
python scripts/bump_version.py --current       # print current version, no changes
python scripts/bump_version.py patch|minor|major
python scripts/bump_version.py 1.2.3            # explicit version
python scripts/bump_version.py patch --commit   # also git add+commit+tag

# Build + push all four Docker images (app, whisper, parakeet, garage-init) to the registry.
# docker_build_push.sh is local-only (gitignored), not checked into the repo.
# Uses bump_version.py --current, or OPENDOX_VERSION if already exported.
# Builds multi-arch (linux/amd64,linux/arm64) via buildx by default — override
# with OPENDOX_PLATFORMS=linux/amd64 for a fast single-arch test build.
# Pushes to registry.nutsolution.de by default; dual-push to ghcr.io too with
# OPENDOX_REGISTRIES="registry.nutsolution.de ghcr.io/<owner>". Whisper/Parakeet
# also get cpu-* tagged variants (no CUDA runtime — set WHISPER_DEVICE=cpu at
# deploy time for the Whisper cpu-* image; Parakeet's onnx-asr falls back to
# CPUExecutionProvider on its own).
./docker_build_push.sh

# Docker Swarm production deploy (docker-compose.yml stays the local/dev/demo setup)
docker swarm init                        # once per manager node
./create_docker_secrets.sh               # once — creates all secrets docker-swarm.yml needs
export OPENDOX_VERSION=$(python3 scripts/bump_version.py --current)
# export OPENDOX_REGISTRY=ghcr.io/<owner>  # optional — defaults to registry.nutsolution.de
./docker_build_push.sh
docker stack deploy -c docker-swarm.yml opendox
```

CI: `.github/workflows/ci.yml` runs backend (ruff + pytest) and frontend
(vitest + eslint) on every push/PR to `master`. `.github/workflows/docker-publish.yml`
is a separate, manual-only (`workflow_dispatch`) workflow that builds and
pushes all 4 images (multi-arch, plus Whisper/Parakeet `cpu-*` variants) to
`ghcr.io/<repo-owner>` using the built-in `GITHUB_TOKEN` — no extra secret
needed. Each build also emits a CycloneDX SBOM artifact per image variant
(`anchore/sbom-action`, pinned to the pushed manifest digest) plus
`provenance`/`sbom` attestations — voluntary, since CRA obligations don't
apply to non-commercial AGPL v3 OSS (see `docs/hospital-audit-frameworks.md`
§7); there is intentionally no CVE-scan gate behind it. Newly published
packages start private; switch each to public in its own Package Settings if
that's the intent.

**Backend tests** — pytest, config in `pyproject.toml` (`[tool.pytest.ini_options]`: `pythonpath=["."]`, `testpaths=["tests"]`):

```bash
pytest tests/            # all tests
pytest tests/llm/        # single package
pytest -k "test_name"    # single test
```

Shared fixtures live in `tests/conftest.py` — **reuse them, don't hand-build an app**: `client` (TestClient), `app` (minimal FastAPI wiring only the 4 routers with `get_session` dependency-overridden), `session_factory` (in-memory SQLite, `StaticPool`), plus `create_user`/`auth_headers`. An **autouse fixture resets the `SettingsService` singleton** each test so cached settings can't leak between tests — don't assume a warm cache.

**Frontend tests** — vitest, config `frontend/vitest.config.ts` (jsdom, setup `src/test/setup.ts`, `globals: true`); tests colocated in `src/**/__tests__/*.test.tsx`:

```bash
cd frontend && npm run test   # = vitest run
```

No automated integration tests for Docker/full-stack scenarios.

## Entrypoints & Wiring

- **Backend**: `main.py` → `backend/run.py:create_app()` — auto-runs Alembic on startup, mounts SPA static files
- **Routers**: `run.py` includes `record_bp`, `auth_bp`, `oidc_bp`, `settings_bp` — all under `router_prefix` (ROOT_PATH or empty). `oidc_bp` is imported in `auth_api/__init__.py` and registered separately in `run.py`.
- **Frontend**: `frontend/src/main.tsx` — path alias `@/` → `src/`, build output → `../backend/static` (NOT `frontend/dist`)
- **Parakeet server**: `parakeet_server/main.py` — standalone FastAPI, port 5001. Two endpoints: OpenAI-compatible `POST /v1/audio/transcriptions` (one-shot) and `WS /v1/audio/stream` (VAD-segmented streaming, see `parakeet_server/streaming.py`). Silero VAD + Parakeet ONNX (onnx-asr) loaded at startup; VAD model is downloaded at Docker build time into `/app/models/silero-vad` (flat dir, onnxruntime rejects HF's symlinked cache). The Dockerfile defaults to the NVIDIA GPU base (CUDA 12.4.1 + cuDNN) and auto-selects `CUDAExecutionProvider` with CPU fallback; build with `PARAKEET_DEVICE=cpu` for a CPU-only image. **Live streaming is only real-time on a GPU**: on CPU (either image) the 0.4s partial re-decode cannot keep up and live text lags badly, so on GPU-less hosts set `live_backend` to `disabled` (or have clients connect with `live=0`). Concurrent ASR `recognize()` calls across all sessions (partial re-decode every 0.4s + segment commits) are bounded process-wide by a `threading.BoundedSemaphore`, default `2`, override via `PARAKEET_MAX_CONCURRENT_DECODES` — this is a software cap independent of GPU headroom, so on a large GPU (e.g. H200) with many concurrent speakers it's usually the first thing to raise and load-test, not the hardware. Optional `ROOT_PATH` env var (same convention/rationale as the main backend's, see ROOT_PATH section below) lets a separate edge proxy expose this service under a sub-path — needed because Parakeet's native WS protocol (`partial`/`committed`/`delta`/`final` JSON frames, not an OpenAI schema) can't be proxied by litellm, so a deployment that fronts everything else with litellm still has to reverse-proxy Parakeet directly. `/v1/models` stays unauthenticated (it's the Docker `HEALTHCHECK` target); `/v1/audio/transcriptions` and the WS endpoint require `Authorization: Bearer <key>` whenever `PARAKEET_API_KEY`/`PARAKEET_API_KEY_FILE` is set (matches the token the backend already sends from `live_api_key`/`final_api_key` — no client-side change needed) — unset, they're open, with a startup warning logged.
- **Whisper server**: `whisper_server/app.py` — standalone, OpenAI-compatible, port 5002 in container. Like Parakeet, the Dockerfile has a `DEVICE` build-arg (`ARG DEVICE=gpu`, `base-cpu`/`base-gpu` stages) defaulting to the CUDA+cuDNN base; build with `--build-arg DEVICE=cpu` for a CPU-only image. Only the base image changes between devices — `faster-whisper`/`ctranslate2` ship a single wheel that detects CUDA at runtime, so `requirements.txt` doesn't need a cpu/gpu split (unlike Parakeet's `onnxruntime` vs `onnxruntime-gpu`). Concurrent `transcribe()` calls against the single shared `whisper_model` instance are bounded by an `asyncio.Semaphore`, default `4`, override via `WHISPER_MAX_CONCURRENT_TRANSCRIPTIONS` — matters especially when Whisper and Parakeet share one GPU, since a burst of many recordings finishing at once (e.g. a multi-user load test) would otherwise hit the GPU with zero coordination.
- **Env loading**: `backend/components/modules/env.py` — `env_or_file()` + `load_dotenv(override=True)` at import time. Every `{VAR}_FILE` suffix reads from file (Docker secrets)
- **Model registration**: `backend/components/models/__init__.py` imports every SQLModel table — Alembic autogenerate only sees models imported there. Add new models to both the file and `__all__`.

## Architecture

### Two-Stage ASR

| Stage | Backend | Purpose |
|---|---|---|
| **Live** | Parakeet (GPU default, onnx-asr) | Near-real-time VAD-segmented WebSocket transcription with punctuation |
| **Final** | Whisper (GPU, faster-whisper) | High-quality re-transcription of full audio |

- `asr_factory.py` creates backend instances based on `live_backend` setting (`"parakeet"` / `"api"` / `"disabled"`). `"parakeet"` → `ParakeetStreamBackend` (VAD-segmented streaming over WS); `"api"` → `OpenAICompatibleBackend` (fixed-chunk HTTP).
- When `live_backend="parakeet"` and `live_api_endpoint` is None, factory falls back to `PARAKEET_API_ENDPOINT` env var
- Parakeet live text: `record.py` forwards every float32 PCM frame to the Parakeet server's WS; the server's `StreamingSession` runs Silero VAD + Parakeet ONNX, commits segments at pauses (re-decoding the open segment every 0.4s for a live partial) and streams back `{"partial": <open segment>}` / `{"committed": ..., "delta": ...}` / `{"final": ...}`. `record.py` relays `delta` as `{"text": delta}` (appended to `stableTranscript` client-side) and `partial` as `{"partial": ...}` (renders as the live tail). No LLM correction (Parakeet already outputs punctuation). `chunk_length_s`/`overlap_s`/`left_context_s`/`merge_overlapping_text` do **not** apply to the streaming path — segmentation is internal to the Parakeet server.
- Whisper (`"api"`) live text goes through the fixed-chunk path in `record.py` (chunk_length_s/overlap_s/merge_overlapping_text) with batch LLM correction (`chunk_correction_service.py`, flushes every 5 chunks).

### Phonetic Term Correction

`term_correction_service.py` fuzzy-corrects mistranscribed German medical terms in the **final** Whisper text only (not live). The glossary source is `Categories.glossary` — a dedicated free-text field (comma/semicolon/newline-split via `parse_glossary()`), deliberately **separate** from `whisper_prompt`. They used to be the same field; split because `whisper_prompt` is also sent to Whisper as `initial_prompt`, which faster-whisper (mirroring OpenAI Whisper's `decoding.py`) truncates to the **last 224 tokens** of the context window with no length check and no warning — combining a category's spelling hints with an arbitrarily long glossary risked silently dropping whichever part landed at the front. `glossary` only ever reaches `correct_terms()`, which has no length limit, so it can hold as many terms as needed. A migration backfills `glossary = whisper_prompt` for categories created before the split.

Each user also has a private, free-text `User.personal_glossary` — "Mein Wörterbuch" / "My dictionary" — the "Wörterbuch" tab of `ProfileModal.tsx` (opened via "Profil" in `UserDropdown.tsx`; `PersonalDictionary.tsx`, `GET`/`PUT /api/v1/settings/my-dictionary/`, scoped to the caller only). Unlike personal categories (see below), it is **never** exposed to admins through any endpoint or schema. `background_transcription_service.py` merges the selected recording's `category.glossary` with the record owner's `personal_glossary` (`_build_correction_glossary()`, newline-joined) before parsing/correcting — so per recording, exactly one category's glossary (global or personal, whichever was picked) plus the owner's personal dictionary always apply together. `initial_prompt` is untouched by any of this — it only ever uses `category.whisper_prompt`.

`background_transcription_service.py` calls `correct_terms(text, glossary, threshold)` right after the final `backend.transcribe(...)` call, before the text is assigned to `record.content`: it slides a 1-3 word window over the text, compares each window's **Kölner Phonetik** code (`koelner_phonetik()`, self-contained, no dependency — Soundex/Metaphone don't fit German) against the glossary's precomputed codes via `rapidfuzz.fuzz.ratio`, and replaces windows scoring ≥ threshold with the glossary term's original spelling. Fail-open like `chunk_correction_service.py` (any exception → original text unchanged, `logger.warning`). Gated by `WhisperSettingsModel.term_correction_enabled` (default **off**) + `term_correction_threshold` (0-100 rapidfuzz scale, default 85.0), configurable in Admin UI → Dienste → Whisper → Final tab. Each replacement is logged (`original`/`replacement`/`score`) for threshold tuning, not persisted to the DB.

Note: `User.personal_glossary` is excluded from Settings Backup/Restore along with the rest of the `User` table (see that section below) — a user's personal dictionary isn't covered by that mechanism.

### PII Sanitizer (EntityGuard)

See `docs/pii.md` for the full flow. Summary:

1. `background_transcription_service.py` runs Whisper on the full audio → `record.content` (real names, encrypted at rest).
2. If sanitizer enabled (`sanitizing_service.py`), text is POSTed to the configured sanitizer endpoint, which returns `sanitized_text` (tokens like `[PERSON_1]`) and ideally a `mapping` dict.
3. If no `mapping` returned, `_extract_mapping()` falls back to word-level `difflib.SequenceMatcher` diff — best-effort, skips ambiguous adjacent tokens rather than risk wrong attribution. Result stored encrypted in `record.pii_mapping`.
4. The LLM only sees `sanitized_text` + `PRESERVE_TOKENS_INSTRUCTION` → `summary_anonymized`.
5. `reinject()` string-replaces tokens back to real names → `record.summarize` (real names, encrypted).

Configured via Admin UI → LLM settings → PII-Sanitizer. `sanitizer_endpoint` is a **full URL** (no path auto-appended), so it must include the complete sanitize route (e.g. `http://entityguard:9500/api/v1/sanitize`). Tokens must be unique per occurrence (e.g. `PERSON_1`/`PERSON_2`) — both the `mapping` dict and the diff fallback key on the literal token string, so a repeated token across two different entities silently collides.

### Categories & LLM Prompt Composition

`Categories` rows (`backend/components/models/categories.py`) serve four distinct roles per recording, chosen once at recording start (`Dashboard.tsx`'s category `<Select>`) and changeable afterward via `PUT /record/{id}` (`RecordUpdate.category_id`, applied in `record.py:update_record` — validates the id exists, 404 otherwise):

1. `whisper_prompt` → passed as Whisper's `initial_prompt` (vocabulary/spelling hints for the final transcription, `background_transcription_service.py`). Subject to faster-whisper's 224-token, last-N truncation — keep it short.
2. `glossary` → the term-correction glossary source (see "Phonetic Term Correction" above); deliberately separate from `whisper_prompt` since it has no length limit.
3. `system_prompt` → the LLM system prompt for summarization (`SummarizeModel.generate_response(custom_system_prompt=...)`). Falls back to `SummarizeModel.get_system_prompt()` (a generic, non-medical "clean up and structure" prompt) only when `record.category_id` is unset or the category has no `system_prompt` — rare in practice since the UI always preselects a category.
4. `llm_override_enabled` + `llm_model`/`llm_api_endpoint`/`llm_api_key`/`llm_temperature`/`llm_max_tokens` → optional per-category LLM backend override, so e.g. a "Kardiologie" category can route to a different model/endpoint than the global default.

**Placeholder-hallucination hardening is enforced in code, not in prompt text**: `generate_response()` unconditionally appends an anti-hallucination instruction (don't invent `[DATUM]`/`[WERT]`-style bracket placeholders for missing info, but preserve existing EntityGuard `[PERSON]`/`[LOCATION]` tokens — worded to not contradict `sanitizing_service._PRESERVE_TOKENS_INSTRUCTION`) to *every* prompt regardless of source, right next to the existing "Do not output your reasoning" suppression. This is deliberate: an admin creating a new category via `CategorySettings.tsx` writes free-form `system_prompt` text and has no way of knowing the local model tends to hallucinate placeholders — the rule can't rely on being written into that text.

### Audio Download (S3-compatible Object Storage)

Optional feature (`AudioSettingsModel`: `audio_download_enabled`, `audio_bitrate` up to `320k`, `audio_sample_rate`, `audio_format`) that keeps a compressed, encrypted copy of the final recording around for clinicians to download later — separate from the raw PCM/WAV (see Audio File Cleanup below for when that raw copy is actually deleted, which is no longer "always").

1. After Whisper's final transcription succeeds, `background_transcription_service.py:_persist_audio()` runs ffmpeg (mono, configurable bitrate/sample rate) on the WAV into a `tempfile.NamedTemporaryFile` — never a fixed on-disk path. The codec/extension is chosen from `audio_format` (`mp3`→libmp3lame, `ogg`→libopus, `flac`→flac at a fixed compression level, `wav`→pcm_s16le with no bitrate); unknown/empty values fall back to mp3.
2. The encoded bytes are encrypted with `field_encryption.encrypt_bytes()` (same `ENCRYPTION_KEY`/Fernet as text fields, just operating on raw bytes) and uploaded via `backend/components/services/audio_storage.py` (thin boto3 wrapper) to an S3-compatible bucket under key `records/{record.id}.{ext}.enc`. The temp file is deleted immediately after upload.
3. `record.file` stores that **S3 object key** (its `.{ext}.` segment is the source of truth for the stored format — settings can change between recordings), not a filesystem path.
4. `GET /record/{id}/audio` (`record.py:download_audio`) downloads the encrypted object, decrypts it, and streams it back via a plain `Response` — the plaintext audio never touches local disk on the serving side either. `Content-Type`/filename extension are derived from `record.file`'s key, not hardcoded.
5. `delete_record` deletes the S3 object (`audio_storage.delete()`) instead of a local file.

Configured entirely via env vars (not DB/admin-UI, since it's a deployment concern): `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION` — all support the `_FILE` convention. Any S3-compatible backend works (the app is generic boto3); `docker-compose.yml`/`docker-swarm.yml` bundle **Garage** (`dxflrs/garage`, self-hosted, AGPL, `garage/` dir) rather than MinIO, which has licensing restrictions. See the "Object Storage (Garage)" entry under Docker Layout for the init flow.

PCM chunks (the live-recording scratch buffer) intentionally stay **local and ephemeral**, not S3: a WebSocket connection (and the `finalize()` call that ends it) is pinned to a single backend process for its whole lifetime, so there's no cross-instance access problem to solve, and the raw audio is deleted moments after transcription anyway (DSGVO/§203 StGB minimization — see Audio File Cleanup). S3's lack of a cheap append API for many small realtime writes makes it a poor fit for that hot path regardless.

### App Version

`pyproject.toml`'s `[project].version` is the single source of truth for the whole app (frontend + backend ship in one Docker image). `backend/run.py:_read_app_version()` reads it at startup and sets `FastAPI(title="openDox", version=...)` (shows up in `/docs`) plus a public `GET /api/version` route. Bump with `scripts/bump_version.py` (see Dev Commands) — never hand-edit the version in `pyproject.toml`/`frontend/package.json` separately, the lockfile needs `npm install --package-lock-only` to resync.

**Release rule — don't bump after every feature.** Committing and pushing to `master` is free and happens continuously; new entries go under `## [Unreleased]` in `CHANGELOG.md`. A version is only cut when the maintainer says to release. Bumping moves `[Unreleased]` under `## [X.Y.Z]`, and **pushing the `vX.Y.Z` tag** is what triggers `.github/workflows/release.yml` (GitHub Release with that CHANGELOG section as notes; it fails if the heading is missing). Never bump, tag or push a tag on your own initiative. Meaning of the numbers while on 0.x: minor = something worth announcing to users, patch = fixes/small changes; an additional UI language (locale files only) counts as patch. Steps when asked to release:

1. `.venv/bin/python scripts/bump_version.py minor|patch` **without** `--commit` (the system `python3` is 3.10 and lacks `tomllib`).
2. `uv lock` — the script does not stage `uv.lock`, which embeds the project version; check that `git diff uv.lock` only changes that one line.
3. `git add pyproject.toml frontend/package.json frontend/package-lock.json CHANGELOG.md uv.lock`, commit `chore: bump version to vX.Y.Z`, then `git tag vX.Y.Z`. Push the tag only when the maintainer wants the release published.

### Authentication

Three methods, layered in this order in `auth_routes.py:login()`:

1. **Local DB** — bcrypt-hashed password in `User.hashed_password`.
2. **LDAP** — `LdapSettingsModel`. `ldap.py:authenticate()` escapes the username with `ldap3.utils.conv.escape_filter_chars()` before building `(user_dn=username)`, optionally ANDed with the raw `search_filter` power-user field. On successful bind, group membership is read from the user's `memberOf` attribute (assumes AD or OpenLDAP+memberof-overlay) and matched against three comma-separated **plain group name** fields — the app builds the expected DN itself as `cn={name},{base_dn}`, admins never type a DN: `allowed_groups` (gate — empty means any authenticated LDAP user may log in), `admin_groups`/`moderator_groups` (role mapping, admin takes precedence, mirrors the OIDC group mapping below). Empty passwords are rejected before any bind attempt (RFC 4513 unauthenticated-bind guard). Users are auto-provisioned on first successful login (empty password hash); role is re-synced from current group membership on every login. The optional LDAPS CA certificate is stored **in the DB** (`LdapSettingsModel.cert_data`, uploaded via `POST /ldap-settings/upload-cert/`) and passed to `ldap3.Tls(ca_certs_data=...)` — never written to disk; `cert_filename` is just a display label.
3. **OIDC (SSO)** — `oidc_bp` (`/api/v1/auth/oidc/{login,callback,status}`). Authorization Code Flow with discovery (`{provider_url}/.well-known/openid-configuration`). State is signed with `SECRET_KEY` via `itsdangerous.URLSafeSerializer` and stored in a short-lived cookie. The callback issues local JWT tokens and redirects to `/login?access_token=...&refresh_token=...` — the frontend (`Login.tsx`) extracts them from the query string and stores in localStorage. `OidcSettingsModel.admin_groups`/`moderator_groups` (comma-separated) map OIDC groups → role, same admin-takes-precedence logic as LDAP above. Users are auto-provisioned on first login. OIDC button in `Login.tsx` only shows when `/oidc/status` returns `{"enabled": true}`. `_build_redirect_uri()` only honors `X-Forwarded-Proto`/`X-Forwarded-Host` when the immediate peer is a trusted reverse proxy (`request.state.trusted_proxy`, set by `run.py`'s `mark_trusted_proxy` middleware from `TRUSTED_PROXY_IPS` — see Environment) — otherwise those headers are attacker-controllable and could redirect the OIDC callback.

OIDC depends on `itsdangerous` (added to `pyproject.toml`) and reuses `httpx` + `PyJWT` for token exchange and id_token verification against the provider JWKS.

`SECRET_KEY` (`backend/components/security/hashing.py`) has **no hardcoded fallback** — if unset, a random key is generated per process start and a `logger.critical()` warning is emitted (all existing sessions/tokens are invalidated on every restart until a stable `SECRET_KEY` is configured). `oidc_routes.py` imports the same `SECRET_KEY` for its state serializer rather than reading the env var separately, so both stay in sync.

### Settings Backup / Restore

`GET /api/v1/settings/backup/` exports all settings tables (Whisper, LLM, LDAP, OIDC, Categories, Languages) as a JSON file with `Content-Disposition: attachment`. `POST /api/v1/settings/backup/restore/` accepts a `multipart/form-data` upload and upserts singletons / replaces list tables wholesale. User table is intentionally excluded (passwords) — this also means `User.personal_glossary` (see "Phonetic Term Correction" above) isn't covered by backup/restore. After restore, `invalidate_cache()` + `reset_asr_backends()` are called.

### System Health Check

`GET /api/v1/settings/services-health/` (`settings_routes.py`) backs the admin "System" tab (`SystemSettings.tsx`, polled every 10s) — one `async def check_x()` closure per service (Postgres, Redis, Whisper, Parakeet, EntityGuard, S3, encryption-key state), run concurrently via `asyncio.gather`. Each returns `"online"`/`"offline"`/`"disabled"` — `"disabled"` short-circuits before any network call when a service isn't configured (e.g. `audio_storage.is_configured()` for S3, `isinstance(session_store, RedisSessionStore)` for Redis), so an intentionally-off feature doesn't show as a false "offline". The frontend is fully generic — it just renders whatever `{name, status}` list comes back, so adding a new check only requires backend changes.

### ROOT_PATH (Sub-path Deployment)

Set `ROOT_PATH=/opendox` in `.env`. Backend injects `window.__ROOT_PATH__` into `static/index.html` at startup — **no frontend rebuild needed**. `api.ts` reads `window.__ROOT_PATH__` (runtime, injected) with `import.meta.env.VITE_ROOT_PATH` as a Vite dev-only fallback. WebSocket in `Recorder.tsx` imports `BASE_PATH` from `api.ts`.

Do NOT pass `root_path=` to `FastAPI()` — it causes Starlette to strip the prefix before route matching, double-counting it. Routes are prefixed manually in `create_app()`.

Vite dev server proxy is keyed on `ROOT_PATH` (read from `.env` via `loadEnv`), not `VITE_ROOT_PATH`. Keep `VITE_ROOT_PATH` mirroring `ROOT_PATH` so the `api.ts` build-time fallback also works.

### Settings Cache

`SettingsService` is a singleton with `_whisper_settings` / `_llm_settings` caches. DB values override `.env` fallbacks. After changing settings via API or DB, call `invalidate_cache()` or `reset_asr_backends()` — otherwise the app serves stale values until restart.

### Session Store

`session_store.py` — factory that selects backend based on `REDIS_URL`:
- **Redis** (production): `REDIS_URL` set → `RedisSessionStore` with TTL, persistence, multi-instance support
- **In-Memory** (fallback): no `REDIS_URL` → `SessionStore` dict, sessions lost on restart, single-instance only

PCM audio is always written to disk (`session_{id}.pcm`), never stored in Redis. Import stays `from backend.components.services.session_store import session_store` — the factory decides.

Docker Compose includes a `redis:7-alpine` service with health check. App depends on it.

### Audio File Cleanup

Audio files (PCM + intermediate WAV) live in `chunks/` and are cleaned up via three mechanisms — all automatic, no manual intervention needed. This is about the *raw* recording scratch space; the optional persisted audio for download lives in S3-compatible storage instead, see Audio Download above. `chunks/` is backed by a named volume (`app-chunks`, mounted at `/app/chunks` in both `docker-compose.yml` and `docker-swarm.yml`) — without it, a container recreation wipes `chunks/failed/` along with everything else, silently breaking retry for any task whose failure predates the restart.

1. **Finalize** (`record.py:finalize()`): `finally` block only deletes `session_*.pcm` — it's fully redundant once the WAV exists. The WAV's fate is decided inside `background_transcription_task` itself (`background_transcription_service.py`), not here: deleted on success, **moved to `chunks/failed/task_{id}.wav` on failure** instead of being deleted, so a crashed/failed transcription no longer loses the recording. Same pattern for the `/upload` endpoint's `run_pipeline()` — no `finally`-block cleanup of `upload_path` needed since `background_transcription_task` owns it too.
2. **Stale-session loop** (`run.py:lifespan`): background task runs every 10 min, calls `session_store.cleanup_stale_sessions(30)` — removes sessions inactive for >30 min (browser closed without "Stop") and their PCM files.
3. **Startup cleanup** (`run.py:lifespan`): on app start, all `chunks/session_*.pcm` and `chunks/session_*.wav` files are removed — crash recovery for files left from a previous run. This only matches the top level of `chunks/` (non-recursive), so it does **not** touch `chunks/failed/` — retained failure audio survives app restarts.
4. **Failed-audio archival loop** (`run.py:lifespan`, `failed_audio_archival_service.py`): every 6h, `archive_stale_failed_audio()` moves any `chunks/failed/` file whose task hasn't been retried within `FAILED_AUDIO_RETENTION_DAYS` (default 3) to the same S3/Garage bucket used by Audio Download, under `archive/task_{id}.{ext}.enc` — encrypted the same way (`field_encryption.encrypt_bytes()`). If the configured `audio_format` is `"wav"` and the source is already `.wav` (the common case — `finalize()` always hands off WAV), the original bytes are uploaded as-is with no ffmpeg re-encode/resample; otherwise it transcodes via the same `_build_ffmpeg_args()` helper `_persist_audio()` uses. No-ops (logs once) if S3 isn't configured, leaving local files untouched. `Task.retry_audio_in_s3` marks which state `retry_audio_path` is in (local path vs. S3 key).

The lifespan handler (`contextlib.asynccontextmanager`) cancels both loops on shutdown for a graceful exit. `/upload-chunk` endpoint was removed (unused, leaked `.webm` files).

**Retry for failed transcriptions**: `Task.retry_audio_path` points at the retained file when set (`Task.retry_audio_in_s3` says whether that's a local path or an S3 key). Admin-only `GET /api/v1/records/tasks/failed` lists tasks with `status == "error"` and a retained file (joined with `Record` for title/timestamp), including an `archived` flag; `POST /api/v1/records/tasks/{id}/retry` fetches the audio back from S3 first if archived (decrypts, writes to `chunks/failed/`, deletes the S3 object only after the task's `"pending"` reset commits), resets the task to `"pending"`, and re-runs `background_transcription_task` on the audio in the background. Backed by `frontend/src/components/settings/FailedTranscriptions.tsx`, shown below the Audio-Download settings in AdminModal's "Audio" tab.

### Field Encryption

`field_encryption.py` — uses `ENCRYPTION_KEY` env var (Fernet). **Mandatory**: `_load_key()` raises `EncryptionKeyError` (critical log) at import if the key is unset, empty or not a Fernet key, so the app never runs unencrypted. Tests get a throwaway key from `tests/conftest.py` when none is configured. Rows written in plaintext before this rule still decrypt as-is (`decrypt()` returns non-decryptable values unchanged) and are not re-encrypted. `encrypt()`/`decrypt()` operate on `str` (used by the `EncryptedString` SQLAlchemy column type); `encrypt_bytes()`/`decrypt_bytes()` are the binary-safe siblings (same key), used by `audio_storage.py` for the persisted-audio feature.

## Docker Layout

- **`docker-compose.yml` (repo root)** — local dev/demo stack: postgres + redis + garage + garage-init + whisper (GPU, internal port 5002) + parakeet + app. All build contexts are `.` (repo root) with explicit `dockerfile:` paths (`whisper_server/Dockerfile`, `parakeet_server/Dockerfile`, `Dockerfile`).
- **`docker-swarm.yml` (repo root)** — production `docker stack deploy` target, paired with `create_docker_secrets.sh`. **`docker-swarm.rotation.yml`** is an optional overlay (`-c docker-swarm.yml -c docker-swarm.rotation.yml`), only applied during an active `ENCRYPTION_KEY` rotation — wires in `ENCRYPTION_KEY_PREVIOUS_FILE`/the `opendox_encryption_key_previous` secret, which `create_docker_secrets.sh` deliberately does *not* create by default (see the file's header comment for the full rotation procedure — Swarm secrets are immutable, so rotating means creating new secrets and redeploying, not editing one in place). Key differences from `docker-compose.yml` (see the file's header comment for the full list): no `build:` (Swarm only pulls, so all 4 images must be built+pushed first via `docker_build_push.sh`), secrets injected via Swarm's native `secrets:` + the app's existing `_FILE` env convention instead of plaintext `environment:`, `depends_on` removed (unenforced under Swarm — services rely on `restart_policy: on-failure` retrying until dependencies come up), and `app` pinned to `replicas: 1` (the PCM chunk dir is local-disk-only, see Audio File Cleanup). **GPU services need `deploy.placement.constraints: [node.labels.gpu == true]`, not `deploy.resources.reservations.devices`** — that key is a `docker compose`-only extension; native Swarm has no GPU-aware scheduling at all. Make the GPU available to every container on that node via `nvidia-ctk runtime configure --runtime=docker --set-as-default` on the node itself, then label it (`docker node update --label-add gpu=true <node>`).
- **Object Storage (Garage)** — `garage/garage.toml` (config, no secrets committed — `GARAGE_RPC_SECRET`/`GARAGE_ADMIN_TOKEN` env vars override, same pattern Garage's own CLI supports natively) + `garage/init/` (small Alpine image wrapping the static `dxflrs/garage` binary, since that upstream image ships no shell). `garage-init` is a one-shot idempotent setup (cluster layout, bucket, S3 access key) that runs on every `up`/`deploy` and exits 0 once configured; safe to re-run. Two non-obvious things if touching this: (1) don't set `rpc_public_addr` for this single-node cluster — under Swarm's overlay network the service's own DNS name isn't always resolvable from inside the container at boot, which put Garage in a crash-restart loop; (2) Swarm mounts secrets world-readable (mode 0444) by default, but Garage refuses to start if its RPC secret file is group/world-readable — the `garage_rpc_secret`/`garage_admin_token` secret entries in `docker-swarm.yml` need `mode: 0600`.
- `whisper_server/docker-compose.yml` — standalone Whisper for isolated dev, port 5002 (matches the port the main stack's `app` service expects)
- `docker/docker-whisper.yml` — older standalone Whisper compose (port 9100 → container 9000, 9000 conflicts with Jupyter); port doesn't match the main stack, likely superseded by `whisper_server/docker-compose.yml`
- `docker/docker-parakeet.yml` — standalone Parakeet (port 9200 → container 5001)

## Environment

Copy `.env.example` → `.env`:
- `DATABASE_URI` overrides individual `SQL_*` vars
- `WHISPER_API_ENDPOINT` / `WHISPER_API_KEY` fallback when DB settings are `None`
- `PARAKEET_API_ENDPOINT` — Parakeet server URL (default `http://localhost:5001/v1`); if it carries a sub-path (e.g. `.../parakeet/v1`), `ParakeetStreamBackend`/`OpenAICompatibleBackend` preserve it when deriving the WS/HTTP URLs, so it composes with `PARAKEET_ROOT_PATH` below
- `PARAKEET_ROOT_PATH` / `PARAKEET_PORT` / `PARAKEET_API_KEY` — Parakeet server sub-path, published host port, and bearer-auth key (see Parakeet server entry above); all optional, empty = root path, unpublished port, no auth
- `ENCRYPTION_KEY` — Fernet key for encrypted patient data (required, the app refuses to start without it)
- `SECRET_KEY` — JWT signing key; no insecure fallback, generated randomly per process (with a critical log warning) if unset — see Authentication
- `CORS_ALLOWED_ORIGINS` — comma-separated trusted origins; empty/unset allows all origins (logs a warning)
- `TRUSTED_PROXY_IPS` — comma-separated IPs allowed to set `X-Forwarded-Proto`/`-Host` (used for the OIDC redirect URI, see Authentication); empty/unset auto-detects loopback + the container's Docker gateway IP (`get_trusted_proxy_ips()` in `env.py`) — a same-host reverse proxy's connection through a published port arrives as the gateway IP, not `127.0.0.1`, since Docker NATs it
- `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` / `S3_REGION` — object storage for persisted audio downloads (see Audio Download section); `docker-compose.yml` points these at the bundled `garage` service by default
- `REDIS_URL` — Redis URL for session store (if empty, falls back to in-memory)
- `ROOT_PATH` — sub-path deployment prefix (empty for root)
- `VITE_ROOT_PATH` — Vite dev-only fallback for `api.ts`; should mirror `ROOT_PATH`
- `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` — trust a private CA for outbound HTTPS to internal endpoints (e.g. Whisper/LLM behind an internal reverse proxy like litellm); both must point at the same CA bundle, see Gotchas below

OIDC and LDAP settings live in the DB (`OidcSettingsModel`, `LdapSettingsModel`), not env vars. OIDC redirect URI is built from the incoming request (`X-Forwarded-Proto`/`Host` + `ROOT_PATH`), so it works behind reverse proxies without extra config.

## Gotchas

- **Dev server**: `uv run uvicorn main:app --reload` for hot reload; `uv run main.py` starts the app once as well (it passes the app object to `uvicorn.run`, so there is no double init), just without reload
- **SPA routing**: `SPAStaticFiles` in `run.py` falls back to `index.html` for 404s, but `/api/` routes are not static — they're matched by the router first
- **WebSocket**: Uses `BASE_PATH` from `api.ts` + `window.location.host`. Vite proxy has `ws: true`
- **Microphone**: Requires HTTPS (except localhost). `Permissions-Policy` header set in middleware
- **LLM**: Fresh `SummarizeModel()` per task, not singleton — DB settings re-read each time
- **Alembic URL**: `alembic.ini` has `sqlite3:///test.sqlite3` but both `run.py` and `alembic/env.py` override it at runtime with `SQLALCHEMY_URI` — the ini value is irrelevant
- **Frontend build output**: `vite.config.ts` outputs to `../backend/static` (not `frontend/dist`). This matters for Docker builds
- **SQLite fallback**: If no `DATABASE_URI` or `SQL_*` vars are set, `db_config.py` defaults to `postgresql+psycopg2://postgres:postgres@localhost:5432/aidox` (note: DB name is `aidox`, not `opendox`)
- **ruff known-first-party**: `pyproject.toml` has `known-first-party = ["dein_projektname"]` (template placeholder) — should be `["backend"]` for correct import sorting
- **Datetimes are timezone-aware UTC**: `sqlmodel` >= 0.0.47 maps `datetime` fields to `UTCDateTime`, which raises on naive values. Always write `datetime.now(timezone.utc)`, never `datetime.utcnow()`/`datetime.now()` into a model field (the in-memory session store's `datetime.now()` and the German display timestamps are not DB columns). Under PostgreSQL the columns are `timestamptz` (migration `e3b7c1a95d42`).
- **`pyproject.toml` pins direct dependencies only**: transitive packages belong to `uv.lock`. Exact pins on transitives made Dependabot group PRs unresolvable (e.g. `langchain-core` vs `uuid-utils`). Packages the code imports directly but which are also transitive (`httpx`, `requests`, `starlette`, `sqlalchemy`, `websockets`) use lower-bound ranges.
- **Session store mutations**: Never mutate session dicts directly in `record.py` — always use `session_store.set_live_state()`, `session_store.update_session()`, `session_store.append_audio()`. With Redis, dicts are not shared references
- **Apache reverse proxy + WebSocket**: If live transcription drops after 1-2 sentences behind Apache, `mod_proxy_wstunnel` is likely not loaded — `mod_proxy_http` lets the WS upgrade through but breaks on binary audio frames. Fix: `a2enmod proxy_wstunnel` and declare the WS `ProxyPass` for `/api/v1/records/ws/record` *before* the catch-all `ProxyPass /`. `Recorder.tsx`'s `ws.onclose` already handles unexpected disconnects (shows a toast, resets recording state).
- **`/api/health` is dead code**: `backend/views/root_view/root.py` defines `/health` and a second `/api/endpoint`, but that router is never `include_router()`'d in `create_app()`. Any request to `/api/health` silently falls through to the `SPAStaticFiles` catch-all and returns the SPA shell with a 200 — it looks like a working health check but isn't one. The real liveness/version routes are `/api/endpoint` and `/api/version`, both registered directly on `app` inside `create_app()`. Follow that same inline-registration pattern for new public root-level routes, not the unmounted `root_view` router.
- **Parakeet server deps**: `parakeet_server/requirements.txt` was split into `requirements.cpu.txt` and `requirements.gpu.txt` — the Dockerfile selects via `DEVICE` build-arg. Always add deps to **both** files (with the matching onnxruntime extra).
- **`onnxruntime-gpu` arm64 wheels**: linux/aarch64 wheels only exist from 1.29.0 onwards (older releases are x86_64-only), and they require glibc ≥ 2.34 (Ubuntu 22.04 base has 2.35 — fine). `requirements.gpu.txt` pins `>=1.29.0` accordingly; lowering the floor back to `<1.29` breaks the arm64 half of the multi-arch build with "No matching distribution found". Note the CUDA base (12.4) stays compatible — 1.29+ still targets CUDA 12.x.
- **CORS**: `allow_origins` is driven by `CORS_ALLOWED_ORIGINS` (comma-separated, `backend/run.py`) — empty/unset falls back to `["*"]` and logs a warning rather than failing. Set it once the real public origin(s) behind the reverse proxy are known.
- **Private CA trust is split across two env vars**: `httpx` (used by the LLM client — `langchain_openai.ChatOpenAI` in `llm_model.py`) honors `SSL_CERT_FILE`/`SSL_CERT_DIR`, but the plain `requests` library (used by `asr_backends/openai_compatible.py`, `chunk_correction_service.py`, `sanitizing_service.py`, `parakeet_stream.py`, `settings_routes.py`) ignores those and only honors `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` — neither library reads the other's var. Setting only `SSL_CERT_FILE` (e.g. to trust an internal CA behind litellm) makes the LLM connection work while ASR/EntityGuard/health-check calls to the same host still fail with `CERTIFICATE_VERIFY_FAILED`. `docker-swarm.yml`'s `app` service sets both, pointed at the same host-mounted `/etc/ssl/certs/ca-certificates.crt`.
- **`docker stack config`/`docker stack deploy` interpolation bug**: a literal ` - ` (space-hyphen-space) inside a `${VAR:?error message}` clause makes the Compose-spec interpolator silently mangle the substitution (returns garbage instead of the variable's value, even when it's set) — reproduced directly, not theoretical. Avoid dashes in `:?`/`:-` default/error text in any Swarm compose file; `docker-swarm.yml`'s `OPENDOX_VERSION` guard message was reworded around this.

## Frontend Conventions

- **UI**: shadcn/ui components in `src/components/ui/`
- **Toaster**: `<Toaster />` from `sonner` is mounted once in `App.tsx`. Call `toast.success()`/`toast.error()` anywhere — it won't render without this.
- **State**: `useAuth()` from `AuthContext.tsx` is source of truth. NEVER hardcode `userId="1"`
- **Disclaimer**: "Kein Medizinprodukt" required in recording dialog AND transcript view — in **every** UI language (translations live in the `disclaimer` i18n namespace and must say the same thing; a language is not done until they exist). See `DISCLAIMER.md` (repo root) for the full operator/regulatory disclaimer, and `DisclaimerGate.tsx` for the mandatory first-login acceptance gate (`User.disclaimer_accepted_at`, checked in `App.tsx`'s `ProtectedRoute`) — don't remove or make either bypassable
- **Logo**: `Logo.tsx` animated SVG — `viewBox` is tightly cropped to the actual drawn content (text + waveform), not the original oversized template box; don't widen it back or `justify-center` placements (mobile header, `AdminModal`) will drift off-center again
- **API prefix**: All modules must import `BASE_PATH` from `api.ts`, not define their own
- **Mobile viewport height**: use `dvh` (dynamic viewport height), not `vh`, for anything meant to fill the screen/a dialog (`Recorder.tsx`, `AdminModal.tsx`, `Dashboard.tsx`'s root). Mobile browsers resize `100vh` when the address bar shows/hides, causing clipping or forced page-scroll that `dvh` avoids
- **Flex children that must scroll internally** (e.g. `Sidebar.tsx`'s recordings `ScrollArea`) need `min-h-0` — a `flex-1` child otherwise refuses to shrink below its content's natural height and overflows the parent instead of scrolling
- **i18n**: `i18next` + `react-i18next`. UI strings are never hardcoded — use `useTranslation('<namespace>')` (cross-namespace: `t('common:save')`). Translations are JSON in `frontend/src/i18n/locales/<lang>/<namespace>.json`, one namespace per component group (`admin`, `whisper`, `record`, `disclaimer`, `errors`, ...); `src/i18n/index.ts` loads every file via `import.meta.glob`, so a new namespace file needs no registration. German is the source language and the fallback (`fallbackLng: 'de'`). `src/i18n/__tests__/locales.test.ts` fails if any language lacks a key, has an empty value or different `{{placeholders}}` than German — keep the languages in sync. **Adding a language**: create `locales/<code>/` with a file for every German namespace, add it to `SUPPORTED_LANGUAGES` in `i18n/index.ts` and to `UI_LANGUAGES` in `backend/components/models/user_model.py`. The chosen language is stored per user (`User.ui_language`, `PUT /api/v1/settings/my-language/`, exposed on `/auth/me`; set from `ProfileModal.tsx` via `AuthContext.updateUiLanguage`); before login it falls back to `localStorage["ui_language"]`, then the browser language. It is unrelated to the transcription language (`WhisperSettingsModel.language`). Non-React code (e.g. `lib/archive.ts`) uses `i18n.t('ns:key')` directly. Dates are formatted with `i18n.language`; recording timestamps stay stored as German-format strings (`parseRecordTimestamp()` parses them) and are only *displayed* via `formatRecordTimestamp()`. Tests run in German (`src/test/setup.ts`); switch with `await i18n.changeLanguage('en')` and restore it in `finally`.
- **API errors**: user-facing backend errors are raised with `api_error(status, code, message, **params)` (`backend/components/modules/api_errors.py`) → `detail={"code","message","params"}`. The frontend renders them with `apiErrorMessage(body, fallback)` (`lib/apiError.ts`), which looks up `errors:<code>` and falls back to `message`, then to legacy string details. Probe endpoints (`/asr-test/`) return `{"ok": false, "code", "error"}` and go through the same helper. New user-facing errors need a code + an `errors.json` entry in every language. The OIDC callback errors (`oidc_routes.py`) stay plain strings on purpose — the browser shows that JSON directly after a redirect, the SPA never renders it.
- **Profile modal**: the user menu has "Profil" (→ `ProfileModal.tsx`, same layout as `AdminModal`: language, dictionary, own categories for role `user`, appearance) and — for non-`user` roles — "Administration".
- **AdminModal nav**: "Dienste" tab has Whisper/ASR + LLM sub-tabs. "Audio" tab holds `AudioConfig.tsx` (audio-download settings, incl. format/bitrate) followed by `FailedTranscriptions.tsx` (retry list for failed transcriptions, see Audio File Cleanup). "Authentifizierung" tab has LDAP + OIDC/SSO sub-tabs. Whisper config tab grid columns depend on `live_backend` value (`grid-cols-3` vs `grid-cols-4`) — the "Qualität" tab only exists when `live_backend === 'api'`.

## Python Style (enforced by ruff)

Config in `pyproject.toml` — rules: `E, F, I, D` (PEP8 + isort + pydocstyle), Google docstrings, line length 88. Standard 3-group imports with blank lines (`# Standard library` / `# Third-party` / `# Custom`), `snake_case` for functions/variables, `PascalCase` for classes, type hints + Google docstrings. The `known-first-party` placeholder gotcha is noted under Gotchas above.