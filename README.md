# openDox

**Medical transcription platform** – Audioaufnahmen transkribieren, kategorisieren und per LLM zusammenfassen. AGPL-3.0-or-later.

## Überblick

openDox ist eine webbasierte Plattform für die medizinische Dokumentation. Ärzte und medizinisches Fachpersonal können Audioaufnahmen (z. B. Patienten-Anamnesen) aufzeichnen, automatisch transkribieren, korrigieren und von einem externen Sprachmodell (LLM) zusammenfassen lassen.

**Wichtig:** openDox ist **kein Medizinprodukt** (Abgrenzung zur MDR: [`docs/zweckbestimmung.md`](docs/zweckbestimmung.md)). Alle maschinell erstellten Texte müssen von qualifiziertem Personal überprüft werden. Wer eine eigene Instanz betreibt, trägt die Verantwortung für regulatorische Konformität in der eigenen Jurisdiktion — siehe [`DISCLAIMER.md`](DISCLAIMER.md).

## Stack

| Schicht | Technologie |
|---------|-------------|
| **Backend** | Python 3.12+, FastAPI, SQLModel, Alembic |
| **Frontend** | React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS |
| **Transkription** | Zweistufig: Live per Parakeet (VAD-Streaming über WebSocket), final per Whisper (faster-whisper, OpenAI-kompatible API); beide als Docker-Services mitgeliefert |
| **Oberfläche** | Mehrsprachig (Deutsch/English, `i18next`), Sprache pro Nutzer |
| **Desktop-Client** | Optional: separater openDox-Client (Go/Wails), Verteilung und Richtlinie im Admin-Bereich, siehe [`docs/client.md`](docs/client.md) |
| **Zusammenfassung** | Externes LLM via LangChain/OpenAI-kompatible API |
| **Datenbank** | PostgreSQL (Docker) oder SQLite (Fallback) |
| **Auth** | JWT (python-jose + bcrypt), optional LDAP (inkl. Gruppen-Rollenmapping) oder OIDC/SSO |
| **Objektspeicher** | S3-kompatibel (self-hosted Garage per Default, austauschbar) für persistierte Audio-Downloads |

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
- **App**: http://localhost:20000 (Port über `APP_PORT` konfigurierbar)

PostgreSQL, Redis, Whisper, Parakeet und der Objektspeicher (Garage) sind nur intern im Docker-Netzwerk erreichbar, nicht direkt vom Host aus.

Login mit dem seeded Admin-User:
- Benutzer: `admin`
- Passwort: `admin`

### Produktion (Docker Swarm)

Für einen gehärteten Produktions-Deploy (echte Secrets statt Klartext-Defaults, GPU-Placement, versionsfixierte Images) gibt es `docker-swarm.yml` statt `docker-compose.yml`:

```bash
docker swarm init                        # einmalig pro Manager-Node
./create_docker_secrets.sh                # einmalig — erzeugt alle benötigten Secrets
export OPENDOX_VERSION=$(python3 scripts/bump_version.py --current)
./docker_build_push.sh
docker stack deploy -c docker-swarm.yml opendox
```

Details (Secrets-Handling, GPU-Scheduling unter Swarm, Key-Rotation) siehe Kommentare in `docker-swarm.yml` und `AGENTS.md`.

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
# Vite schreibt den Build direkt nach ../backend/static/ (kein separater Kopierschritt)
```

## Architektur

### Transkriptions-Pipeline

1. **Aufnahme**: Browser nimmt Audio über `MediaRecorder` + `AudioWorklet` auf
2. **Live-Transkription** (optional, pro Aufnahme abschaltbar mit `?live=0`): Audio-Frames gehen per WebSocket ans Backend und von dort an den Parakeet-Server, der per VAD segmentiert und Text mit Zeichensetzung zurückstreamt (alternativ Whisper-API in festen Chunks)
3. **Finale Transkription**: Nach Stopp der Aufnahme werden alle Audio-Chunks zu einer Datei zusammengefügt und erneut an die Whisper-API geschickt (optional mit phonetischer Fachbegriff-Korrektur und PII-Sanitizer vor dem LLM, siehe [`docs/pii.md`](docs/pii.md))
4. **LLM-Zusammenfassung**: Der transkribierte Text wird zusammen mit einem kategoriespezifischen Prompt an ein externes LLM geschickt (z. B. Ollama, vLLM, OpenAI-kompatibel)

### Kategorien

Beim Start einer Aufnahme wird eine medizinische Kategorie gewählt (z. B. Kardiologie, Orthopädie). Jede Kategorie hat einen eigenen System-Prompt für das LLM, einen kurzen Whisper-Prompt (Schreibweisen) und ein Korrektur-Glossar für Fachbegriffe; optional kann sie ein eigenes LLM-Backend nutzen.

### Audio-Download (optional)

Nach der finalen Transkription kann eine komprimierte, verschlüsselte Kopie (MP3/OGG/FLAC/WAV) der Aufnahme für den späteren Download aufbewahrt werden (Admin-UI → „Audio"-Tab: an/aus, Bitrate, Sample-Rate). Die Datei wird client-seitig mit dem `ENCRYPTION_KEY` verschlüsselt und landet im konfigurierten S3-kompatiblen Objektspeicher, nie unverschlüsselt auf der Platte. Die rohe PCM/WAV-Aufnahme wird davon unabhängig nach erfolgreicher Transkription gelöscht (DSGVO-Datenminimierung); bei einem Fehlschlag bleibt sie für einen Retry erhalten und wird nach `FAILED_AUDIO_RETENTION_DAYS` (Standard 3) verschlüsselt in den Objektspeicher archiviert.

### Static Files

- Statische Assets (Logos, Icons) liegen in `frontend/public/`
- `vite.config.ts` schreibt den Build-Output direkt nach `../backend/static/` (kein `frontend/dist/`-Zwischenschritt)
- `backend/static/` ist in `.gitignore` (wird beim Frontend-Build generiert)
- FastAPI mountet `StaticFiles` auf `/` mit `html=True` für SPA-Routing

### Docker-Secrets

Sensible Werte können via `{VAR}_FILE` aus Dateien gelesen werden (z. B. `SECRET_KEY_FILE=/run/secrets/secret_key`) — Grundlage für den Docker-Swarm-Produktionspfad (siehe oben), wo `create_docker_secrets.sh` alle Secrets anlegt und `docker-swarm.yml` sie über diese Konvention einbindet.

## Konfiguration

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `SQL_USER` / `SQL_PASS` / `SQL_HOST` / `SQL_PORT` / `SQL_DB` | PostgreSQL-Komponenten | postgres/postgres/localhost/5432/aidox |
| `DATABASE_URI` | Volle DB-URI (überschreibt Komponenten, z.B. `sqlite:///test.sqlite3`) | – |
| `SECRET_KEY` | JWT-Signing-Key. Nicht gesetzt = zufällig generiert pro Prozessstart (invalidiert Sessions bei jedem Neustart) statt unsicherem Fallback | – |
| `ALGORITHM` | JWT-Algorithmus | `HS256` |
| `ENCRYPTION_KEY` | Fernet-Key für verschlüsselte Patientendaten (DSGVO/§203 StGB) | – (Verschlüsselung deaktiviert wenn leer) |
| `CORS_ALLOWED_ORIGINS` | Komma-getrennte erlaubte CORS-Origins | – (alle erlaubt, loggt Warnung) |
| `TRUSTED_PROXY_IPS` | IPs, die `X-Forwarded-Proto`/`-Host` setzen dürfen (OIDC-Redirect) | – (Auto-Erkennung: Loopback + Docker-Gateway) |
| `CLIENT_SERVER_URL` | Server-Adresse, die in die `settings.json` des Desktop-Clients geschrieben wird (Admin → Clients) | – (aus der Anfrage des Admins abgeleitet, inkl. `ROOT_PATH`) |
| `CLIENT_DOWNLOAD_BASE_URL` | Basis-URL der Installer-Downloads im Admin-Bereich | neuestes GitHub-Release von `opendox-client` |
| `WHISPER_API_ENDPOINT` | Whisper-API-URL (Fallback, wenn keine DB-Settings gesetzt sind) | `http://localhost:9100/v1` |
| `WHISPER_API_KEY` | Whisper-API-Key | `loc-123` |
| `FAILED_AUDIO_RETENTION_DAYS` | Tage, bis Audio fehlgeschlagener Transkriptionen in den Objektspeicher archiviert wird | `3` |
| `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | S3-kompatibler Objektspeicher für Audio-Downloads | zeigt im Docker-Compose-Stack auf den mitgelieferten `garage`-Service |

Vollständige Liste inkl. Kommentaren: [`.env.example`](.env.example).

## Tests

```bash
pytest tests/                  # Backend
cd frontend && npm run test    # Frontend (vitest)
ruff check . && ruff format --check .
```

CI (`.github/workflows/ci.yml`) führt beides bei jedem Push/PR auf `master` aus.

## Datenbank-Migrationen

Nach Änderungen an SQLModel-Tabellen:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Im Docker-Image laufen Migrationen automatisch vor dem App-Start (`entrypoint.sh: alembic upgrade head`).

## Wichtige Dateien

| Datei | Rolle |
|-------|-------|
| `main.py` | Entrypoint: `uvicorn main:app` |
| `backend/run.py` | App-Factory: CORS/Proxy-Trust-Middleware, StaticFiles, Admin-Seed |
| `backend/components/sql/db_config.py` | Zentrale DB-URI (PostgreSQL oder SQLite) |
| `backend/components/services/asr_factory.py` | ASR-Backend-Factory |
| `backend/components/services/background_transcription_service.py` | Finale Transkription + LLM-Summary + Audio-Persistierung |
| `backend/components/services/audio_storage.py` | S3-Client für persistierte Audio-Downloads |
| `docker-swarm.yml` / `create_docker_secrets.sh` | Produktions-Deploy (Docker Swarm) mit echten Secrets |
| `AGENTS.md` (auch als `CLAUDE.md` verlinkt) | Detaillierte Entwickler-Dokumentation |

## Dokumentation und Governance

| Dokument | Inhalt |
|----------|--------|
| [`docs/zweckbestimmung.md`](docs/zweckbestimmung.md) | Bestimmungsgemäßer Zweck, Abgrenzung zur MDR |
| [`DISCLAIMER.md`](DISCLAIMER.md) | Kein-Medizinprodukt- und Haftungshinweis |
| [`docs/data-mapping.md`](docs/data-mapping.md) | Datenflüsse, Verschlüsselung, Aufbewahrung (Ausgangspunkt für Art. 30 DSGVO) |
| [`docs/pii.md`](docs/pii.md) | PII-Sanitizer (EntityGuard) |
| [`docs/audit-checklist-opendox.md`](docs/audit-checklist-opendox.md) | Selbstauskunft für Audits, mit Fundstellen und offenen Lücken |
| [`docs/hospital-audit-frameworks.md`](docs/hospital-audit-frameworks.md) | Einordnung gegen ISO 27001, BSI, NIS2, CRA, MDR, DSGVO |
| [`docs/client.md`](docs/client.md) | Desktop-Client |
| [`docs/opendox.md`](docs/opendox.md) | Ausführliche Gesamtdokumentation |
| [`SECURITY.md`](SECURITY.md) | Meldeweg für Schwachstellen, technische Maßnahmen (Art. 32) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), [`CHANGELOG.md`](CHANGELOG.md) | Mitarbeit, Verhaltenskodex, Änderungen |

Releases entstehen nur auf Anweisung des Maintainers (Tag `vX.Y.Z` löst den Release-Workflow aus); SBOMs (CycloneDX) pro Image erzeugt der manuelle Docker-Publish-Workflow.

## Lizenz

**AGPL-3.0-or-later**

Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

Dieses Programm ist freie Software. Details siehe `LICENSE`.

---

*Kein Medizinprodukt.*
