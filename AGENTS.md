# openDox: Agent Guide

Medical transcription platform. **License: AGPL-3.0-or-later**, Author: `Christopher Abanilla <christopher.abanilla@gmx.de>`.

## Dev Commands

```bash
# Backend — only valid entrypoint; never `uv run main.py` (causes double init)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Frontend
cd frontend && npm run dev    # port 3000, proxies /api/v1/ → localhost:5000

# DB migrations (run after any SQLModel change)
alembic revision --autogenerate -m "desc"
alembic upgrade head

# Lint (backend only, ruff config in pyproject.toml)
ruff check --fix .
ruff format .

# Full stack Docker
docker compose -f docker/docker-compose.yml up --build
```

No automated tests exist in this repo. No CI workflows configured.

## Entrypoints & Wiring

- **Backend**: `main.py` → `backend/run.py:create_app()` — auto-runs Alembic on startup, mounts SPA static files
- **Frontend**: `frontend/src/main.tsx` — path alias `@/` → `src/`, build output → `../backend/static` (NOT `frontend/dist`)
- **Parakeet server**: `parakeet_server/main.py` — standalone FastAPI, OpenAI-compatible `/v1/audio/transcriptions`, port 5001
- **Env loading**: `backend/components/modules/env.py` — `env_or_file()` + `load_dotenv(override=True)` at import time. Every `{VAR}_FILE` suffix reads from file (Docker secrets)

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

### ROOT_PATH (Sub-path Deployment)

Set `ROOT_PATH=/opendox` in `.env`. Backend injects `window.__ROOT_PATH__` into `static/index.html` at startup — **no frontend rebuild needed**. `api.ts` reads this at runtime and patches `window.fetch`. WebSocket in `Recorder.tsx` imports `BASE_PATH` from `api.ts`.

Do NOT pass `root_path=` to `FastAPI()` — it causes Starlette to strip the prefix before route matching, double-counting it. Routes are prefixed manually in `create_app()`.

For Vite dev server, set `VITE_ROOT_PATH` to match `ROOT_PATH` (both in `.env`).

### Settings Cache

`SettingsService` is a singleton with `_whisper_settings` / `_llm_settings` caches. DB values override `.env` fallbacks. After changing settings via API or DB, call `invalidate_cache()` or `reset_asr_backends()` — otherwise the app serves stale values until restart.

### Session Store

`session_store.py` — factory that selects backend based on `REDIS_URL`:
- **Redis** (production): `REDIS_URL` set → `RedisSessionStore` with TTL, persistence, multi-instance support
- **In-Memory** (fallback): no `REDIS_URL` → `SessionStore` dict, sessions lost on restart, single-instance only

PCM audio is always written to disk (`session_{id}.pcm`), never stored in Redis. Import stays `from backend.components.services.session_store import session_store` — the factory decides.

Docker Compose includes a `redis:7-alpine` service with health check. App depends on it.

### Field Encryption

`field_encryption.py` — uses `ENCRYPTION_KEY` env var (Fernet). Required for encrypted patient data. If not set, encryption is silently disabled.

## Docker Layout

- `docker/docker-compose.yml` — full stack: postgres + redis + whisper (GPU, built from `whisper_server/Dockerfile`) + parakeet + app
- `docker/docker-whisper.yml` — standalone Whisper (port 9100 → container 9000), also uses local `whisper_server/Dockerfile`
- `docker/docker-parakeet.yml` — standalone Parakeet (port 9200 → container 5001)
- **`docker/parakeet-server/` is empty** — `docker-compose.yml` build context `./docker/parakeet-server` must be changed to `../parakeet_server` (where `Dockerfile` and `main.py` actually live)
- Whisper port is `9100:9000` (9000 conflicts with Jupyter)

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
- `VITE_ROOT_PATH` — must mirror `ROOT_PATH` for Vite dev server proxy

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

## Frontend Conventions

- **UI**: shadcn/ui components in `src/components/ui/`
- **State**: `useAuth()` from `AuthContext.tsx` is source of truth. NEVER hardcode `userId="1"`
- **Disclaimer**: "Kein Medizinprodukt" required in recording dialog AND transcript view
- **Logo**: `Logo.tsx` animated SVG — don't remove `width`/`height` attributes
- **API prefix**: All modules must import `BASE_PATH` from `api.ts`, not define their own

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