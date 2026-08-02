# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# openDox: Agent Guide

Medical transcription platform (AGPL-3.0-or-later), Author: `Christopher Abanilla <christopher.abanilla@gmx.de>`: record audio → transcribe (Whisper/Parakeet) → optionally sanitize PII → summarize via LLM, organized by medical category.

**Not a certified medical device** ("Kein Medizinprodukt") — this disclaimer must stay in the recording dialog and transcript view, in the repo-level `DISCLAIMER.md`, and in the mandatory first-login acceptance gate (`DisclaimerGate.tsx`, gated on `User.disclaimer_accepted_at` in `App.tsx`'s `ProtectedRoute`) — never remove or make any of the three bypassable.

## Dev Commands

```bash
# Backend — only valid entrypoint; never `uv run main.py` (causes double init)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000

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
docker compose up --build

# Bump the app version (syncs pyproject.toml + frontend/package.json + lockfile)
python scripts/bump_version.py --current       # print current version, no changes
python scripts/bump_version.py patch|minor|major
python scripts/bump_version.py 1.2.3            # explicit version
python scripts/bump_version.py patch --commit   # also git add+commit+tag

# Build + push all four Docker images (app, whisper, parakeet, garage-init) to the registry
# (uses bump_version.py --current, or OPENDOX_VERSION if already exported)
./docker_build_push.sh

# Docker Swarm production deploy (docker-compose.yml stays the local/dev/demo setup)
docker swarm init                        # once per manager node
./create_docker_secrets.sh               # once — creates all secrets docker-swarm.yml needs
export OPENDOX_VERSION=$(python3 scripts/bump_version.py --current)
./docker_build_push.sh
docker stack deploy -c docker-swarm.yml opendox
```

No CI workflows configured. Tests live in `tests/`; run via pytest:

```bash
pytest tests/            # all tests
pytest tests/llm/        # single package
pytest -k "test_name"    # single test
```

No automated integration tests for Docker/full-stack scenarios.

## Entrypoints & Wiring

- **Backend**: `main.py` → `backend/run.py:create_app()` — auto-runs Alembic on startup, mounts SPA static files
- **Routers**: `run.py` includes `record_bp`, `auth_bp`, `oidc_bp`, `settings_bp` — all under `router_prefix` (ROOT_PATH or empty). `oidc_bp` is imported in `auth_api/__init__.py` and registered separately in `run.py`.
- **Frontend**: `frontend/src/main.tsx` — path alias `@/` → `src/`, build output → `../backend/static` (NOT `frontend/dist`)
- **Parakeet server**: `parakeet_server/main.py` — standalone FastAPI, port 5001. Two endpoints: OpenAI-compatible `POST /v1/audio/transcriptions` (one-shot) and `WS /v1/audio/stream` (VAD-segmented streaming, see `parakeet_server/streaming.py`). Silero VAD + Parakeet ONNX (onnx-asr) loaded at startup; VAD model is downloaded at Docker build time into `/app/models/silero-vad` (flat dir, onnxruntime rejects HF's symlinked cache). The Dockerfile defaults to the NVIDIA GPU base (CUDA 12.4.1 + cuDNN) and auto-selects `CUDAExecutionProvider` with CPU fallback; build with `PARAKEET_DEVICE=cpu` for a CPU-only image.
- **Whisper server**: `whisper_server/app.py` — standalone, OpenAI-compatible, port 5002 in container. Like Parakeet, the Dockerfile has a `DEVICE` build-arg (`ARG DEVICE=gpu`, `base-cpu`/`base-gpu` stages) defaulting to the CUDA+cuDNN base; build with `--build-arg DEVICE=cpu` for a CPU-only image. Only the base image changes between devices — `faster-whisper`/`ctranslate2` ship a single wheel that detects CUDA at runtime, so `requirements.txt` doesn't need a cpu/gpu split (unlike Parakeet's `onnxruntime` vs `onnxruntime-gpu`).
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

### PII Sanitizer (EntityGuard)

See `docs/pii.md` for the full flow. Summary:

1. `background_transcription_service.py` runs Whisper on the full audio → `record.content` (real names, encrypted at rest).
2. If sanitizer enabled (`sanitizing_service.py`), text is POSTed to the configured sanitizer endpoint, which returns `sanitized_text` (tokens like `[PERSON_1]`) and ideally a `mapping` dict.
3. If no `mapping` returned, `_extract_mapping()` falls back to word-level `difflib.SequenceMatcher` diff — best-effort, skips ambiguous adjacent tokens rather than risk wrong attribution. Result stored encrypted in `record.pii_mapping`.
4. The LLM only sees `sanitized_text` + `PRESERVE_TOKENS_INSTRUCTION` → `summary_anonymized`.
5. `reinject()` string-replaces tokens back to real names → `record.summarize` (real names, encrypted).

Configured via Admin UI → LLM settings → PII-Sanitizer. `sanitizer_endpoint` is a **full URL** (no path auto-appended), so it must include the complete sanitize route (e.g. `http://entityguard:9500/api/v1/sanitize`). Tokens must be unique per occurrence (e.g. `PERSON_1`/`PERSON_2`) — both the `mapping` dict and the diff fallback key on the literal token string, so a repeated token across two different entities silently collides.

### Audio Download (S3-compatible Object Storage)

Optional feature (`AudioSettingsModel`: `audio_download_enabled`, `audio_bitrate`, `audio_sample_rate`) that keeps a compressed, encrypted copy of the final recording around for clinicians to download later — separate from the raw PCM/WAV, which is always deleted after transcription (see Audio File Cleanup below).

1. After Whisper's final transcription succeeds, `background_transcription_service.py:_persist_audio_as_mp3()` runs ffmpeg (mono, configurable bitrate/sample rate) on the WAV into a `tempfile.NamedTemporaryFile` — never a fixed on-disk path.
2. The MP3 bytes are encrypted with `field_encryption.encrypt_bytes()` (same `ENCRYPTION_KEY`/Fernet as text fields, just operating on raw bytes) and uploaded via `backend/components/services/audio_storage.py` (thin boto3 wrapper) to an S3-compatible bucket under key `records/{record.id}.mp3.enc`. The temp file is deleted immediately after upload.
3. `record.file` stores that **S3 object key**, not a filesystem path.
4. `GET /record/{id}/audio` (`record.py:download_audio`) downloads the encrypted object, decrypts it, and streams it back via a plain `Response` — the plaintext MP3 never touches local disk on the serving side either.
5. `delete_record` deletes the S3 object (`audio_storage.delete()`) instead of a local file.

Configured entirely via env vars (not DB/admin-UI, since it's a deployment concern): `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION` — all support the `_FILE` convention. Any S3-compatible backend works (the app is generic boto3); `docker-compose.yml`/`docker-swarm.yml` bundle **Garage** (`dxflrs/garage`, self-hosted, AGPL, `garage/` dir) rather than MinIO, which has licensing restrictions. See the "Object Storage (Garage)" entry under Docker Layout for the init flow.

PCM chunks (the live-recording scratch buffer) intentionally stay **local and ephemeral**, not S3: a WebSocket connection (and the `finalize()` call that ends it) is pinned to a single backend process for its whole lifetime, so there's no cross-instance access problem to solve, and the raw audio is deleted moments after transcription anyway (DSGVO/§203 StGB minimization — see Audio File Cleanup). S3's lack of a cheap append API for many small realtime writes makes it a poor fit for that hot path regardless.

### App Version

`pyproject.toml`'s `[project].version` is the single source of truth for the whole app (frontend + backend ship in one Docker image). `backend/run.py:_read_app_version()` reads it at startup and sets `FastAPI(title="openDox", version=...)` (shows up in `/docs`) plus a public `GET /api/version` route. Bump with `scripts/bump_version.py` (see Dev Commands) — never hand-edit the version in `pyproject.toml`/`frontend/package.json` separately, the lockfile needs `npm install --package-lock-only` to resync.

### Authentication

Three methods, layered in this order in `auth_routes.py:login()`:

1. **Local DB** — bcrypt-hashed password in `User.hashed_password`.
2. **LDAP** — `LdapSettingsModel`. `ldap.py:authenticate()` escapes the username with `ldap3.utils.conv.escape_filter_chars()` before building `(user_dn=username)`, optionally ANDed with the raw `search_filter` power-user field. On successful bind, group membership is read from the user's `memberOf` attribute (assumes AD or OpenLDAP+memberof-overlay) and matched against three comma-separated **plain group name** fields — the app builds the expected DN itself as `cn={name},{base_dn}`, admins never type a DN: `allowed_groups` (gate — empty means any authenticated LDAP user may log in), `admin_groups`/`moderator_groups` (role mapping, admin takes precedence, mirrors the OIDC group mapping below). Empty passwords are rejected before any bind attempt (RFC 4513 unauthenticated-bind guard). Users are auto-provisioned on first successful login (empty password hash); role is re-synced from current group membership on every login. The optional LDAPS CA certificate is stored **in the DB** (`LdapSettingsModel.cert_data`, uploaded via `POST /ldap-settings/upload-cert/`) and passed to `ldap3.Tls(ca_certs_data=...)` — never written to disk; `cert_filename` is just a display label.
3. **OIDC (SSO)** — `oidc_bp` (`/api/v1/auth/oidc/{login,callback,status}`). Authorization Code Flow with discovery (`{provider_url}/.well-known/openid-configuration`). State is signed with `SECRET_KEY` via `itsdangerous.URLSafeSerializer` and stored in a short-lived cookie. The callback issues local JWT tokens and redirects to `/login?access_token=...&refresh_token=...` — the frontend (`Login.tsx`) extracts them from the query string and stores in localStorage. `OidcSettingsModel.admin_groups`/`moderator_groups` (comma-separated) map OIDC groups → role, same admin-takes-precedence logic as LDAP above. Users are auto-provisioned on first login. OIDC button in `Login.tsx` only shows when `/oidc/status` returns `{"enabled": true}`.

OIDC depends on `itsdangerous` (added to `pyproject.toml`) and reuses `httpx` + `python-jose` for token exchange and id_token verification against the provider JWKS.

`SECRET_KEY` (`backend/components/security/hashing.py`) has **no hardcoded fallback** — if unset, a random key is generated per process start and a `logger.critical()` warning is emitted (all existing sessions/tokens are invalidated on every restart until a stable `SECRET_KEY` is configured). `oidc_routes.py` imports the same `SECRET_KEY` for its state serializer rather than reading the env var separately, so both stay in sync.

### Settings Backup / Restore

`GET /api/v1/settings/backup/` exports all settings tables (Whisper, LLM, LDAP, OIDC, Categories, Languages, Terminology) as a JSON file with `Content-Disposition: attachment`. `POST /api/v1/settings/backup/restore/` accepts a `multipart/form-data` upload and upserts singletons / replaces list tables wholesale. User table is intentionally excluded (passwords). After restore, `invalidate_cache()` + `reset_asr_backends()` are called.

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

Audio files (PCM + intermediate WAV) live in `chunks/` and are cleaned up via three mechanisms — all automatic, no manual intervention needed. This is about the *raw* recording scratch space; the optional persisted MP3 for download lives in S3-compatible storage instead, see Audio Download above.

1. **Finalize** (`record.py:finalize()`): `finally` block deletes both `session_*.pcm` and `session_*.wav` regardless of whether transcription succeeded. `background_transcription_task` also deletes the WAV on success (redundant, harmless).
2. **Stale-session loop** (`run.py:lifespan`): background task runs every 10 min, calls `session_store.cleanup_stale_sessions(30)` — removes sessions inactive for >30 min (browser closed without "Stop") and their PCM files.
3. **Startup cleanup** (`run.py:lifespan`): on app start, all `chunks/session_*.pcm` and `chunks/session_*.wav` files are removed — crash recovery for files left from a previous run.

The lifespan handler (`contextlib.asynccontextmanager`) cancels the cleanup loop on shutdown for a graceful exit. `/upload-chunk` endpoint was removed (unused, leaked `.webm` files).

### Field Encryption

`field_encryption.py` — uses `ENCRYPTION_KEY` env var (Fernet). Required for encrypted patient data. If not set, encryption is silently disabled (logs a warning, unlike `SECRET_KEY`'s critical-and-generate behavior above). `encrypt()`/`decrypt()` operate on `str` (used by the `EncryptedString` SQLAlchemy column type); `encrypt_bytes()`/`decrypt_bytes()` are the binary-safe siblings (same key), used by `audio_storage.py` for the persisted-audio feature.

## Docker Layout

- **`docker-compose.yml` (repo root)** — local dev/demo stack: postgres + redis + garage + garage-init + whisper (GPU, internal port 5002) + parakeet + app. All build contexts are `.` (repo root) with explicit `dockerfile:` paths (`whisper_server/Dockerfile`, `parakeet_server/Dockerfile`, `Dockerfile`).
- **`docker-swarm.yml` (repo root)** — production `docker stack deploy` target, paired with `create_docker_secrets.sh`. Key differences from `docker-compose.yml` (see the file's header comment for the full list): no `build:` (Swarm only pulls, so all 4 images must be built+pushed first via `docker_build_push.sh`), secrets injected via Swarm's native `secrets:` + the app's existing `_FILE` env convention instead of plaintext `environment:`, `depends_on` removed (unenforced under Swarm — services rely on `restart_policy: on-failure` retrying until dependencies come up), and `app` pinned to `replicas: 1` (the PCM chunk dir is local-disk-only, see Audio File Cleanup). **GPU services need `deploy.placement.constraints: [node.labels.gpu == true]`, not `deploy.resources.reservations.devices`** — that key is a `docker compose`-only extension; native Swarm has no GPU-aware scheduling at all. Make the GPU available to every container on that node via `nvidia-ctk runtime configure --runtime=docker --set-as-default` on the node itself, then label it (`docker node update --label-add gpu=true <node>`).
- **Object Storage (Garage)** — `garage/garage.toml` (config, no secrets committed — `GARAGE_RPC_SECRET`/`GARAGE_ADMIN_TOKEN` env vars override, same pattern Garage's own CLI supports natively) + `garage/init/` (small Alpine image wrapping the static `dxflrs/garage` binary, since that upstream image ships no shell). `garage-init` is a one-shot idempotent setup (cluster layout, bucket, S3 access key) that runs on every `up`/`deploy` and exits 0 once configured; safe to re-run. Two non-obvious things if touching this: (1) don't set `rpc_public_addr` for this single-node cluster — under Swarm's overlay network the service's own DNS name isn't always resolvable from inside the container at boot, which put Garage in a crash-restart loop; (2) Swarm mounts secrets world-readable (mode 0444) by default, but Garage refuses to start if its RPC secret file is group/world-readable — the `garage_rpc_secret`/`garage_admin_token` secret entries in `docker-swarm.yml` need `mode: 0600`.
- `whisper_server/docker-compose.yml` — standalone Whisper for isolated dev, port 5002 (matches the port the main stack's `app` service expects)
- `docker/docker-whisper.yml` — older standalone Whisper compose (port 9100 → container 9000, 9000 conflicts with Jupyter); port doesn't match the main stack, likely superseded by `whisper_server/docker-compose.yml`
- `docker/docker-parakeet.yml` — standalone Parakeet (port 9200 → container 5001)

### Dockerfile Frontend Build

`vite.config.ts` outputs to `../backend/static` (resolves to `/app/backend/static` in Docker). The Dockerfile `COPY` line correctly copies from `/app/backend/static`.

## Environment

Copy `.env.example` → `.env`:
- `DATABASE_URI` overrides individual `SQL_*` vars
- `WHISPER_API_ENDPOINT` / `WHISPER_API_KEY` fallback when DB settings are `None`
- `PARAKEET_API_ENDPOINT` — Parakeet server URL (default `http://localhost:5001/v1`)
- `ENCRYPTION_KEY` — Fernet key for encrypted patient data (silently disabled if empty)
- `SECRET_KEY` — JWT signing key; no insecure fallback, generated randomly per process (with a critical log warning) if unset — see Authentication
- `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` / `S3_REGION` — object storage for persisted audio downloads (see Audio Download section); `docker-compose.yml` points these at the bundled `garage` service by default
- `REDIS_URL` — Redis URL for session store (if empty, falls back to in-memory)
- `ROOT_PATH` — sub-path deployment prefix (empty for root)
- `VITE_ROOT_PATH` — Vite dev-only fallback for `api.ts`; should mirror `ROOT_PATH`

OIDC and LDAP settings live in the DB (`OidcSettingsModel`, `LdapSettingsModel`), not env vars. OIDC redirect URI is built from the incoming request (`X-Forwarded-Proto`/`Host` + `ROOT_PATH`), so it works behind reverse proxies without extra config.

## Gotchas

- **Dev server**: Always `python -m uvicorn main:app`, never `uv run main.py`
- **SPA routing**: `SPAStaticFiles` in `run.py` falls back to `index.html` for 404s, but `/api/` routes are not static — they're matched by the router first
- **WebSocket**: Uses `BASE_PATH` from `api.ts` + `window.location.host`. Vite proxy has `ws: true`
- **Microphone**: Requires HTTPS (except localhost). `Permissions-Policy` header set in middleware
- **LLM**: Fresh `SummarizeModel()` per task, not singleton — DB settings re-read each time
- **Alembic URL**: `alembic.ini` has `sqlite3:///test.sqlite3` but both `run.py` and `alembic/env.py` override it at runtime with `SQLALCHEMY_URI` — the ini value is irrelevant
- **Frontend build output**: `vite.config.ts` outputs to `../backend/static` (not `frontend/dist`). This matters for Docker builds
- **SQLite fallback**: If no `DATABASE_URI` or `SQL_*` vars are set, `db_config.py` defaults to `postgresql+psycopg2://postgres:postgres@localhost:5432/aidox` (note: DB name is `aidox`, not `opendox`)
- **ruff known-first-party**: `pyproject.toml` has `known-first-party = ["dein_projektname"]` (template placeholder) — should be `["backend"]` for correct import sorting
- **Session store mutations**: Never mutate session dicts directly in `record.py` — always use `session_store.set_live_state()`, `session_store.update_session()`, `session_store.append_audio()`. With Redis, dicts are not shared references
- **Apache reverse proxy + WebSocket**: If live transcription drops after 1-2 sentences behind Apache, `mod_proxy_wstunnel` is likely not loaded — `mod_proxy_http` lets the WS upgrade through but breaks on binary audio frames. Fix: `a2enmod proxy_wstunnel` and declare the WS `ProxyPass` for `/api/v1/records/ws/record` *before* the catch-all `ProxyPass /`. `Recorder.tsx`'s `ws.onclose` already handles unexpected disconnects (shows a toast, resets recording state).
- **`/api/health` is dead code**: `backend/views/root_view/root.py` defines `/health` and a second `/api/endpoint`, but that router is never `include_router()`'d in `create_app()`. Any request to `/api/health` silently falls through to the `SPAStaticFiles` catch-all and returns the SPA shell with a 200 — it looks like a working health check but isn't one. The real liveness/version routes are `/api/endpoint` and `/api/version`, both registered directly on `app` inside `create_app()`. Follow that same inline-registration pattern for new public root-level routes, not the unmounted `root_view` router.
- **Parakeet server deps**: `parakeet_server/requirements.txt` was split into `requirements.cpu.txt` and `requirements.gpu.txt` — the Dockerfile selects via `DEVICE` build-arg. Always add deps to **both** files (with the matching onnxruntime extra).
- **`/api/ready` is currently broken**: `readiness_check()` in `backend/run.py` imports `RedisSessionStore` from `backend.components.services.session_store` — it actually lives in `session_store_redis` (see `settings_routes.py`'s `check_redis()` for the correct import). Every call 500s with an `ImportError`. Pre-existing bug, not yet fixed; don't assume `/api/ready` works when wiring up healthchecks/probes — `/api/endpoint` (pure liveness, no DB/Redis check) is the one that actually works today.
- **`docker stack config`/`docker stack deploy` interpolation bug**: a literal ` - ` (space-hyphen-space) inside a `${VAR:?error message}` clause makes the Compose-spec interpolator silently mangle the substitution (returns garbage instead of the variable's value, even when it's set) — reproduced directly, not theoretical. Avoid dashes in `:?`/`:-` default/error text in any Swarm compose file; `docker-swarm.yml`'s `OPENDOX_VERSION` guard message was reworded around this.

## Frontend Conventions

- **UI**: shadcn/ui components in `src/components/ui/`
- **Toaster**: `<Toaster />` from `sonner` is mounted once in `App.tsx`. Call `toast.success()`/`toast.error()` anywhere — it won't render without this.
- **State**: `useAuth()` from `AuthContext.tsx` is source of truth. NEVER hardcode `userId="1"`
- **Disclaimer**: "Kein Medizinprodukt" required in recording dialog AND transcript view. See `DISCLAIMER.md` (repo root) for the full operator/regulatory disclaimer, and `DisclaimerGate.tsx` for the mandatory first-login acceptance gate (`User.disclaimer_accepted_at`, checked in `App.tsx`'s `ProtectedRoute`) — don't remove or make either bypassable
- **Logo**: `Logo.tsx` animated SVG — `viewBox` is tightly cropped to the actual drawn content (text + waveform), not the original oversized template box; don't widen it back or `justify-center` placements (mobile header, `AdminModal`) will drift off-center again
- **API prefix**: All modules must import `BASE_PATH` from `api.ts`, not define their own
- **Mobile viewport height**: use `dvh` (dynamic viewport height), not `vh`, for anything meant to fill the screen/a dialog (`Recorder.tsx`, `AdminModal.tsx`, `Dashboard.tsx`'s root). Mobile browsers resize `100vh` when the address bar shows/hides, causing clipping or forced page-scroll that `dvh` avoids
- **Flex children that must scroll internally** (e.g. `Sidebar.tsx`'s recordings `ScrollArea`) need `min-h-0` — a `flex-1` child otherwise refuses to shrink below its content's natural height and overflows the parent instead of scrolling
- **AdminModal nav**: "Dienste" tab has Whisper/ASR + LLM sub-tabs. "Audio" tab (`AudioConfig.tsx`) holds the audio-download settings. "Authentifizierung" tab has LDAP + OIDC/SSO sub-tabs. Whisper config tab grid columns depend on `live_backend` value (`grid-cols-3` vs `grid-cols-4`) — the "Qualität" tab only exists when `live_backend === 'api'`.

## Python Style (enforced by ruff)

Config in `pyproject.toml` — rules: `E, F, I, D` (PEP8 + isort + pydocstyle), Google docstrings, line length 88. Standard 3-group imports with blank lines (`# Standard library` / `# Third-party` / `# Custom`), `snake_case` for functions/variables, `PascalCase` for classes, type hints + Google docstrings.

The `known-first-party` in `pyproject.toml` still says `["dein_projektname"]` (template placeholder) — `ruff` ignores the missing local module during formatting, but if it ever blocks sorting, change it to `["backend"]`.