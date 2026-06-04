# Projekt Red: Agent Guide

Medical transcription platform with FastAPI backend and React frontend.

## Stack
- **Backend**: Python 3.12+, FastAPI, SQLModel, uv (package manager)
- **Frontend**: React + TypeScript + Vite + shadcn/ui + Tailwind CSS
- **AI**: Whisper (faster-whisper, openai-whisper), LangChain, PyTorch
- **Auth**: JWT + LDAP support

## Project Structure
```
├── main.py                 # Entry point (port 5000)
├── app/
│   ├── run.py             # App factory, seeds admin user
│   ├── views/             # API routes (auth_api, record_api, settings_api)
│   ├── components/        # Business logic (services, models, security, sql)
│   └── static/            # Built frontend (copied from frontend/dist)
├── frontend/              # React app (Vite + shadcn/ui)
├── config.py              # Config via env or {VAR}_FILE
└── pyproject.toml         # uv-based dependencies
```

## Backend Commands
```bash
# Run dev server (hot reload)
uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Alternative (script uses gunicorn)
source .venv/bin/activate && gunicorn main:app --reload --bind 0.0.0.0:5000
```

## Frontend Commands
```bash
cd frontend/
npm install
npm run dev      # Vite dev server
npm run build    # Outputs to frontend/dist
npm run lint     # ESLint
```

## Full Stack Dev
```bash
# Terminal 1: Backend
uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Terminal 2: Frontend
cd frontend && npm run dev
```

## Build & Deploy
```bash
# Compile frontend and copy to app/static/
python compile_and_push.py

# Note: Script has hardcoded Node path: /home/crizz/.nvm/versions/node/v22.18.0/bin/node
```

## Environment Setup
- Copy `.env` format from existing file
- Required: `DATABASE_URI` (PostgreSQL) or defaults to SQLite `test.sqlite3`
- `SECRET_KEY`, `ALGORITHM`, token expiry settings

## Key Conventions

### Backend
- **App factory**: `app/run.py:create_app()` - initializes logging, DB, seeds admin
- **Auto-seed**: Admin user created at startup (username: `admin`, password: `admin`)
- **DB**: SQLModel with `create_db_and_tables()` on startup
- **APIs**: Router-based in `app/views/*_api/`
- **Config**: `env_or_file()` supports `{VAR}_FILE` for Docker secrets

### Frontend
- **UI**: shadcn/ui components (Radix + Tailwind)
- **Path alias**: `@/` maps to `src/`
- **Lovable**: Project linked to lovable.dev - changes pushed there reflect in repo
- **Styling**: Tailwind with CSS variables, dark mode via `next-themes`

### Data/Artifacts
- Generated at runtime: `logs/`, `chunks/`, `models_cache/`, `*.sqlite3`
- Git-ignored: `__pycache__/`, `.venv/`, `node_modules/`, `model/`, `image/`

## Whisper/Transcription
- Supports multiple backends: `faster-whisper`, `openai-whisper`
- Models cached in `models_cache/`
- Audio processing via `torchaudio`, `soundfile`, `webrtcvad`

### ASR Backend Architecture
The transcription system now supports pluggable backends via `app/components/services/asr_backends/`:

- **FasterWhisperBackend** (`faster_whisper.py`): Local whisper on GPU/CPU
- **OpenAICompatibleBackend** (`openai_compatible.py`): API endpoints (vLLM, OpenRouter, etc.)
- **DisabledBackend** (`disabled.py`): No transcription (for testing)

Settings control which backend is used:
```python
# GET/PUT /whisper-settings/
{
    "live_backend": "local|api|disabled",
    "live_model_size": "large-v3-turbo",
    "live_device": "cuda",
    "live_api_endpoint": "http://localhost:8000/v1",
    "live_api_key": "...",
    "final_backend": "local|api",
    "final_model_size": "large-v3",
    # ... (see WhisperSettingsModel)
}
```

Factory: `app/components/services/asr_factory.py`
- `get_live_backend()`: Near-live transcription (3s chunks, beam_size=1)
- `get_final_backend()`: Final transcription (full file, beam_size=5)

## Testing Notes
- No explicit test runner configured
- For transcription: ensure `chunks/` dir exists (runtime-created)
- LDAP integration requires separate LDAP server config in settings
