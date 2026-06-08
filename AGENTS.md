# Projekt Red / openDox: Agent Guide

Medical transcription platform. **License: AGPL-3.0-or-later**, Author: `crizz <christopher.abanilla@gmx.de>`.

## Stack
- **Backend**: Python 3.12+, FastAPI, SQLModel, Alembic, `uv` package manager
- **Frontend**: React 18 + TypeScript + Vite + shadcn/ui + Tailwind CSS
- **AI**: External OpenAI-compatible Whisper API (local Docker), external LLM via LangChain/OpenAI
- **Auth**: JWT (`python-jose` + `passlib` bcrypt), optional LDAP
- **DB**: PostgreSQL (Docker) or SQLite fallback (`test.sqlite3`)

## Project Structure (current)
```
├── main.py                 # Entry point: uvicorn main:app --port 5000
├── config.py               # env_or_file() supports {VAR}_FILE Docker secrets
├── backend/
│   ├── run.py              # create_app(): mounts /static, runs Alembic, seeds admin
│   ├── views/              # API routers: auth_api, record_api, settings_api, root_view
│   ├── components/
│   │   ├── models/         # SQLModel tables + Pydantic schemas
│   │   ├── services/       # ASR factory, LLM, settings, LDAP, task service
│   │   │   └── asr_backends/   # openai_compatible.py, disabled.py (no local Whisper)
│   │   ├── sql/            # sql_engine.py, db_config.py (PostgreSQL or SQLite)
│   │   ├── llm/            # llm_model.py (OllamaModel = ChatOpenAI wrapper)
│   │   └── security/       # JWT create/decode, bcrypt hashing
│   └── alembic/            # Managed migrations (replaces create_db_and_tables)
├── frontend/               # Vite React app, shadcn/ui components
├── docker-compose.yml      # postgres + whisper + app
├── Dockerfile              # Multi-stage: frontend build → Python backend + static files
└── pyproject.toml          # uv deps, no torch/whisper packages (externalized)
```

## Critical Paths
- **Static files**: `backend/run.py` mounts `./static` → `app.mount("/static", StaticFiles(directory="static"), ...)`. Dockerfile copies `frontend/dist` to `/app/static/`.
- **App factory**: `backend.run.create_app()` is the ONLY valid entrypoint. Do NOT use `app/run.py` (old path, deleted).
- **DB migrations**: Alembic runs on startup via `create_app()` → `_run_alembic_migrations()`. Seed data (admin user, default categories, LLM defaults) is in the initial Alembic revision. After model changes, run `alembic revision --autogenerate && alembic upgrade head`.

## Developer Commands

### Backend
```bash
# Dev server (hot reload) — use module syntax, NOT `uv run main.py`
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Alembic (manual)
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "desc"   # new migration
```

### Frontend
```bash
cd frontend/
npm install
npm run dev        # Vite dev server (port 3000/3001)
npm run build      # Outputs to frontend/dist
npm run lint       # ESLint
```

### Full Stack (two terminals)
```bash
# Terminal 1
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Terminal 2
cd frontend && npm run dev
```

### Docker (production-like)
```bash
docker compose up --build
# Services: postgres (5432), whisper (9000), app (5000)
```

## Environment / Config
- **`.env`**: Copy from existing file. Key vars:
  - `SQL_USER`, `SQL_PASS`, `SQL_HOST`, `SQL_PORT`, `SQL_DB` → built into `postgresql+psycopg2://` URI by `db_config.py`
  - `DATABASE_URI` overrides components (e.g. `sqlite3:///test.sqlite3`)
  - `SECRET_KEY`, `ALGORITHM` → JWT signing
  - `_FILE` suffix on any env var reads from a file (Docker secrets)

## Auth & User Isolation
- **Login**: `POST /api/v1/auth/login` → `{access_token, refresh_token}`
- **Token storage**: `localStorage.getItem("access_token")` (managed by `AuthContext.tsx`)
- **User ID**: Frontend fetches `/api/v1/auth/me` on mount to get real `user.id`. NEVER hardcode `userId="1"`.
- **Record isolation**: `GET /api/v1/records/list-records/{user_id}` filters by user. Dashboard must pass the authenticated user's ID.

## ASR / Transcription Architecture
- **No local Whisper**. Only external API backends:
  - `OpenAICompatibleBackend` (`openai_compatible.py`): Sends WAV to API endpoint
  - `DisabledBackend` (`disabled.py`): Returns empty string (live transcript hidden in UI)
- **Factory**: `asr_factory.py` → `get_live_backend()` (3s chunks, beam=1) / `get_final_backend()` (full file, beam=5)
- **Live loop**: WebSocket in `record.py` accumulates audio chunks, calls backend when buffer >= `chunk_length_s`
- **Final processing**: `background_transcription_service.py` runs Whisper → LLM summarization in background thread. Task status tracked in DB.

## LLM Setup (commonly broken)
- **Settings table**: `LlmSettingsModel` (NOT `WhisperSettingsModel`)
- **Load function**: `get_llm_settings()` in `settings_service.py`
- **Client**: `OllamaModel` class in `llm_model.py` wraps `ChatOpenAI` from `langchain-openai`
- **Fresh instance**: `background_transcription_service.py` creates a NEW `OllamaModel()` per task (picks up latest settings). Do NOT use a module-level singleton.

## Frontend Conventions
- **Path alias**: `@/` maps to `src/`
- **UI library**: shadcn/ui (Radix + Tailwind). Custom components added manually under `src/components/ui/`
- **State**: `useAuth()` from `AuthContext.tsx` is the source of truth for current user
- **Disclaimer**: "Kein Medizinprodukt" banner required in recording dialog AND above transcript view

## Build & Deploy
- **Production build**: `npm run build` in frontend, then `docker compose up --build`
- **Old script**: `compile_and_push.py` exists but has a hardcoded Node path and is deprecated in favor of Docker

## Git / License
- **License**: AGPL-3.0-or-later. All source files have the standard header. `LICENSE` and `AUTHORS` files present.
- **Do NOT modify license without explicit user confirmation**.

## Known Gotchas
- **Dev server startup**: `uv run main.py` causes `create_app()` to run twice and uvicorn silently hangs. **Always use `python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000`**.
- **Whisper settings env fallback**: `settings_service.py` reads `WHISPER_API_ENDPOINT` / `WHISPER_API_KEY` from `.env` **only when the DB values are `None`**. If the DB already has stale entries, either clear them in the DB or update the Settings UI.
- **Whisper port collision**: Port `9000` is commonly occupied (e.g., Jupyter). The `docker-whisper.yml` maps `9100:9000`; update `WHISPER_API_ENDPOINT` in `.env` accordingly (e.g., `http://localhost:9100/v1`).
- **`uv.lock` was deleted**; `uv pip install --system -r pyproject.toml` regenerates it. Do NOT commit a stale lockfile.
- **WebSocket in dev**: Frontend uses `window.location.host` for WebSocket URL. Vite proxy (`vite.config.ts`) is configured with `ws: true` for WebSocket proxying to port 5000.
- **DB model changes**: After any `SQLModel` change, run `alembic revision --autogenerate -m "desc" && alembic upgrade head`. The `create_app()` factory auto-runs Alembic on startup, but a new revision must exist first.
- **Frontend build**: `npm run dev` (port 3000) and `npm run build` → `frontend/dist`. No test runner configured; manual verification only.
- **CORS**: Wide-open (`allow_origins=["*"]`) in dev; tighten for production.
- **Static files**: `backend/run.py` mounts `./static`. In Docker, `frontend/dist` is copied to `/app/static/`.
- **Logo SVG**: `frontend/src/components/Logo.tsx` contains an animated SVG that relies on `width`/`height` attributes. Do not remove them — the animation uses the viewBox and the text path.
- **Task ID link**: The `Record` model has a `task_id` column (added in migration `560287c845a5`) that links to the `Task` table. This allows the frontend to poll task status even when the WebSocket `finished` event is missed.
- **`localStorage` session persistence**: `currentSession` is cleared on logout to prevent cross-user leakage.
