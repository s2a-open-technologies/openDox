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

# Build + push all three Docker images to the registry (uses bump_version.py --current)
./docker_buid_pull.sh
```

No automated tests exist in this repo. No CI workflows configured.

## Entrypoints & Wiring

- **Backend**: `main.py` → `backend/run.py:create_app()` — auto-runs Alembic on startup, mounts SPA static files
- **Routers**: `run.py` includes `record_bp`, `auth_bp`, `oidc_bp`, `settings_bp` — all under `router_prefix` (ROOT_PATH or empty). `oidc_bp` is imported in `auth_api/__init__.py` and registered separately in `run.py`.
- **Frontend**: `frontend/src/main.tsx` — path alias `@/` → `src/`, build output → `../backend/static` (NOT `frontend/dist`)
- **Parakeet server**: `parakeet_server/main.py` — standalone FastAPI, OpenAI-compatible `/v1/audio/transcriptions`, port 5001
- **Whisper server**: `whisper_server/app.py` — standalone, OpenAI-compatible, port 9000 in container
- **Env loading**: `backend/components/modules/env.py` — `env_or_file()` + `load_dotenv(override=True)` at import time. Every `{VAR}_FILE` suffix reads from file (Docker secrets)
- **Model registration**: `backend/components/models/__init__.py` imports every SQLModel table — Alembic autogenerate only sees models imported there. Add new models to both the file and `__all__`.

## Architecture

### Two-Stage ASR

| Stage | Backend | Purpose |
|---|---|---|
| **Live** | Parakeet (CPU, onnx-asr) | Near-real-time WebSocket transcription with punctuation |
| **Final** | Whisper (GPU, faster-whisper) | High-quality re-transcription of full audio |

- `asr_factory.py` creates `OpenAICompatibleBackend` instances based on `live_backend` setting (`"parakeet"` / `"api"` / `"disabled"`)
- When `live_backend="parakeet"` and `live_api_endpoint` is None, factory falls back to `PARAKEET_API_ENDPOINT` env var
- Parakeet live text is sent directly to frontend — no LLM correction (Parakeet already outputs punctuation)
- Whisper live text goes through batch LLM correction (`chunk_correction_service.py`, flushes every 5 chunks)

### PII Sanitizer (EntityGuard)

See `docs/pii.md` for the full flow. Summary:

1. `background_transcription_service.py` runs Whisper on the full audio → `record.content` (real names, encrypted at rest).
2. If sanitizer enabled (`sanitizing_service.py`), text is POSTed to the configured sanitizer endpoint, which returns `sanitized_text` (tokens like `[PERSON_1]`) and ideally a `mapping` dict.
3. If no `mapping` returned, `_extract_mapping()` falls back to word-level `difflib.SequenceMatcher` diff — best-effort, skips ambiguous adjacent tokens rather than risk wrong attribution. Result stored encrypted in `record.pii_mapping`.
4. The LLM only sees `sanitized_text` + `PRESERVE_TOKENS_INSTRUCTION` → `summary_anonymized`.
5. `reinject()` string-replaces tokens back to real names → `record.summarize` (real names, encrypted).

Configured via Admin UI → LLM settings → PII-Sanitizer. `sanitizer_endpoint` is a **full URL** (no path auto-appended), so it must include the complete sanitize route (e.g. `http://entityguard:9500/api/v1/sanitize`). Tokens must be unique per occurrence (e.g. `PERSON_1`/`PERSON_2`) — both the `mapping` dict and the diff fallback key on the literal token string, so a repeated token across two different entities silently collides.

### App Version

`pyproject.toml`'s `[project].version` is the single source of truth for the whole app (frontend + backend ship in one Docker image). `backend/run.py:_read_app_version()` reads it at startup and sets `FastAPI(title="openDox", version=...)` (shows up in `/docs`) plus a public `GET /api/version` route. Bump with `scripts/bump_version.py` (see Dev Commands) — never hand-edit the version in `pyproject.toml`/`frontend/package.json` separately, the lockfile needs `npm install --package-lock-only` to resync.

### Authentication

Three methods, layered in this order in `auth_routes.py:login()`:

1. **Local DB** — bcrypt-hashed password in `User.hashed_password`.
2. **LDAP** — `LdapSettingsModel` with optional `search_filter` (group restriction). `ldap.py:authenticate()` ANDs the filter with `(user_dn=username)`. Users are auto-provisioned on first successful login (empty password hash).
3. **OIDC (SSO)** — `oidc_bp` (`/api/v1/auth/oidc/{login,callback,status}`). Authorization Code Flow with discovery (`{provider_url}/.well-known/openid-configuration`). State is signed with `SECRET_KEY` via `itsdangerous.URLSafeSerializer` and stored in a short-lived cookie. The callback issues local JWT tokens and redirects to `/login?access_token=...&refresh_token=...` — the frontend (`Login.tsx`) extracts them from the query string and stores in localStorage. `OidcSettingsModel.admin_groups` (comma-separated) maps OIDC groups → `is_superuser=True`. Users are auto-provisioned on first login. OIDC button in `Login.tsx` only shows when `/oidc/status` returns `{"enabled": true}`.

OIDC depends on `itsdangerous` (added to `pyproject.toml`) and reuses `httpx` + `python-jose` for token exchange and id_token verification against the provider JWKS.

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

Audio files (PCM + intermediate WAV) live in `chunks/` and are cleaned up via three mechanisms — all automatic, no manual intervention needed:

1. **Finalize** (`record.py:finalize()`): `finally` block deletes both `session_*.pcm` and `session_*.wav` regardless of whether transcription succeeded. `background_transcription_task` also deletes the WAV on success (redundant, harmless).
2. **Stale-session loop** (`run.py:lifespan`): background task runs every 10 min, calls `session_store.cleanup_stale_sessions(30)` — removes sessions inactive for >30 min (browser closed without "Stop") and their PCM files.
3. **Startup cleanup** (`run.py:lifespan`): on app start, all `chunks/session_*.pcm` and `chunks/session_*.wav` files are removed — crash recovery for files left from a previous run.

The lifespan handler (`contextlib.asynccontextmanager`) cancels the cleanup loop on shutdown for a graceful exit. `/upload-chunk` endpoint was removed (unused, leaked `.webm` files).

### Field Encryption

`field_encryption.py` — uses `ENCRYPTION_KEY` env var (Fernet). Required for encrypted patient data. If not set, encryption is silently disabled.

## Docker Layout

- **`docker-compose.yml` (repo root)** — full stack: postgres + redis + whisper (GPU, internal port 5002) + parakeet + app. All build contexts are `.` (repo root) with explicit `dockerfile:` paths (`whisper_server/Dockerfile`, `parakeet_server/Dockerfile`, `Dockerfile`).
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
- `REDIS_URL` — Redis URL for session store (if empty, falls back to in-memory)
- `ROOT_PATH` — sub-path deployment prefix (empty for root)
- `VITE_ROOT_PATH` — Vite dev-only fallback for `api.ts`; should mirror `ROOT_PATH`

OIDC and LDAP settings live in the DB (`OidcSettingsModel`, `LdapSettingsModel`), not env vars. OIDC redirect URI is built from the incoming request (`X-Forwarded-Proto`/`Host` + `ROOT_PATH`), so it works behind reverse proxies without extra config.

## Gotchas

- **Dev server**: Always `python -m uvicorn main:app`, never `uv run main.py`
- **SPA routing**: `SPAStaticFiles` in `run.py` falls back to `index.html` for 404s, but `/api/` routes are not static — they're matched by the router first
- **WebSocket**: Uses `BASE_PATH` from `api.ts` + `window.location.host`. Vite proxy has `ws: true`
- **Microphone**: Requires HTTPS (except localhost). `Permissions-Policy` header set in middleware
- **LLM**: Fresh `OllamaModel()` per task, not singleton — DB settings re-read each time
- **Alembic URL**: `alembic.ini` has `sqlite3:///test.sqlite3` but both `run.py` and `alembic/env.py` override it at runtime with `SQLALCHEMY_URI` — the ini value is irrelevant
- **Frontend build output**: `vite.config.ts` outputs to `../backend/static` (not `frontend/dist`). This matters for Docker builds
- **SQLite fallback**: If no `DATABASE_URI` or `SQL_*` vars are set, `db_config.py` defaults to `postgresql+psycopg2://postgres:postgres@localhost:5432/aidox` (note: DB name is `aidox`, not `opendox`)
- **ruff known-first-party**: `pyproject.toml` has `known-first-party = ["dein_projektname"]` (template placeholder) — should be `["backend"]` for correct import sorting
- **Session store mutations**: Never mutate session dicts directly in `record.py` — always use `session_store.set_live_state()`, `session_store.update_session()`, `session_store.append_audio()`. With Redis, dicts are not shared references
- **Apache reverse proxy + WebSocket**: If live transcription drops after 1-2 sentences behind Apache, `mod_proxy_wstunnel` is likely not loaded — `mod_proxy_http` lets the WS upgrade through but breaks on binary audio frames. Fix: `a2enmod proxy_wstunnel` and declare the WS `ProxyPass` for `/api/v1/records/ws/record` *before* the catch-all `ProxyPass /`. `Recorder.tsx`'s `ws.onclose` already handles unexpected disconnects (shows a toast, resets recording state).
- **`/api/health` is dead code**: `backend/views/root_view/root.py` defines `/health` and a second `/api/endpoint`, but that router is never `include_router()`'d in `create_app()`. Any request to `/api/health` silently falls through to the `SPAStaticFiles` catch-all and returns the SPA shell with a 200 — it looks like a working health check but isn't one. The real liveness/version routes are `/api/endpoint` and `/api/version`, both registered directly on `app` inside `create_app()`. Follow that same inline-registration pattern for new public root-level routes, not the unmounted `root_view` router.

## Frontend Conventions

- **UI**: shadcn/ui components in `src/components/ui/`
- **Toaster**: `<Toaster />` from `sonner` is mounted once in `App.tsx`. Call `toast.success()`/`toast.error()` anywhere — it won't render without this.
- **State**: `useAuth()` from `AuthContext.tsx` is source of truth. NEVER hardcode `userId="1"`
- **Disclaimer**: "Kein Medizinprodukt" required in recording dialog AND transcript view. See `DISCLAIMER.md` (repo root) for the full operator/regulatory disclaimer, and `DisclaimerGate.tsx` for the mandatory first-login acceptance gate (`User.disclaimer_accepted_at`, checked in `App.tsx`'s `ProtectedRoute`) — don't remove or make either bypassable
- **Logo**: `Logo.tsx` animated SVG — `viewBox` is tightly cropped to the actual drawn content (text + waveform), not the original oversized template box; don't widen it back or `justify-center` placements (mobile header, `AdminModal`) will drift off-center again
- **API prefix**: All modules must import `BASE_PATH` from `api.ts`, not define their own
- **Mobile viewport height**: use `dvh` (dynamic viewport height), not `vh`, for anything meant to fill the screen/a dialog (`Recorder.tsx`, `AdminModal.tsx`, `Dashboard.tsx`'s root). Mobile browsers resize `100vh` when the address bar shows/hides, causing clipping or forced page-scroll that `dvh` avoids
- **Flex children that must scroll internally** (e.g. `Sidebar.tsx`'s recordings `ScrollArea`) need `min-h-0` — a `flex-1` child otherwise refuses to shrink below its content's natural height and overflows the parent instead of scrolling
- **AdminModal nav**: "Dienste" tab has Whisper/ASR + LLM sub-tabs. "Authentifizierung" tab has LDAP + OIDC/SSO sub-tabs. Whisper config tab grid columns depend on `live_backend` value (`grid-cols-3` vs `grid-cols-4`) — the "Qualität" tab only exists when `live_backend === 'api'`.

## Python Style (enforced by ruff)

Config in `pyproject.toml` — rules: `E, F, I, D` (PEP8 + isort + pydocstyle), Google docstrings, line length 88.

### Imports — 3 groups with blank lines

```python
# Standard library
import os
from typing import Optional

# Third-party
from fastapi import FastAPI
from sqlmodel import Session

# Custom (local modules)
from backend.components.models.user_model import User
```

### Functions — type hints + Google docstrings

```python
def process_data(data: dict[str, str], threshold: float = 0.5) -> list[int]:
    """Process data and filter by threshold.

    Args:
        data: Dictionary with source data.
        threshold: Filter threshold. Defaults to 0.5.

    Returns:
        List of IDs passing the filter.

    Raises:
        ValueError: If input dictionary is empty.
    """
```

- `snake_case` for functions/variables, `PascalCase` for classes
- Always annotate return types (including `-> None`)