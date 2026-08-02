# openDox – Medizinische Transkriptionsplattform

> **AGPL-3.0-or-later** | Copyright (C) 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
> 
> Dieses Programm ist freie Software: Sie können es unter den Bedingungen der GNU Affero General Public License weiterverteilen und/oder modifizieren.

---

## Projektvision

**openDox** ist eine moderne, webbasierte Plattform für medizinische Transkription, entwickelt für Praxen, Kliniken und medizinische Versorgungszentren (MVZs). Die Anwendung ermöglicht medizinischem Fachpersonal die sprachgesteuerte Dokumentation von Patientendaten mittels KI-gestützter Spracherkennung und automatischer Zusammenfassung.

### Kernfeatures

- 🎤 **Zwei-Stufen-Transkription**: Parakeet (Live, CPU) + Whisper (Final, GPU)
- 🤖 **KI-Zusammenfassung**: Automatische Grammatikkorrektur und Strukturierung
- 🔐 **DSGVO-konform**: Feldweise Verschlüsselung für patientenbezogene Daten
- 🏢 **Enterprise-Ready**: LDAP-Integration, Redis-Sessions (geplant), horizontale Skalierung
- 🐳 **Cloud-Native**: Docker-basierte Deployment mit PostgreSQL

---

## Systemarchitektur

### High-Level Architektur

```mermaid
graph TB
    subgraph Frontend["React 18 Frontend (Vite)"]
        A[Recorder Component]
        B[TranscriptView]
        C[AuthContext]
        D[Settings Panels]
    end
    
    subgraph Backend["FastAPI Backend (Python 3.12)"]
        E[WebSocket Handler]
        F[REST API]
        G["Session Store<br/>(In-Memory, PCM on Disk)"]
        H[ASR Factory]
        I[Task Service]
        J[Chunk Correction Service]
    end
    
    subgraph Database["Datenbank & Cache"]
        K[(PostgreSQL 15)]
    end
    
    subgraph AIServices["KI-Services"]
        L[Whisper ASR<br/>GPU — Final]
        M[Parakeet ASR<br/>CPU — Live]
        N[Ollama LLM]
    end
    
    subgraph Enterprise["Enterprise Services"]
        O[LDAP/Active Directory]
    end
    
    A -->|WebSocket PCM| E
    A -->|HTTP Upload| F
    E --> G
    E --> H
    H -->|Live| M
    H -->|Final| L
    E -->|Whisper only| J
    F --> K
    F --> O
    I --> N
```

### Transkriptions-Pipeline (Zwei-Stufen-ASR)

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant Browser as 🌐 Browser
    participant WS as 🔌 WebSocket
    participant Parakeet as 🎤 Parakeet<br/>(CPU, Live)
    participant Whisper as 🎙️ Whisper<br/>(GPU, Final)
    participant DB as 🗄️ PostgreSQL
    participant LLM as 🤖 Ollama LLM
    
    User->>Browser: Start Recording
    Browser->>Browser: AudioWorklet (16kHz PCM)
    
    loop Every 3 seconds
        Browser->>WS: Send Audio Chunk (Float32)
        WS->>WS: Write PCM to disk (session_{id}.pcm)
        
        alt live_backend = "parakeet"
            WS->>Parakeet: Transcribe (live, batch)
            Parakeet-->>WS: Text (mit Interpunktion)
            WS-->>Browser: Update Live Transcript
            Note over WS: Kein LLM-Korrektur nötig<br/>(Parakeet liefert fertige Sätze)
        else live_backend = "api" (Whisper)
            WS->>Whisper: Transcribe (live)
            Whisper-->>WS: Partial Text (roh)
            WS->>WS: Batch-LLM-Korrektur<br/>(alle 5 Chunks)
            WS-->>Browser: Update Live Transcript
        end
    end
    
    User->>Browser: Stop Recording
    Browser->>Browser: Warte auf Uploads (MediaRecorder)
    Browser->>WS: STOP Event
    WS->>WS: PCM → WAV konvertieren
    WS->>Whisper: Transcribe (final, full quality)
    Whisper-->>WS: Complete Transcript
    WS->>DB: Store encrypted content
    WS->>LLM: Summarize with category prompt
    LLM-->>WS: Summary (Markdown)
    WS->>DB: Store encrypted summary
    WS->>WS: Audio-Datei löschen (DSGVO)
    WS-->>Browser: Final Result + Task ID
```

---

## Tech-Stack

### Backend

| Komponente | Technologie | Version | Zweck |
|------------|-------------|---------|-------|
| **Web Framework** | FastAPI | ≥0.122.0 | REST API, WebSocket |
| **ORM** | SQLModel | ≥0.0.27 | Datenbank-Mapping |
| **Migrationen** | Alembic | ≥1.15.2 | Schema-Management |
| **Datenbank** | PostgreSQL | 15 | Primärspeicher (Default-DB: `aidox`) |
| **Fallback-DB** | SQLite3 | - | Development |
| **Auth** | python-jose + bcrypt | ≥3.5.0 | JWT-Token |
| **LDAP** | ldap3 | ≥2.9.1 | Enterprise-Auth |
| **LLM-Client** | LangChain | ≥1.2.0 | LLM-Orchestrierung |
| **Live-ASR** | Parakeet (onnx-asr) | - | CPU-basierte Live-Transkription |
| **Final-ASR** | Whisper (faster-whisper) | - | GPU-basierte Final-Transkription |
| **Verschlüsselung** | cryptography (Fernet) | - | Feldweise Encryption |
| **Audio** | ffmpeg | System | Chunk-Merging |
| **Server** | Uvicorn | ≥0.38.0 | ASGI-Server |

### Frontend

| Komponente | Technologie | Version | Zweck |
|------------|-------------|---------|-------|
| **Framework** | React | 18.3.1 | UI-Komponenten |
| **Language** | TypeScript | ≥5.8.3 | Typsicherheit |
| **Build** | Vite | ≥5.4.19 | Dev-Server, Bundling |
| **UI-Kit** | shadcn/ui | - | Radix-basierte Components |
| **Styling** | Tailwind CSS | ≥3.4.17 | Utility-First CSS |
| **State** | React Context | - | Auth, Theme |
| **API-Prefix** | api.ts (BASE_PATH) | - | Runtime ROOT_PATH Injection |
| **Data Fetching** | TanStack Query | ≥5.83.0 | Server-State |
| **Markdown** | react-markdown | ≥10.1.0 | Summary-Rendering |
| **Icons** | lucide-react | ≥0.462.0 | Icon-Set |

---

## Zwei-Stufen-ASR: Implementation

openDox nutzt ein zweistufiges Transkriptionsmodell:

| Stage | Backend | Hardware | Zweck |
|-------|----------|----------|-------|
| **Live** | Parakeet (onnx-asr) | CPU | Near-Real-Time WebSocket mit Interpunktion |
| **Final** | Whisper (faster-whisper) | GPU | Hochwertige Re-Transkription des vollständigen Audios |

### ASR Factory (asr_factory.py)

Die `ASRFactory` erstellt den Live-Backend basierend auf der `live_backend`-Einstellung (`"parakeet"` | `"api"` | `"disabled"`):

```python
class ASRFactory:
    def _create_live_backend(self) -> ASRBackend:
        settings = get_settings()

        if settings.live_backend == "parakeet":
            endpoint = settings.live_api_endpoint or env_or_file("PARAKEET_API_ENDPOINT")
            return OpenAICompatibleBackend(
                endpoint=endpoint,
                model=settings.live_api_model or "nemo-parakeet-tdt-0.6b-v3",
            )

        if settings.live_backend == "api":  # Whisper
            return OpenAICompatibleBackend(
                endpoint=settings.live_api_endpoint,
                model=settings.live_api_model or "whisper-1",
            )

        return DisabledBackend()
```

### Frontend: AudioWorklet (Recorder.tsx)

Die Audio-Erfassung erfolgt über den `AudioWorklet` für maximale Performance und direkten Zugriff auf PCM-Daten:

```typescript
// Recorder.tsx - AudioWorklet Implementation
const workletCode = `
  class PCMProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
      const input = inputs[0];
      if (input.length > 0) {
        // Sende rohes Float32 (4 Byte pro Sample) direkt an das Backend
        this.port.postMessage(input[0].buffer);
      }
      return true;
    }
  }
  registerProcessor("pcm-worklet", PCMProcessor);
`;

// Chunk-Berechnung für optimale Latenz
const SAMPLE_RATE = 16000;        // 16kHz (Whisper-optimal)
const BYTES_PER_SAMPLE = 4;       // Float32
const CHUNK_DURATION_S = 3;       // 3 Sekunden
const OVERLAP_S = 1;              // 1 Sekunde Überlappung

const bytesPerChunk = CHUNK_DURATION_S * SAMPLE_RATE * BYTES_PER_SAMPLE;     // 192 KB
const bytesPerOverlap = OVERLAP_S * SAMPLE_RATE * BYTES_PER_SAMPLE;          // 64 KB

// Inline Worklet-Code laden
const blob = new Blob([workletCode], { type: "application/javascript" });
const workletUrl = URL.createObjectURL(blob);
await audioCtx.audioWorklet.addModule(workletUrl);

const source = audioCtx.createMediaStreamSource(stream);
const worklet = new AudioWorkletNode(audioCtx, "pcm-worklet");

// Float32 → WebSocket
worklet.port.onmessage = (e) => {
  if (socketRef.current?.readyState === WebSocket.OPEN) {
    socketRef.current.send(e.data); // ArrayBuffer (Float32)
  }
};
```

**Hintergrund:** WebM-Encoding wäre ineffizient, da Whisper ohnehin PCM erwartet. Der AudioWorklet ermöglicht direkte Verarbeitung ohne Format-Konvertierung.

### Frontend: Parallel-Upload für finale Datei

```typescript
// MediaRecorder für WebM-Chunks (alle 10s)
const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

mediaRecorder.ondataavailable = (e) => {
  if (e.data.size > 0 && sessionIdRef.current) {
    uploadChunk(e.data, sessionIdRef.current);
  }
};

mediaRecorder.onstop = async () => {
  // Warte auf alle Uploads vor STOP-Event
  await Promise.all(Array.from(activeUploadsRef.current));
  socketRef.current?.send(JSON.stringify({ event: "stop" }));
};

// Upload-Funktion mit Promise-Tracking
const uploadChunk = (chunk: Blob, sessionId: string) => {
  const formData = new FormData();
  formData.append("file", chunk, `chunk_${Date.now()}_${sessionId}.webm`);
  formData.append("session_id", sessionId);
  formData.append("user_id", userId);

  const promise = fetch("/api/v1/records/upload-chunk", {
    method: "POST",
    body: formData
  }).finally(() => activeUploadsRef.current.delete(promise));

  activeUploadsRef.current.add(promise);
};
```

### Backend: WebSocket Handler (record.py)

```python
@record_bp.websocket("/ws/record")
async def websocket_record(websocket: WebSocket, db: SessionDep):
    await websocket.accept()
    
    session_id = websocket.query_params.get("session_id")
    user_id = websocket.query_params.get("user_id")
    
    # Session-State initialisieren (PCM auf Disk, nicht im RAM)
    session = session_store.get_by_session(session_id)
    if session is None:
        session = session_store.create_session(
            user_id=int(user_id),
            session_id=session_id,
            record_id=record.id,
            title=record.title,
            audio_dir="chunks",
        )
    
    # Audio wird auf Disk geschrieben (session_{id}.pcm)
    # session["audio_file_path"] zeigt auf die PCM-Datei
    
    try:
        while True:
            msg = await websocket.receive()
            
            if msg.get("bytes"):
                chunk = msg["bytes"]
                
                # PCM auf Disk schreiben (kein RAM-Anstieg bei langen Aufnahmen)
                with open(session["audio_file_path"], "ab") as _f:
                    _f.write(chunk)
                session["audio_file_size"] += len(chunk)
                
                # Live-ASR alle 3s
                buffer_len = session["audio_file_size"]
                new_data_len = buffer_len - session["last_index"]
                
                if new_data_len >= bytes_per_chunk:
                    start = session["last_index"]
                    with open(session["audio_file_path"], "rb") as _f:
                        _f.seek(start)
                        audio_slice = _f.read(bytes_per_chunk)
                    
                    session["last_index"] = start + bytes_per_chunk - bytes_per_overlap
                    
                    # KEIN live_prompt — Whisper neigt dazu, Prompt-Text zu wiederholen
                    backend = get_live_asr()
                    result_text = await asyncio.to_thread(
                        backend.transcribe,
                        audio=audio_slice,
                        language="de",
                        prompt=None,
                        params=whisper_params,
                    )
                    
                    if result_text:
                        session["live_text"] = (session["live_text"] + " " + result_text).strip()
                        await websocket.send_json({
                            "session_id": session_id, "text": result_text
                        })
    
    except Exception as e:
        logger.error(f"[WS-ERROR] {e}")
    
    finally:
        if stopped:
            # PCM → WAV konvertieren, dann Hintergrund-Transkription
            await finalize(session_id, user_id)
```

**Wichtige Designentscheidungen:**

- **Audio auf Disk:** PCM wird in `session_{id}.pcm` geschrieben, nicht im RAM gehalten — verhindert Memory-Leaks bei langen Aufnahmen
- **Kein `live_prompt`:** Whisper neigt dazu, Text aus dem Prompt zu wiederholen, was Duplikate im Live-Transkript erzeugt
- **Parakeet = kein LLM-Korrektur:** Parakeet liefert bereits korrekte Interpunktion und Groß-/Kleinschreibung
- **Whisper = Batch-LLM-Korrektur:** Rohe Whisper-Chunks werden alle 5 Chunks über `chunk_correction_service.py` bereinigt

### Latenz-Profil

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ ZWEI-STUFEN LATENZ-PROFIL                                │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  STAGE 1: LIVE (Parakeet, CPU)                               │
│  Komponente              │ Latenz      │ Optimierung       │
│  ────────────────────────┼─────────────┼──────────────────  │
│  Audio-Capture (Browser) │   10-20ms   │ 16kHz direkt      │
│  WebSocket RTT           │    5-10ms   │ Lokales Netzwerk  │
│  Parakeet Inferenz (3s)  │  200-500ms  │ CPU (ONNX)        │
│  Response-Serialization  │    5-10ms   │ JSON minimal      │
│  ────────────────────────┼─────────────┼──────────────────  │
│  Gesamt (Live)           │  ~220-540ms  │ Kein LLM nötig    │
│                                                               │
│  STAGE 2: FINAL (Whisper, GPU)                              │
│  Komponente              │ Latenz      │ Optimierung       │
│  ────────────────────────┼─────────────┼──────────────────  │
│  PCM → WAV Konvertierung │   50-100ms  │ numpy + struct    │
│  Whisper Inferenz        │    2-10s    │ GPU (CUDA)        │
│  LLM Zusammenfassung    │    3-15s    │ Ollama CPU        │
│  ────────────────────────┼─────────────┼──────────────────  │
│  Gesamt (Final)          │   ~5-25s    │ Hintergrund-Task  │
│                                                               │
│  🔧 Optimierungspotenzial (Live):                              │
│  • Chunk auf 2s reduzieren (höhere CPU-Last)                   │
│  • Parakeet-Modell austauschbar via PARAKEET_MODEL             │
└─────────────────────────────────────────────────────────────┘
```

**Warum zwei Stufen?**
- **Parakeet (Live):** CPU-only, keine GPU nötig, liefert sofort Sätze mit Interpunktion — kein LLM-Korrekturschritt
- **Whisper (Final):** GPU-beschleunigt, höhere Qualität für die endgültige Transkription und Zusammenfassung

---

## Parakeet ASR Server (Eigenständiger Dienst)

Der Parakeet-Server ist ein eigenständiger FastAPI-Dienst, der über die OpenAI-kompatible API `/v1/audio/transcriptions` angesprochen wird.

### Architektur

```mermaid
graph LR
    subgraph Backend["openDox Backend"]
        A[ASR Factory]
        B[OpenAICompatibleBackend]
    end
    
    subgraph Parakeet["Parakeet Server (Port 5001)"]
        C["/v1/audio/transcriptions"]
        D[get_model - Dict Cache]
        E[onnx_asr Model]
    end
    
    A -->|live_backend="parakeet"| B
    B -->|HTTP POST| C
    C --> D
    D --> E
```

### Implementation (parakeet_server/main.py)

```python
# Standard library
import os
import struct
import tempfile
from contextlib import asynccontextmanager

# Third-party imports
import onnx_asr
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

DEFAULT_MODEL = os.getenv("PARAKEET_MODEL", "nemo-parakeet-tdt-0.6b-v3")

_models: dict[str, onnx_asr.Model] = {}


def get_model(name: str | None = None) -> onnx_asr.Model:
    """Load and cache an ONNX ASR model by name."""
    model_name = name or DEFAULT_MODEL
    if model_name in _models:
        return _models[model_name]
    _models[model_name] = onnx_asr.load_model(model_name)
    return _models[model_name]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_model()     # Default-Modell vorladen
    yield
    _models.clear()


app = FastAPI(title="openDox Parakeet ASR", lifespan=lifespan)


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    language: str = Form(default=""),
):
    content = await file.read()
    if not content:
        return JSONResponse({"text": ""})

    # WAV erkennen oder PCM → WAV konvertieren
    wav_bytes = content if content[:4] == b"RIFF" else _pcm_to_wav(content)
    m = get_model(model or None)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(wav_bytes)
        tmp.flush()
        result = m.recognize(tmp.name)
        text = result if isinstance(result, str) else str(result)

    return {"text": text}


def _pcm_to_wav(pcm: bytes) -> bytes:
    """Convert raw float32 16kHz mono PCM bytes to a WAV file."""
    audio = np.frombuffer(pcm, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (audio * 32767).astype(np.int16)
    # ... WAV-Header + Daten
```

**Eigenschaften:**
- **OpenAI-kompatibel:** Gleiche API wie Whisper — `OpenAICompatibleBackend` funktioniert unverändert
- **Modell-Cache:** `get_model(name)` mit Dict-Cache, keine Singletons
- **Lifespan:** Default-Modell wird beim Start vorgeladen (~300MB), bei Shutdown freigegeben
- **PCM → WAV:** Akzeptiert rohes Float32-PCM (16kHz, Mono) oder WAV-Dateien
- **CPU-only:** Keine GPU nötig, läuft auf jedem Host

---

## Enterprise: Redis Session-Store

### Current State: Redis-backed (with In-Memory Fallback)

Der Session-Store unterstützt jetzt Redis als Backend. Wenn `REDIS_URL` gesetzt ist, werden Sessions in Redis gespeichert (mit TTL, Persistence, Multi-Instance-Support). Ohne `REDIS_URL` fällt der Store auf das In-Memory-Dict zurück (Single-Instance, Sessions gehen bei Restart verloren).

```python
# backend/components/services/session_store.py
# Factory: wählt Redis oder In-Memory basierend auf REDIS_URL
from backend.components.modules.env import env_or_file

def _create_session_store():
    redis_url = env_or_file("REDIS_URL")
    if redis_url:
        from backend.components.services.session_store_redis import RedisSessionStore
        store = RedisSessionStore(redis_url)
        store.ping()  # Health-Check
        return store
    return SessionStore()  # In-Memory-Fallback

session_store = _create_session_store()
```

**Interface-Kompatibilität:** `RedisSessionStore` und `SessionStore` bieten identische Methoden:
- `create_session()`, `get_session()`, `get_by_session()`, `delete_session()`
- `update_session()`, `pause_session()`, `resume_session()`
- `set_live_state()`, `append_audio()`, `cleanup_stale_sessions()`

**Audio auf Disk:** PCM-Daten werden weiterhin auf Disk geschrieben (`session_{id}.pcm`), nicht in Redis. Redis speichert nur Metadaten (Session-IDs, Status, Live-Text, etc.).

### Redis-Konfiguration

```python
class SessionStore:
    """In-memory session store for active recordings.
    
    Audio data is written to disk (session_{id}.pcm), not held in RAM,
    to prevent memory leaks during long recordings.
    
    TODO: Replace with Redis for production/multi-instance deployments.
    """
    
    def __init__(self):
        self._sessions: Dict[int, Dict[str, Any]] = {}  # user_id -> session_data
        self._session_to_user: Dict[str, int] = {}      # session_id -> user_id
    
    def create_session(self, user_id, session_id, record_id, title, 
                       category_id=None, audio_dir="."):
        # PCM-Datei auf Disk erstellen (nicht im RAM)
        _audio_path = os.path.join(audio_dir, f"session_{session_id}.pcm")
        open(_audio_path, "wb").close()  # leere Datei erstellen
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "record_id": record_id,
            "title": title,
            "category_id": category_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "status": "recording",
            # Audio auf Disk — audio_file_size trackt Gesamtbytes
            "audio_file_path": _audio_path,
            "audio_file_size": 0,
            "last_index": 0,              # Fortschritt für Overlap
            "live_text": "",              # Akkumuliertes Live-Transkript
            "last_cleanup_time": 0.0,     # Periodische LLM-Glättung
            "last_cleanup_len": 0,
        }
        
        self._sessions[user_id] = session_data
        self._session_to_user[session_id] = user_id
        return session_data
    
    def append_audio(self, session_id: str, chunk: bytes) -> None:
        """Append raw audio bytes to the session's on-disk PCM file."""
        session = self.get_by_session(session_id)
        if session is not None and session.get("audio_file_path"):
            with open(session["audio_file_path"], "ab") as f:
                f.write(chunk)
            session["audio_file_size"] += len(chunk)
```

### Probleme der In-Memory-Lösung (ohne REDIS_URL)

| Problem | Auswirkung | Lösung |
|---------|------------|--------|
| ❌ Datenverlust bei Restart | Unfertige Aufnahmen gehen verloren | Redis Persistence (AOF) |
| ❌ Kein Multi-Instance | Load-Balancing unmöglich | Redis Cluster |
| ❌ Memory-Leak | Sessions nie aufgeräumt | Redis TTL (30 Min) |
| ❌ Keine Shared State | Websocket auf anderer Instance findet Session nicht | Redis als zentraler Store |

> **Mit `REDIS_URL` gesetzt:** Alle Probleme sind gelöst. Redis bietet TTL-basierte Bereinigung, Persistence, und Multi-Instance-Support.

### Implementation: RedisSessionStore (session_store_redis.py)

Die `RedisSessionStore`-Klasse ist implementiert und produktionsbereit:

- **Redis Hash:** `session:{user_id}` → Felder als Key/Value-Paare
- **Reverse Mapping:** `session_map:{session_id}` → `user_id` (String, mit TTL)
- **TTL:** 30 Minuten Default, wird bei jedem Zugriff erneuert
- **PCM-Audio:** Bleibt auf Disk, Redis speichert nur `audio_file_path` als Referenz
- **Serialisierung:** `datetime` → ISO-String, Numerics → Strings, `None` → leerer String
- **Health-Check:** `ping()` im Konstruktor, Fallback auf In-Memory bei Verbindungsfehler

> Die vollständige Implementation befindet sich in `backend/components/services/session_store_redis.py`.

### Docker-Integration

```yaml
# docker-compose.yml - Redis Service (bereits integriert)
services:
  redis:
    image: redis:7-alpine
    container_name: opendox-redis
    restart: always
    command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy

volumes:
  redis-data:
    name: opendox-redis-data
```

### Migration Guide

```bash
# Schritt 1: Redis-Abhängigkeit installieren (bereits in pyproject.toml)
uv pip install redis

# Schritt 2: REDIS_URL in .env setzen
echo "REDIS_URL=redis://localhost:6379/0" >> .env

# Schritt 3: App neu starten — Factory wählt automatisch Redis
# (kein Code-Wechsel nötig, session_store.py entscheidet anhand REDIS_URL)
docker compose -f docker/docker-compose.yml restart app
```

---

## Enterprise: LDAP Integration

### LDAP-Service (ldap.py)

```python
# ldap.py - Enterprise Authentication Service
from ldap3 import Server, Connection, ALL, Tls
from typing import Dict, Optional

class LdapService:
    """LDAP authentication service for enterprise environments.
    
    Supports:
    - Active Directory
    - OpenLDAP
    - FreeIPA
    """
    
    def __init__(self, settings: LdapSettingsModel):
        # SSL/TLS Configuration
        tls = Tls(validate=ssl.CERT_REQUIRED) if settings.use_ssl else None
        
        self.server = Server(
            settings.server_url,
            get_info=ALL,
            use_ssl=settings.use_ssl,
            tls=tls
        )
        self.bind_dn = settings.bind_dn
        self.bind_password = settings.bind_password
        self.user_search_base = settings.user_search_base
        self.user_filter = settings.user_filter
    
    def authenticate(self, username: str, password: str) -> Dict:
        """Authenticate user against LDAP server."""
        try:
            # Build user DN from filter template
            user_filter = self.user_filter.format(username=username)
            
            # Connect with admin/service credentials
            conn = Connection(
                self.server,
                self.bind_dn,
                self.bind_password,
                auto_bind=True
            )
            
            # Search for user
            conn.search(
                self.user_search_base,
                user_filter,
                attributes=['dn', 'mail', 'displayName']
            )
            
            if len(conn.entries) == 0:
                return {"success": False, "error": "User not found"}
            
            user_dn = conn.entries[0].dn
            
            # Verify password with user DN
            user_conn = Connection(self.server, user_dn, password)
            if user_conn.bind():
                user_conn.unbind()
                return {
                    "success": True,
                    "email": str(conn.entries[0].mail),
                    "display_name": str(conn.entries[0].displayName)
                }
            else:
                return {"success": False, "error": "Invalid password"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
```

### Auth-Endpoints mit LDAP-Fallback

```python
# auth_routes.py - Login mit LDAP-Integration
@auth_bp.post("/login", response_model=Token)
async def login(user_in: UserLogin, db: SessionDep):
    # 1. Lokale Authentifizierung versuchen
    stmt = select(User).where(User.name == user_in.name)
    user = db.exec(stmt).first()
    
    if user and user.hashed_password:
        if verify_password(user_in.password, user.hashed_password):
            access_token = create_access_token(sub=str(user.id))
            refresh_token = create_refresh_token(sub=str(user.id))
            return Token(access_token=access_token, refresh_token=refresh_token)
    
    # 2. LDAP Login (Fallback)
    stmt_ldap = select(LdapSettingsModel)
    ldap_settings = db.exec(stmt_ldap).first()
    
    if ldap_settings:
        ldap_service = LdapService(ldap_settings)
        auth_result = ldap_service.authenticate(user_in.name, user_in.password)
        
        if auth_result["success"]:
            # Auto-Provisioning: Neuen Benutzer anlegen
            if not user:
                user = User(
                    name=user_in.name,
                    hashed_password="",  # Kein Passwort für LDAP-User
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            access_token = create_access_token(sub=str(user.id))
            refresh_token = create_refresh_token(sub=str(user.id))
            return Token(access_token=access_token, refresh_token=refresh_token)
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect name or password",
    )
```

### LDAP Settings Model

```python
# models/ldap_model.py
class LdapSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    server_url: str = "ldap://ldap.example.com:389"
    use_ssl: bool = False
    base_dn: str = "dc=example,dc=com"
    bind_dn: str = "cn=admin,dc=example,dc=com"
    bind_password: str  # Verschlüsselt speichern!
    user_search_base: str = "ou=users,dc=example,dc=com"
    # OpenLDAP Format:
    user_filter: str = "(uid={username})"
    # Active Directory Alternative:
    # user_filter = "(sAMAccountName={username})"
```

### Vergleich: Local vs. LDAP

```
┌─────────────────────────────────────────────────────────────┐
│  🔐 AUTHENTICATION COMPARISON                               │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  Feature                │ Local Auth │ LDAP Integration     │
│  ───────────────────────┼────────────┼──────────────────────  │
│  Setup Complexity       │ ✅ Simple  │ ⚠️  Moderate          │
│  Password Management    │ ❌ Manual  │ ✅ Centralized        │
│  Multi-System Login     │ ❌ Per App │ ✅ Single Sign-On     │
│  Password Policies      │ ❌ Basic   │ ✅ Enterprise         │
│  User Provisioning      │ ❌ Manual  │ ✅ Auto-Sync          │
│  MFA Support            │ ❌ Custom  │ ✅ Built-in           │
│  Offline Capability     │ ✅ Yes     │ ⚠️ Cached only        │
│  Compliance (GDPR)        │ ⚠️ Self    │ ✅ Audit-ready        │
│                                                               │
│  🎯 Recommendation:                                           │
│  • <10 Users: Local Auth sufficient                          │
│  • 10-100 Users: LDAP recommended                            │
│  • >100 Users: LDAP + SSO (SAML/OIDC) required              │
└─────────────────────────────────────────────────────────────┘
```

---

## Sub-Pfad Deployment (ROOT_PATH)

openDox kann unter einem Sub-Pfad wie `/opendox` betrieben werden, ohne dass das Frontend neu gebaut werden muss.

### Funktionsweise

1. **`.env`**: `ROOT_PATH=/opendox` setzen
2. **Backend-Start**: `run.py:_inject_root_path()` schreibt `window.__ROOT_PATH__='/opendox'` in `static/index.html`
3. **Frontend-Runtime**: `api.ts` liest `window.__ROOT_PATH__` und patcht `window.fetch` — alle `/api/`-Aufrufe bekommen den Prefix
4. **WebSocket**: `Recorder.tsx` importiert `BASE_PATH` aus `api.ts` für die WebSocket-URL
5. **Vite Dev**: `vite.config.ts` liest `ROOT_PATH` aus `.env` für den Proxy

```python
# backend/run.py — Runtime-Injektion
def _inject_root_path(static_dir: str, root_path: str) -> None:
    """Write window.__ROOT_PATH__ into index.html on disk at startup."""
    index_path = os.path.join(static_dir, "index.html")
    html = open(index_path, "r").read()
    script = f"<script>window.__ROOT_PATH__='{root_path}';</script>"
    # Altes Script entfernen, neues vor </head> einfügen
    html = re.sub(r"<script>window\.__ROOT_PATH__='.*?';</script>", "", html)
    html = html.replace("</head>", f"{script}</head>", 1)
    open(index_path, "w").write(html)
```

```typescript
// frontend/src/api.ts — Runtime-Patch
export const BASE_PATH: string =
  (window as any).__ROOT_PATH__ || import.meta.env.VITE_ROOT_PATH || "";

if (BASE_PATH) {
  const originalFetch = window.fetch;
  window.fetch = (input, init) => {
    let url = typeof input === "string" ? input : input.toString();
    if (url.startsWith("/api/")) url = BASE_PATH + url;
    return originalFetch(url, init);
  };
}
```

**Wichtig:** `root_path=` NICHT an `FastAPI()` übergeben — Starlette würde den Prefix vor dem Routing entfernen, was zu doppeltem Prefix und 404s führt. Routen werden manuell in `create_app()` geprefixt.

**Wichtig (Vite Dev):** `VITE_ROOT_PATH` in `.env` muss `ROOT_PATH` entsprechen, damit der Vite-Proxy und der `api.ts`-Fallback korrekt funktionieren.

```typescript
// vite.config.ts — Proxy mit ROOT_PATH
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const rootPath = env.ROOT_PATH ?? "";

  return {
    base: "",
    build: {
      outDir: path.resolve(__dirname, "../backend/static"),
      emptyOutDir: true,
    },
    server: {
      proxy: {
        [`${rootPath}/api/v1/`]: {
          target: "http://localhost:5000",
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
```

---

## 🔒 Datenbankverschlüsselung (DSGVO-konform)

> **⚠️ Wichtig:** Wenn `ENCRYPTION_KEY` nicht gesetzt ist, wird die Verschlüsselung **stillschweigend deaktiviert** — patientenbezogene Daten werden im Klartext gespeichert. Es gibt keine Fehlermeldung, nur einen Warning-Log-Eintrag. Für DSGVO-Konformität muss `ENCRYPTION_KEY` zwingend gesetzt sein.

### Fernet-Verschlüsselung (field_encryption.py)

```python
# field_encryption.py - Transparent Field Encryption
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator
from backend.components.modules.env import env_or_file

# Key aus Environment oder Docker Secrets
_raw_key = env_or_file("ENCRYPTION_KEY", None)

if _raw_key is None:
    logger.warning(
        "ENCRYPTION_KEY is not set — patient data will be stored unencrypted. "
        "Set ENCRYPTION_KEY to a Fernet key for DSGVO compliance. "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
    _fernet = None
else:
    _fernet = Fernet(_raw_key.encode() if isinstance(_raw_key, str) else _raw_key)


def encrypt(value: str) -> str:
    """Encrypt a string using Fernet symmetric encryption."""
    if _fernet is None or not value:
        return value
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a Fernet-encrypted string. Falls back to plaintext for unencrypted legacy data."""
    if _fernet is None or not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Old plaintext record — return as-is to allow gradual migration
        return value


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts on write and decrypts on read.
    
    Usage:
        content: str = Field(sa_column=Column(EncryptedString, nullable=False))
    
    The encryption is transparent to the application layer:
    - Write: Plaintext → Encrypted (automatic)
    - Read: Encrypted → Plaintext (automatic)
    """
    
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Called when writing to database."""
        if value is None:
            return value
        return encrypt(value)
    
    def process_result_value(self, value, dialect):
        """Called when reading from database."""
        if value is None:
            return value
        return decrypt(value)
```

### Anwendung in Record-Model

```python
# record_model.py
from sqlalchemy import Column
from backend.components.security.field_encryption import EncryptedString

class Record(SQLModel, table=True):
    """Medical record with encrypted patient data."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    user_id: int
    title: str
    
    # 🔒 VERSCHLÜSSELT: Patientenbezogene Daten
    content: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    summarize: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    
    # Unverschlüsselt (kein medizinischer Inhalt)
    timestamp: str
    file: str
    archived: bool = Field(default=False)
```

### Key-Management

```bash
# 1. Fernet-Key generieren
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Output: b'your-key-here...'

# 2. Als Environment Variable setzen
export ENCRYPTION_KEY="your-key-here..."

# 3. Oder in Docker Secret
# echo "your-key-here..." | docker secret create encryption_key -

# 4. Oder in .env Datei
echo "ENCRYPTION_KEY=your-key-here..." >> .env

# 5. Mit Docker Secrets (empfohlen)
# docker-compose.yml
secrets:
  encryption_key:
    file: ./secrets/encryption_key

services:
  app:
    secrets:
      - encryption_key
    environment:
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
```

### DSGVO-Compliance

```
┌─────────────────────────────────────────────────────────────┐
│  🛡️  DSGVO-COMPLIANCE                                       │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  ✅ Verschlüsselung bei Speicherung (Art. 32 DSGVO)          │
│     - Patientenbezogene Felder (content, summarize)           │
│     - AES-128 im Fernet-Format (symmetrisch)                │
│     - Token-basierte Verschlüsselung (Pseudonymisierung)    │
│     ⚠️  Achtung: Ohne ENCRYPTION_KEY stillschweigend deaktiviert! │
│                                                               │
│  ✅ Zugriffskontrolle (Art. 32 DSGVO)                         │
│     - JWT-basierte Authentifizierung                        │
│     - LDAP-Integration für Enterprise-Umgebungen             │
│     - Superuser-Flag für Admin-Funktionen                   │
│                                                               │
│  ✅ Vertraulichkeit (Art. 5 DSGVO)                           │
│     - Field-level encryption (nicht nur DB-Verschlüsselung)  │
│     - Memory-safe: Key nie im Code, nur in Environment       │
│     - Fallback auf Plaintext für Migration (abwärtskompatibel)│
│     ⚠️  Achtung: Ohne ENCRYPTION_KEY werden Daten im Klartext gespeichert │
│                                                               │
│  ⚠️  TODO: Dokumentation (Art. 30 DSGVO)                     │
│     - Verzeichnis von Verarbeitungstätigkeiten (VVT)        │
│     - Datenfluss-Dokumentation                                │
│                                                               │
│  ⚠️  TODO: Audit-Logging (Art. 5 DSGVO)                      │
│     - Wer hat wann auf welche Patientendaten zugegriffen?    │
│     - Unveränderbare Logs (Write-once storage)              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Technische Details

**Algorithmus:** Fernet (AES-128 in CBC mode mit HMAC)

**Was ist verschlüsselt?**
- `Record.content` – Transkript (patientenbezogene Gespräche)
- `Record.summarize` – LLM-Zusammenfassung (patientenbezogene Inhalte)

**Was ist NICHT verschlüsselt?**
- `Record.title` – Titel der Aufnahme (administrativ)
- `Record.timestamp` – Zeitstempel (Metadaten)
- `User.name` – Benutzername (Referenz für Zugriffskontrolle)

**Warum Feldweise Verschlüsselung?**
- 🔍 **Suche erhalten:** Nicht-verschlüsselte Felder bleiben durchsuchbar
- 📊 **Analytics:** Metadaten für Statistiken nutzbar
- 🔄 **Migration:** Abwärtskompatibel (Fallback auf Plaintext)

---

## Architecture Evolution

### Phase 1: MVP (Current State)

```mermaid
graph LR
    subgraph MVP["MVP Architecture"]
        A[Browser] -->|HTTP/WebSocket| B[FastAPI Single Instance]
        B --> C[(PostgreSQL)]
        B --> D[Whisper Docker<br/>GPU — Final]
        B --> E[Parakeet Docker<br/>CPU — Live]
        B --> F[In-Memory Sessions<br/>PCM on Disk]
        B --> G[Ollama LLM]
    end
    
    style MVP fill:#e8f5e9
```

**Charakteristika:**
- ✅ Single-instance deployment
- ✅ PostgreSQL als Primär-DB (SQLite als Fallback möglich, aber nicht empfohlen)
- ✅ Zwei-Stufen-ASR: Parakeet (Live, CPU) + Whisper (Final, GPU)
- ✅ In-Memory Sessions mit Disk-basiertem Audio (kein RAM-Anstieg)
- ✅ Keine externen Abhängigkeiten außer Whisper/Parakeet/Ollama

**Geeignet für:**
- Einzelpraxen (< 5 Benutzer)
- Proof-of-Concept
- Development/Testing

### Phase 2: Production (Target State)

```mermaid
graph TB
    subgraph PROD["Production Architecture"]
        A[Browser] --> LB[Load Balancer<br/>Traefik/Nginx]
        
        LB --> B1[FastAPI Instance 1]
        LB --> B2[FastAPI Instance 2]
        LB --> B3[FastAPI Instance N]
        
        B1 --> DB[(PostgreSQL<br/>Primary-Replica)]
        B2 --> DB
        B3 --> DB
        
        B1 --> C[Redis Cluster]
        B2 --> C
        B3 --> C
        
        B1 --> D1[Parakeet ASR<br/>CPU — Live]
        B1 --> D2[Whisper ASR<br/>GPU — Final]
        
        B1 --> E[Ollama LLM<br/>CPU Cluster]
        
        B1 --> F[LDAP/Active Directory]
    end
    
    style PROD fill:#fff3e0
```

**Enhancements (geplant):**
- ⚠️ Horizontal scaling (multiple FastAPI instances) — aktuell Single-Instance
- ⚠️ Session persistence (Redis Cluster) — aktuell In-Memory
- ⚠️ Database replication (PostgreSQL Primary-Replica)
- ⚠️ High availability (no single point of failure)
- ⚠️ Enterprise authentication (LDAP/Active Directory) — Grundgerüst vorhanden, nicht produktiv erprobt
- ⚠️ Load balancing (Traefik or Nginx)
- ⚠️ Production-grade logging & monitoring

**Geeignet für:**
- Mittelgroße Praxen (10-50 Benutzer)
- Kliniken und MVZs
- Multi-Standort-Deployments

### Migrations-Roadmap

```
┌─────────────────────────────────────────────────────────────┐
│  🗺️  ENTERPRISE MIGRATION ROADMAP                          │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  Phase 1: Foundation (Week 1-2)                              │
│  ├─ Docker-Compose für Redis einrichten                    │
│  ├─ Session-Store auf Redis migrieren (✅ implementiert)    │
│  ├─ PostgreSQL als Primary DB konfigurieren               │
│  └─ Health-Check Endpoints implementieren                    │
│                                                               │
│  Phase 2: Authentication (Week 3-4)                          │
│  ├─ LDAP-Service implementieren                            │
│  ├─ Fallback-Logik (Local → LDAP) testen                   │
│  ├─ User-Sync und Auto-Provisioning                         │
│  └─ SSL/TLS für LDAP konfigurieren                         │
│                                                               │
│  Phase 3: High Availability (Week 5-6)                       │
│  ├─ Load-Balancer (Traefik) aufsetzen                      │
│  ├─ Multi-Instance Deployment (Docker Swarm/K8s)          │
│  ├─ PostgreSQL Replication konfigurieren                    │
│  └─ Redis Cluster für HA-Sessions                          │
│                                                               │
│  Phase 4: Observability (Week 7-8)                           │
│  ├─ Prometheus Metrics exportieren                         │
│  ├─ Grafana Dashboards erstellen                             │
│  ├─ Structured Logging (JSON Format)                       │
│  ├─ Alerting Rules (Slack/Email/PagerDuty)                 │
│  └─ Backup-Strategie testen (Disaster Recovery)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Production Readiness Checklist

```
┌─────────────────────────────────────────────────────────────┐
│  🚀 PRODUCTION READINESS CHECKLIST                           │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  SECURITY 🔐                                                 │
│  ├─ [✅] JWT Authentication                                 │
│  ├─ [✅] LDAP Integration                                   │
│  ├─ [✅] Field Encryption (Fernet)                          │
│  ├─ [✅] HTTPS Enforcement (Reverse-Proxy)                   │
│  ├─ [⚠️ ] Rate-Limiting (TODO: nginx/slowapi)              │
│  ├─ [⚠️ ] Audit-Logging (TODO: who accessed what when)      │
│  └─ [⚠️ ] CSP Headers (TODO: Content-Security-Policy)       │
│                                                               │
│  RELIABILITY 🛡️                                              │
│  ├─ [✅] Health-Check Endpoints (/api/endpoint)             │
│  ├─ [⚠️ ] Readiness Probes (TODO: DB/Redis connection)      │
│  ├─ [✅] Redis Session Store (REDIS_URL → Redis, else In-Memory) │
│  ├─ [⚠️ ] Circuit Breaker (TODO: for external services)   │
│  └─ [⚠️ ] Retry Logic (TODO: exponential backoff)          │
│                                                               │
│  SCALABILITY 📈                                               │
│  ├─ [✅] Stateless Application                              │
│  ├─ [✅] Redis for Sessions (REDIS_URL, else In-Memory fallback) │
│  ├─ [⚠️ ] Load-Balancer Config (TODO: Traefik)              │
│  └─ [⚠️ ] Auto-Scaling Rules (TODO: K8s HPA)               │
│                                                               │
│  MONITORING 📊                                                │
│  ├─ [✅] Basic Logging (Python stdlib)                     │
│  ├─ [⚠️ ] JSON Structured Logs (TODO: pythonjsonlogger)   │
│  ├─ [⚠️ ] Prometheus Metrics (TODO: prometheus-fastapi)   │
│  ├─ [⚠️ ] Grafana Dashboards (TODO: import dashboard)     │
│  └─ [⚠️ ] Alerting (TODO: Alertmanager rules)               │
│                                                               │
│  BACKUP & RECOVERY 💾                                         │
│  ├─ [✅] PostgreSQL Volume                                │
│  ├─ [⚠️ ] Automated Backups (TODO: pg_dump cron)          │
│  ├─ [⚠️ ] Backup Testing (TODO: monthly restore test)     │
│  └─ [⚠️ ] Disaster Recovery Plan (TODO: documented)       │
│                                                               │
│  COMPLIANCE 📋                                                │
│  ├─ [✅] AGPL-3.0 License Headers                         │
│  ├─ [✅] Field Encryption for PHI                         │
│  ├─ [⚠️ ] VVT Documentation (TODO: Art. 30 DSGVO)         │
│  └─ [⚠️ ] Data Processing Agreement (TODO: DPA)           │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Legend:
[✅] Implemented and tested
[⚠️ ] TODO or needs improvement
```

---

## API-Referenz

### Authentication

| Methode | Pfad | Beschreibung | Auth |
|---------|------|--------------|------|
| POST | `/api/v1/auth/register` | Benutzer registrieren | ❌ |
| POST | `/api/v1/auth/login` | Login (lokal + LDAP) | ❌ |
| POST | `/api/v1/auth/refresh` | Token refreshen | ❌ |
| GET | `/api/v1/auth/me` | Aktueller Benutzer | ✅ |
| GET | `/api/v1/auth/users` | Benutzerliste (Admin) | ✅ (Superuser) |
| POST | `/api/v1/auth/users` | Benutzer erstellen (Admin) | ✅ (Superuser) |
| PUT | `/api/v1/auth/users/{id}` | Benutzer updaten (Admin) | ✅ (Superuser) |
| DELETE | `/api/v1/auth/users/{id}` | Benutzer löschen (Admin) | ✅ (Superuser) |

### Records

| Methode | Pfad | Beschreibung | Auth |
|---------|------|--------------|------|
| POST | `/api/v1/records/create` | Neue Aufnahme erstellen | ✅ |
| GET | `/api/v1/records/active-session/{user_id}` | Aktive Session abrufen | ✅ |
| DELETE | `/api/v1/records/cancel-session/{user_id}` | Session abbrechen | ✅ |
| WS | `/api/v1/records/ws/record` | WebSocket für Live-Transkript | ✅ |
| POST | `/api/v1/records/upload-chunk` | Audio-Chunk hochladen | ✅ |
| GET | `/api/v1/records/list-records/{user_id}` | Aufnahmen auflisten | ✅ |
| GET | `/api/v1/records/record/{record_id}` | Einzelne Aufnahme | ✅ |
| PUT | `/api/v1/records/record/{record_id}` | Aufnahme updaten | ✅ |
| DELETE | `/api/v1/records/record/{record_id}` | Aufnahme löschen | ✅ |
| PUT | `/api/v1/records/record/{id}/archive` | Archivieren | ✅ |
| PUT | `/api/v1/records/record/{id}/unarchive` | De-Archivieren | ✅ |
| GET | `/api/v1/records/by-session/{session_id}` | Nach Session-ID suchen | ✅ |
| GET | `/api/v1/records/status/{task_id}` | Task-Status | ✅ |

### Settings (Admin only)

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/api/v1/settings/whisper-settings/` | Whisper-Konfiguration |
| PUT | `/api/v1/settings/whisper-settings/` | Whisper updaten |
| GET | `/api/v1/settings/llm-settings/` | LLM-Konfiguration |
| PUT | `/api/v1/settings/llm-settings/` | LLM updaten |
| GET | `/api/v1/settings/ldap-settings/` | LDAP-Konfiguration |
| PUT | `/api/v1/settings/ldap-settings/` | LDAP updaten |

---

## Entwicklungsbefehle

### Backend

```bash
# Environment kopieren
cp .env.example .env

# Dependencies installieren (mit uv)
uv pip install -r pyproject.toml

# Development Server starten
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000

# ⚠️ Wichtig: Nie "uv run main.py" verwenden (führt zu double init!)

# Datenbank-Migrationen
alembic upgrade head

# Neue Migration erstellen
alembic revision --autogenerate -m "Beschreibung"
```

### Frontend

```bash
cd frontend

# Dependencies installieren
npm install

# Development Server (Port 3000, Proxy zu :5000)
npm run dev

# Production Build (Output: backend/static/)
npm run build

# Preview Build
npm run preview
```

### Docker (Production)

```bash
# Gesamter Stack (PostgreSQL + Whisper + Parakeet + App)
docker compose -f docker/docker-compose.yml up --build

# Nur spezifische Services
docker compose -f docker/docker-compose.yml up -d postgres
docker compose -f docker/docker-compose.yml up -d parakeet

# Standalone Whisper (Port 9100 → Container 9000)
docker compose -f docker/docker-whisper.yml up -d

# Standalone Parakeet (Port 9200 → Container 5001)
docker compose -f docker/docker-parakeet.yml up -d

# Logs ansehen
docker compose -f docker/docker-compose.yml logs -f app

# Container stoppen
docker compose -f docker/docker-compose.yml down

# Mit Volumes löschen (⚠️ Datenverlust)
docker compose -f docker/docker-compose.yml down -v
```

**Hinweis:** `docker/parakeet-server/` ist aktuell ein leeres Verzeichnis. Die `docker-compose.yml` referenziert `./docker/parakeet-server` als Build-Context, aber `Dockerfile` und `main.py` liegen in `parakeet_server/` (Projekt-Root). Entweder das Verzeichnis befüllen oder den Build-Context auf `../parakeet_server` ändern.

**Hinweis:** Redis ist jetzt in der `docker-compose.yml` integriert. Ohne `REDIS_URL` wird der In-Memory-Fallback verwendet.

---

## Bekannte Probleme & Lösungen

### 1. Dev-Server: `python -m uvicorn main:app`

❌ **Falsch:** `uv run main.py` (führt zu double init)  
✅ **Richtig:** `python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000`

**Grund:** `main.py` importiert `create_app()` und ruft `uvicorn.run()` nur bei `__main__` auf.

### 2. Port 9000 Konflikt (Whisper)

Port 9000 ist oft von Jupyter belegt.

**Lösung:**
```yaml
# docker-compose.yml
ports:
  - "9100:9000"  # Host:Container
```

### 3. Whisper Settings: DB priorisiert ENV

DB-Werte überschreiben `.env`. Bei Stale Settings:

**Lösungen:**
1. Settings UI verwenden (`/settings`)
2. DB zurücksetzen: `DELETE FROM whisper_settings_model;`
3. Server neu starten

### 4. WebSocket-Proxy (Vite)

Frontend verwendet `window.location.host` für WebSocket. Der Vite-Proxy berücksichtigt dynamisch `ROOT_PATH`:

```typescript
// vite.config.ts — Proxy mit ROOT_PATH
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const rootPath = env.ROOT_PATH ?? "";

  return {
    server: {
      proxy: {
        [`${rootPath}/api/v1/`]: {
          target: "http://localhost:5000",
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      },
    },
  };
});
```

### 5. Settings-Cache: DB-Werte priorisieren ENV

`SettingsService` cached `_whisper_settings` / `_llm_settings`. Nach Änderungen via API oder DB muss `invalidate_cache()` oder `reset_asr_backends()` aufgerufen werden — sonst werden veraltete Werte geliefert bis zum Neustart.

### 6. LLM: Fresh Instance per Task

❌ **Falsch:** Singleton `OllamaModel()`  
✅ **Richtig:** `OllamaModel()` in `background_transcription_service.py` neu erstellen

**Grund:** Settings-Updates werden sonst nicht übernommen.

### 7. HTTPS für Microphone

Browser erfordern HTTPS für Microphone-Zugriff (außer localhost).

**Lösung:**
```python
# backend/run.py
@app.middleware("http")
async def add_permissions_policy(request: Request, call_next):
    response = await call_next(request)
    response.headers["Permissions-Policy"] = "microphone=(self)"
    return response
```

### 8. env_or_file und ENCRYPTION_KEY

`env_or_file()` in `backend/components/modules/env.py` führt `load_dotenv(override=True)` **beim Import** aus — bevor irgendein anderes Modul `env_or_file()` aufruft. Jede `{VAR}_FILE`-Suffix liest aus einer Datei (Docker Secrets). `ENCRYPTION_KEY_FILE=/run/secrets/encryption_key` wird also automatisch aufgelöst.

**Wichtig:** Wenn `ENCRYPTION_KEY` nicht gefunden wird, liegt das oft daran, dass `load_dotenv()` nicht aufgerufen wurde bevor das Modul importiert wird. `env.py` führt `load_dotenv(override=True)` jetzt automatisch beim Import aus.

### 9. docker/parakeet-server/ ist leer

Die `docker-compose.yml` referenziert `./docker/parakeet-server` als Build-Context für den Parakeet-Service, aber das Verzeichnis ist leer. `Dockerfile` und `main.py` liegen in `parakeet_server/` (Projekt-Root).

**Lösungen:**
1. Dateien nach `docker/parakeet-server/` kopieren
2. Build-Context in `docker-compose.yml` auf `../parakeet_server` ändern

### 10. Alembic.ini URL ist irrelevant

`alembic.ini` enthält `sqlite3:///test.sqlite3`, aber sowohl `run.py` als auch `alembic/env.py` überschreiben die URL zur Laufzeit mit `SQLALCHEMY_URI`. Der ini-Wert hat keine Bedeutung.

### 11. Dockerfile: Frontend-Build-Output-Pfad (✅ behoben)

`vite.config.ts` setzt `outDir` auf `../backend/static`. Im Docker-Build (WORKDIR `/app/frontend`) löst sich das zu `/app/backend/static` auf. Die `Dockerfile`-Zeile kopiert jetzt korrekt von `/app/backend/static`:

```dockerfile
COPY --from=frontend-builder /app/backend/static ./backend/static/
```

### 12. SQLite-Fallback: DB-Name ist `aidox`, nicht `opendox`

Wenn weder `DATABASE_URI` noch `SQL_*`-Variablen gesetzt sind, baut `db_config.py` folgende URI: `postgresql+psycopg2://postgres:postgres@localhost:5432/aidox`. Der Standard-Datenbankname lautet `aidox`, nicht `opendox`. PostgreSQL muss also eine Datenbank namens `aidox` haben, oder es muss `SQL_DB=opendox` gesetzt werden.

### 13. VITE_ROOT_PATH muss ROOT_PATH entsprechen

Für den Vite Dev-Server muss `VITE_ROOT_PATH` in `.env` denselben Wert wie `ROOT_PATH` haben. Ohne diese Variable funktioniert der Proxy und der `api.ts`-Fallback im Dev-Modus nicht korrekt.

### 14. Feldverschlüsselung: Deaktiviert bei fehlendem ENCRYPTION_KEY

Wenn `ENCRYPTION_KEY` nicht gesetzt ist, wird die Verschlüsselung **stillschweigend deaktiviert** — patientenbezogene Daten werden im Klartext gespeichert. Es gibt keine Fehlermeldung, nur einen Warning-Log-Eintrag. Für DSGVO-Konformität muss `ENCRYPTION_KEY` zwingend gesetzt sein.

### 15. ruff known-first-party: Platzhalter statt korrektem Wert

`pyproject.toml` enthält `known-first-party = ["dein_projektname"]` — das ist ein Template-Platzhalter. Für korrekte Import-Sortierung sollte dies `["backend"]` sein.

### 16. Frontend-Build: Output geht nach `../backend/static`, nicht `frontend/dist`

`vite.config.ts` konfiguriert `outDir: path.resolve(__dirname, "../backend/static")`. Das bedeutet `npm run build` schreibt direkt in `backend/static/`, nicht in `frontend/dist/`. Der Eintrag `frontend/dist/` in `.gitignore` ist daher überflüssig; stattdessen ist `static/` (im Backend-Verzeichnis) die relevante Ignore-Regel.

---

## Ressourcen

### Repositories

- **Quellcode:** [GitHub - openDox](https://github.com/christopherabanilla/openDox)
- **Docker Images:** Docker Hub
- **Dokumentation:** Diese Datei (opendox.md)

### Technologie-Dokumentation

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [React](https://react.dev/)
- [shadcn/ui](https://ui.shadcn.com/)
- [Whisper](https://github.com/openai/whisper)
- [Ollama](https://ollama.com/)

---

## Danksagung

Entwickelt von **Christopher Abanilla** für den Einsatz in medizinischen Praxen und Kliniken.

Besonderer Dank an die Open-Source-Community:

- **Sebastián Ramírez** – FastAPI
- **Tiangolo** – SQLModel
- **shadcn** – shadcn/ui
- **OpenAI** – Whisper
- **Ollama Team** – Lokale LLM-Inferenz

---

## Lizenz

```
openDox - Medical transcription platform
Copyright (C) 2025 Christopher Abanilla <christopher.abanilla@gmx.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

---

*Letzte Aktualisierung: Juni 2026*  
*Version: 0.2.0*  
*Änderungen: Redis Session Store implementiert, Dockerfile-Frontend-Build-Pfad behoben*
