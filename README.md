# openDox

**Medical transcription platform** – Audioaufnahmen transkribieren, kategorisieren und per LLM zusammenfassen. AGPL-3.0-or-later.

## Überblick

openDox ist eine webbasierte Plattform für die medizinische Dokumentation. Ärzte und medizinisches Fachpersonal können Audioaufnahmen (z. B. Patienten-Anamnesen) aufzeichnen, automatisch transkribieren, korrigieren und von einem externen Sprachmodell (LLM) zusammenfassen lassen.

**Wichtig:** openDox ist **kein Medizinprodukt** gemäß MPG. Alle maschinell erstellten Texte müssen von qualifiziertem Personal überprüft werden.

## Stack

| Schicht | Technologie |
|---------|-------------|
| **Backend** | Python 3.12+, FastAPI, SQLModel, Alembic |
| **Frontend** | React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS |
| **Transkription** | Externe OpenAI-kompatible Whisper-API (Docker) |
| **Zusammenfassung** | Externes LLM via LangChain/OpenAI-kompatible API |
| **Datenbank** | PostgreSQL (Docker) oder SQLite (Fallback) |
| **Auth** | JWT (python-jose + bcrypt), optional LDAP |

## Schnellstart (Docker)

Die schnellste Möglichkeit, das gesamte System lokal zu starten:

```bash
# Repository klonen
git clone https://github.com/daemolition/openDox.git
cd openDox

# Environment konfigurieren (optional)
cp .env.example .env

# Alles bauen und starten
docker compose up --build
```

Services:
- **App**: http://localhost:5000
- **Whisper API**: http://localhost:9000
- **PostgreSQL**: localhost:5432

Login mit dem seeded Admin-User:
- Benutzer: `admin`
- Passwort: `admin`

## Entwicklung (ohne Docker)

### Voraussetzungen
- Python 3.12+
- `uv` (Python-Paketmanager)
- Node.js 22+
- PostgreSQL (oder SQLite als Fallback)

### Backend starten

```bash
# Abhängigkeiten installieren
uv pip install --system -r pyproject.toml

# Datenbank-Migrationen anwenden
alembic upgrade head

# Dev-Server mit Hot-Reload
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

**Wichtig:** Immer `python -m uvicorn main:app` verwenden, niemals `uv run main.py` (verursacht doppelte Initialisierung).

### Frontend starten

```bash
cd frontend/
npm install
npm run dev
```

Das Frontend ist dann unter http://localhost:3000 erreichbar.

### Build (für Produktion)

```bash
cd frontend
npm run build
# Kopiert automatisch nach ../static/
```

## Architektur

### Transkriptions-Pipeline

1. **Aufnahme**: Browser nimmt Audio über `MediaRecorder` + `AudioWorklet` auf
2. **Live-Transkription** (optional): Audio-Chunks werden per WebSocket an das Backend geschickt und von der Whisper-API in Echtzeit transkribiert
3. **Finale Transkription**: Nach Stopp der Aufnahme werden alle Audio-Chunks zu einer Datei zusammengefügt und erneut an die Whisper-API geschickt
4. **LLM-Zusammenfassung**: Der transkribierte Text wird zusammen mit einem kategoriespezifischen Prompt an ein externes LLM geschickt (z. B. Ollama, vLLM, OpenAI-kompatibel)

### Kategorien

Beim Start einer Aufnahme wird eine medizinische Kategorie gewählt (z. B. Kardiologie, Orthopädie). Jede Kategorie hat einen eigenen System-Prompt, der sowohl der Whisper-API (für Fachtermini) als auch dem LLM (für Zusammenfassung) übergeben wird.

### Static Files

- Statische Assets (Logos, Icons) liegen in `frontend/public/`
- Build-Output landet in `frontend/dist/` und wird nach `static/` kopiert
- `static/` ist in `.gitignore` (wird bei Docker-Build generiert)
- FastAPI mountet `StaticFiles` auf `/` mit `html=True` für SPA-Routing

### Docker-Secrets

Sensible Werte können via `{VAR}_FILE` aus Dateien gelesen werden (z. B. `SECRET_KEY_FILE=/run/secrets/secret_key`).

## Konfiguration

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `SQL_USER` / `SQL_PASS` / `SQL_HOST` / `SQL_PORT` / `SQL_DB` | PostgreSQL-Komponenten | postgres/postgres/localhost/5432/opendox |
| `DATABASE_URI` | Volle DB-URI (überschreibt Komponenten, z.B. `sqlite:///test.sqlite3`) | – |
| `SECRET_KEY` | JWT-Signing-Key | `TestintDebugKey` |
| `ALGORITHM` | JWT-Algorithmus | `HS256` |
| `WHISPER_API_ENDPOINT` | Whisper-API-URL | `http://localhost:9000/v1` |
| `WHISPER_API_KEY` | Whisper-API-Key | `loc-123` |

## Datenbank-Migrationen

Nach Änderungen an SQLModel-Tabellen:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Migrationen werden automatisch beim App-Start ausgeführt (in `backend/run.py`).

## Wichtige Dateien

| Datei | Rolle |
|-------|-------|
| `main.py` | Entrypoint: `uvicorn main:app` |
| `backend/run.py` | App-Factory: CORS, StaticFiles, Alembic-Migrationen, Admin-Seed |
| `backend/components/sql/db_config.py` | Zentrale DB-URI (PostgreSQL oder SQLite) |
| `backend/components/services/asr_factory.py` | ASR-Backend-Factory |
| `backend/components/services/background_transcription_service.py` | Finale Transkription + LLM-Summary |
| `AGENTS.md` | Detaillierte Entwickler-Dokumentation |

## Lizenz

**AGPL-3.0-or-later**

Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

Dieses Programm ist freie Software. Details siehe `LICENSE`.

---

*Kein Medizinprodukt gemäß Medizinproduktegesetz (MPG).*
