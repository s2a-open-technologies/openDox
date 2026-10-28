# openDox – Medizinische Transkriptionsplattform

> **AGPL-3.0-or-later** | Copyright (C) 2025 S2A Open Technologies gGmbH
> 
> Dieses Programm ist freie Software: Sie können es unter den Bedingungen der GNU Affero General Public License weiterverteilen und/oder modifizieren.

---

## Projektvision

**openDox** ist eine moderne, webbasierte Plattform für medizinische Transkription, entwickelt für Praxen, Kliniken und medizinische Versorgungszentren (MVZs). Die Anwendung ermöglicht medizinischem Fachpersonal die sprachgesteuerte Dokumentation von Patientendaten mittels KI-gestützter Spracherkennung und automatischer Zusammenfassung.

### Kernfeatures

- 🎤 **Zwei-Stufen-Transkription**: Parakeet (Live, VAD-segmentiertes WS-Streaming) + Whisper (Final, GPU)
- 🏷️ **Kategorien**: jede Aufnahme bekommt eine Kategorie mit eigenem Whisper-Vokabular-Prompt, LLM-System-Prompt und optionalem Per-Kategorie-LLM-Backend
- 🤖 **KI-Zusammenfassung**: Grammatikkorrektur und Strukturierung über ein beliebiges OpenAI-kompatibles LLM (Ollama, vLLM, Cloud-Anbieter …) — nicht auf Ollama festgelegt
- 🕵️ **PII-Sanitizer (EntityGuard, optional)**: maskiert Klarnamen vor dem LLM-Call, re-injiziert sie danach wieder in die gespeicherte Zusammenfassung
- 🔐 **Datenschutz-Funktionen**: Feldweise Verschlüsselung für patientenbezogene Daten (inkl. Key-Rotation), automatische Löschung des Rohaudios nach erfolgreicher Verarbeitung. Ob ein Betrieb DSGVO-konform ist, hängt von der Konfiguration ab, siehe `docs/data-mapping.md`
- 📖 **Fachbegriff-Korrektur**: optionale phonetische Korrektur (Kölner Phonetik) mit Kategorie-Glossar und privatem Nutzer-Wörterbuch
- 🌍 **Mehrsprachige Oberfläche** (Deutsch/English) und optionaler **Desktop-Client** (`docs/client.md`)
- 🎧 **Optionaler Audio-Download**: komprimierte, verschlüsselte Kopie der Aufnahme (Format/Bitrate wählbar) in einem S3-kompatiblen Objektspeicher (self-hosted Garage per Default)
- 🏢 **Enterprise-Ready**: LDAP- und OIDC/SSO-Integration (inkl. Gruppen→Rollen-Mapping), Redis-Session-Store mit In-Memory-Fallback
- 🐳 **Cloud-Native**: Docker-Compose-Stack (lokal/Demo) und Docker-Swarm-Produktionsdeploy mit PostgreSQL

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
        G["Session Store<br/>(Redis oder In-Memory, PCM auf Disk)"]
        H[ASR Factory]
        I[Task Service]
        J[Chunk Correction Service]
        P[PII Sanitizer<br/>optional]
    end

    subgraph Database["Datenbank & Cache"]
        K[(PostgreSQL)]
        R[(Redis, optional)]
    end

    subgraph AIServices["KI-Services"]
        L[Whisper ASR<br/>GPU — Final]
        M[Parakeet-Server<br/>VAD + ONNX — Live]
        N["LLM<br/>OpenAI-kompatibel<br/>(Ollama, vLLM, Cloud, …)"]
    end

    subgraph Storage["Objektspeicher (optional)"]
        S[("S3-kompatibel<br/>Garage per Default")]
    end

    subgraph Enterprise["Auth"]
        O[LDAP/Active Directory]
        Q[OIDC/SSO-Provider]
    end

    A -->|WebSocket PCM| E
    A -->|HTTP Upload| F
    E --> G
    G -.-> R
    E --> H
    H -->|Live, WS-Streaming| M
    H -->|Final| L
    E -->|Whisper-Chunks| J
    E --> P
    P --> N
    F --> K
    F --> O
    F --> Q
    I --> N
    I --> S
```

### Transkriptions-Pipeline (Zwei-Stufen-ASR)

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant Browser as 🌐 Browser
    participant WS as 🔌 WebSocket
    participant Parakeet as 🎤 Parakeet-Server<br/>(VAD + ONNX, Live)
    participant Whisper as 🎙️ Whisper<br/>(GPU, Final)
    participant Sanitizer as 🕵️ PII-Sanitizer<br/>(optional)
    participant LLM as 🤖 LLM<br/>(OpenAI-kompatibel)
    participant DB as 🗄️ PostgreSQL

    User->>Browser: Start Recording
    Browser->>Browser: AudioWorklet (16kHz PCM)

    alt live_backend = "parakeet"
        loop Jedes PCM-Frame
            Browser->>WS: Float32-Frame
            WS->>WS: PCM auf Disk anhängen (session_{id}.pcm)
            WS->>Parakeet: Frame weiterleiten (WS-Stream)
            Parakeet-->>WS: {"partial": ...} / {"committed", "delta"}
            WS-->>Browser: Live-Transkript aktualisieren
            Note over Parakeet: Silero-VAD segmentiert an Pausen,<br/>liefert bereits fertige Interpunktion —<br/>keine LLM-Korrektur nötig
        end
    else live_backend = "api" (Whisper)
        loop Alle 3 Sekunden
            Browser->>WS: Audio-Chunk (Float32)
            WS->>WS: PCM auf Disk anhängen
            WS->>Whisper: Transcribe (live, fester Chunk)
            Whisper-->>WS: Partial Text (roh)
            WS->>WS: Batch-LLM-Korrektur (alle 5 Chunks)
            WS-->>Browser: Live-Transkript aktualisieren
        end
    end

    User->>Browser: Stop Recording
    Browser->>WS: STOP Event
    WS->>WS: PCM → WAV konvertieren
    WS->>Whisper: Transcribe (final, initial_prompt = Kategorie-Vokabular)
    Whisper-->>WS: Complete Transcript
    WS->>DB: record.content speichern (verschlüsselt)

    opt Sanitizer aktiviert
        WS->>Sanitizer: Text mit Klarnamen
        Sanitizer-->>WS: sanitisierter Text + Mapping
        WS->>DB: pii_mapping speichern (verschlüsselt)
    end

    WS->>LLM: Zusammenfassen (Kategorie-System-Prompt + Anti-Halluzinations-Regel)
    LLM-->>WS: Summary (Markdown, ggf. mit Platzhalter-Token)
    WS->>WS: Platzhalter-Token zurück zu Klarnamen (falls Sanitizer aktiv)
    WS->>DB: record.summarize speichern (verschlüsselt)
    WS->>WS: Audio-Datei löschen (DSGVO) — bei Fehler stattdessen für Retry aufbewahrt
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
| **Auth** | PyJWT + bcrypt | ≥2.10 | JWT-Token |
| **LDAP** | ldap3 | ≥2.9.1 | Enterprise-Auth |
| **OIDC/SSO** | itsdangerous + httpx + PyJWT | - | Signierter State, Token-Exchange, JWKS-Verifikation |
| **LLM-Client** | LangChain | ≥1.2.0 | LLM-Orchestrierung (jedes OpenAI-kompatible Backend, nicht nur Ollama) |
| **PII-Sanitizer-Client** | requests | - | HTTP-Client für den optionalen EntityGuard-Sanitizer |
| **Live-ASR** | Parakeet (onnx-asr, Silero-VAD) | - | VAD-segmentiertes WS-Streaming, GPU-Default mit CPU-Fallback |
| **Final-ASR** | Whisper (faster-whisper) | - | GPU-basierte Final-Transkription |
| **Verschlüsselung** | cryptography (Fernet) | - | Feldweise Encryption inkl. Key-Rotation |
| **Objektspeicher** | boto3 | - | S3-kompatibler Client für den optionalen Audio-Download (self-hosted Garage per Default) |
| **Session-Cache** | redis | - | Session-Store-Backend, optional (In-Memory-Fallback ohne `REDIS_URL`) |
| **Audio** | ffmpeg | System | Chunk-Merging, Format-Konvertierung für den Audio-Download |
| **Server** | Uvicorn | ≥0.38.0 | ASGI-Server |

### Frontend

| Komponente | Technologie | Version | Zweck |
|------------|-------------|---------|-------|
| **Framework** | React | 18.3.1 | UI-Komponenten |
| **Language** | TypeScript | ≥5.8.3 | Typsicherheit |
| **Build** | Vite | ≥5.4.19 | Dev-Server, Bundling |
| **UI-Kit** | shadcn/ui | - | Radix-basierte Components |
| **Styling** | Tailwind CSS | ≥4.3 | Utility-First CSS |
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
| **Live** | Parakeet-Server (onnx-asr, VAD-segmentiertes WS-Streaming) | GPU-Default mit CPU-Fallback | Near-Real-Time-Transkript mit Interpunktion |
| **Final** | Whisper (faster-whisper) | GPU | Hochwertige Re-Transkription des vollständigen Audios |

### ASR Factory (asr_factory.py)

Die `ASRFactory` erstellt Live- und Final-Backend unabhängig voneinander, jeweils lazy und gecacht auf der Factory-Instanz. Live wählt anhand der `live_backend`-Einstellung (`"parakeet"` | `"api"` | `"disabled"`):

```python
def _create_live_backend(self) -> ASRBackend:
    settings = get_settings()

    if settings.live_backend == "disabled":
        return DisabledBackend()

    if settings.live_backend == "parakeet":
        endpoint = settings.live_api_endpoint or env_or_file("PARAKEET_API_ENDPOINT")
        if not endpoint:
            return DisabledBackend()
        # ParakeetStreamBackend hält die WS-Verbindung zum Parakeet-Server offen
        # und relayt partial/committed/final-Nachrichten — kein fixer Chunk-Takt
        return ParakeetStreamBackend(endpoint=endpoint, api_key=settings.live_api_key)

    return DisabledBackend()  # unbekannter Wert
```

Ein Near-live-Whisper-Pfad (feste Chunks mit Überlappung und LLM-Glättung) existiert nicht mehr — Live-Text kommt ausschließlich von Parakeet. Dessen Segmentierung übernimmt intern der Parakeet-Server per Silero-VAD. Die finale Whisper-Transkription entfernt Stille dagegen immer im Backend (`vad_segmenter.py`), bevor sie an den Server geht.

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

`websocket_record()` in `backend/views/record_api/record.py` ist deutlich umfangreicher als ein einfacher Empfangs-Loop und verzweigt früh nach ASR-Backend-Typ:

- **Session-Anlage**: `session_store.get_by_session()`/`create_session()` — PCM wird immer auf Disk geschrieben (`chunks/session_{id}.pcm`), nie im RAM gehalten, unabhängig vom gewählten Session-Store-Backend (Redis speichert nur Metadaten).
- **Parakeet-Streaming-Pfad** (`isinstance(backend, ParakeetStreamBackend)`): jedes empfangene Float32-PCM-Frame wird direkt und ungepuffert an die WebSocket-Verbindung des Parakeet-Servers weitergeleitet. Der Server segmentiert intern per Silero-VAD an Sprechpausen und schickt `{"partial": ...}` (offenes Segment, alle 0.4s neu dekodiert) bzw. `{"committed": ..., "delta": ...}` (abgeschlossenes Segment) zurück — `delta` wird ans `stableTranscript` angehängt, `partial` rendert als Live-Tail. Kein LLM-Korrekturschritt, da Parakeet bereits fertige Interpunktion liefert.
- **Ohne Streaming-Session** (Live aus oder Parakeet nicht erreichbar): Die Aufnahme läuft weiter und wird gespeichert, es gibt nur keinen Live-Text. Die finale Transkription hängt nicht davon ab.
- **Kein `initial_prompt` im Live-Pfad**: Whisper neigt dazu, den Prompt-Text zu wiederholen, was im Live-Transkript zu Duplikaten führt — anders als bei der finalen Transkription, wo `category.whisper_prompt` als Vokabular-Hint übergeben wird.
- **Beenden**: Auf ein `STOP`-Event bzw. Verbindungsabbruch konvertiert `finalize()` die PCM-Datei zu WAV und startet `background_transcription_task` als Hintergrund-Task (finale Whisper-Transkription → optionale PII-Sanitisierung → LLM-Zusammenfassung → optionale Audio-Persistierung). Die WAV-Datei wird bei Erfolg gelöscht, bei einem Fehler stattdessen für einen manuellen Retry aufbewahrt (siehe Abschnitt „Audio-Download").

### Latenz-Profil

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ ZWEI-STUFEN LATENZ-PROFIL                                │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  STAGE 1: LIVE (Parakeet, GPU empfohlen)                      │
│  Komponente              │ Latenz      │ Optimierung       │
│  ────────────────────────┼─────────────┼──────────────────  │
│  Audio-Capture (Browser) │   10-20ms   │ 16kHz direkt      │
│  WebSocket RTT           │    5-10ms   │ Lokales Netzwerk  │
│  Parakeet Inferenz       │ hardwareabh.│ GPU; CPU zu langsam│
│  Response-Serialization  │    5-10ms   │ JSON minimal      │
│  ────────────────────────┼─────────────┼──────────────────  │
│  Gesamt (Live)           │ nicht gemessen│ Kein LLM nötig   │
│                                                               │
│  STAGE 2: FINAL (Whisper, GPU)                              │
│  Komponente              │ Latenz      │ Optimierung       │
│  ────────────────────────┼─────────────┼──────────────────  │
│  PCM → WAV Konvertierung │   50-100ms  │ numpy + struct    │
│  Whisper Inferenz        │    2-10s    │ GPU (CUDA)        │
│  LLM Zusammenfassung    │    3-15s    │ abhängig vom Endpunkt │
│  ────────────────────────┼─────────────┼──────────────────  │
│  Gesamt (Final)          │   ~5-25s    │ Hintergrund-Task  │
│                                                               │
│  🔧 Optimierungspotenzial (Live):                              │
│  • Chunk auf 2s reduzieren (höhere CPU-Last)                   │
│  • Parakeet-Modell austauschbar via PARAKEET_MODEL             │
└─────────────────────────────────────────────────────────────┘
```

**Warum zwei Stufen?**
- **Parakeet (Live):** liefert Sätze mit Interpunktion ohne LLM-Korrekturschritt. Echtzeitfähig ist das nur **mit GPU**: auf der CPU läuft der Dienst (CPU-Image oder GPU-Image ohne GPU), kommt mit dem Re-Decode des offenen Segments alle 0,4 s aber nicht hinterher, und der Live-Text erscheint stark verzögert. Auf Hosts ohne GPU die Live-Transkription abschalten (Admin → Dienste → Whisper → `live_backend` = „disabled“, oder der Client verbindet mit `?live=0`); die finale Transkription nach dem Stopp ist davon unabhängig
- **Whisper (Final):** GPU-beschleunigt, höhere Qualität für die endgültige Transkription und Zusammenfassung

---

## Parakeet ASR Server (Eigenständiger Dienst)

Der Parakeet-Server ist ein eigenständiger FastAPI-Dienst (`parakeet_server/main.py`, Port 5001) mit zwei Endpunkten: dem OpenAI-kompatiblen `POST /v1/audio/transcriptions` (One-Shot, für die finale/Batch-Nutzung) und `WS /v1/audio/stream` (VAD-segmentiertes Streaming, siehe `parakeet_server/streaming.py`) — letzterer ist der eigentliche Live-Pfad, den `ParakeetStreamBackend` nutzt. Silero-VAD + Parakeet-ONNX (onnx-asr) werden beim Start geladen; der Dockerfile-Default ist die NVIDIA-GPU-Base (CUDA 13.0.2 + cuDNN auf Ubuntu 24.04, Host-Treiber ≥ 580) mit automatischer `CUDAExecutionProvider`-Wahl und CPU-Fallback (`PARAKEET_DEVICE=cpu` für ein reines CPU-Image).

### Architektur

```mermaid
graph LR
    subgraph Backend["openDox Backend"]
        A[ASR Factory]
        B[ParakeetStreamBackend]
    end

    subgraph Parakeet["Parakeet Server (Port 5001)"]
        C["WS /v1/audio/stream"]
        C2["POST /v1/audio/transcriptions<br/>(One-Shot, OpenAI-kompatibel)"]
        VAD[Silero VAD]
        D[get_model - Dict Cache]
        E[onnx_asr Model]
    end

    A -->|live_backend="parakeet"| B
    B -->|WS, jedes PCM-Frame| C
    C --> VAD
    VAD -->|Segment an Sprechpause| D
    D --> E
    E -->|partial / committed / final| C
```

### Implementation: One-Shot-Endpunkt (parakeet_server/main.py)

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
- **Lifespan:** Default-Modell wird beim Start vorgeladen, bei Shutdown freigegeben
- **PCM → WAV:** Akzeptiert rohes Float32-PCM (16kHz, Mono) oder WAV-Dateien
- **GPU-Default mit CPU-Fallback:** `CUDAExecutionProvider` wird automatisch gewählt, wenn verfügbar. Der CPU-Fallback ist für Tests und den One-Shot-Endpunkt gedacht, nicht für Live-Streaming (zu langsam)

### Streaming-Endpunkt (WS /v1/audio/stream)

Der eigentliche Live-Pfad: `record.py` leitet jedes empfangene Float32-PCM-Frame direkt an diese WebSocket-Verbindung weiter. `StreamingSession` (`parakeet_server/streaming.py`) kombiniert Silero-VAD mit dem Parakeet-ONNX-Modell:

- **Segmentierung an Sprechpausen** statt festem Zeit-Chunking
- **Offenes Segment**: wird alle 0.4s neu dekodiert und als `{"partial": <Text>}` zurückgeschickt (Live-Tail im Frontend)
- **Abgeschlossenes Segment**: bei erkannter Pause committed und als `{"committed": ..., "delta": ...}` zurückgeschickt — `record.py` hängt `delta` an `stableTranscript` an
- **Ende der Aufnahme**: `{"final": ...}`
- Die Segmentierung ist vollständig serverseitig

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
    
    Fallback when REDIS_URL is unset (single instance only).
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

## Authentifizierung: Local, LDAP, OIDC

Drei Methoden, in dieser Reihenfolge in `auth_routes.py:login()` durchprobiert:

### 1. Local DB

Bcrypt-gehashtes Passwort in `User.hashed_password`.

### 2. LDAP (`ldap.py`)

Kein generisches `LdapService` mit Format-String-Filter, sondern gezielt gegen AD/OpenLDAP+memberof-Overlay gebaut:

```python
# ldap.py — vereinfachter Ablauf von authenticate()
def authenticate(self, username: str, password: str):
    # RFC 4513 "unauthenticated bind": SIMPLE-Bind mit non-empty DN + leerem
    # Passwort wird von vielen Servern als Erfolg gewertet — hier vorher geblockt.
    if not password:
        return {"success": False, ...}

    safe_username = escape_filter_chars(username)
    user_filter = f"({self.settings.user_dn}={safe_username})"
    if self.settings.search_filter:
        user_filter = f"(&{user_filter}({self.settings.search_filter}))"

    # Service-Account-Bind, dann Suche
    conn = self.connect()  # bind_user_dn/bind_user_password (optional)
    conn.search(self.settings.base_dn, user_filter, attributes=[self.settings.user_dn, "memberOf"])
    entry = conn.entries[0]
    user_dn = entry.entry_dn
    member_of = getattr(entry, "memberOf", None)

    # Passwort-Verifikation: Bind als der gefundene User selbst
    Connection(conn.server, user=user_dn, password=password, auto_bind=True)

    # Rollen-Mapping: App baut die erwartete Group-DN selbst (cn={name},{base_dn}) —
    # Admins tragen nur Klartext-Gruppennamen ein, nie eine DN
    allowed = _parse_groups(self.settings.allowed_groups)   # Gate (UI: „User-Gruppen“); Zugang nur für Mitglieder von allowed/admin/moderator, ohne Gruppe niemand
    admin = _parse_groups(self.settings.admin_groups)       # Rollen-Mapping, Admin hat Vorrang
    moderator = _parse_groups(self.settings.moderator_groups)
```

Nutzer werden beim ersten erfolgreichen Login auto-provisioniert (leerer Passwort-Hash); die Rolle wird bei **jedem** Login aus der aktuellen Gruppenmitgliedschaft neu synchronisiert. Das optionale LDAPS-CA-Zertifikat liegt **in der DB** (`LdapSettingsModel.cert_data`, Upload via `POST /ldap-settings/upload-cert/`), nie auf der Platte — `cert_filename` ist nur ein Anzeige-Label.

`LdapSettingsModel` (`models/ldap_model.py`): `server_host`/`server_port`/`use_ssl`, `base_dn`, `user_dn` (Attributname, z. B. `uid` oder `sAMAccountName`), `search_filter` (optionaler Power-User-Zusatzfilter), `bind_user_dn`/`bind_user_password` (Service-Account, verschlüsselt), `cert_filename`/`cert_data`, `allowed_groups`/`admin_groups`/`moderator_groups`, `nested_groups` (nur Active Directory: verschachtelte Gruppen über `LDAP_MATCHING_RULE_IN_CHAIN`).

### 3. OIDC/SSO (`oidc_bp`, `/api/v1/auth/oidc/{login,callback,status}`)

Authorization-Code-Flow mit Discovery (`{provider_url}/.well-known/openid-configuration`). Der `state`-Parameter wird mit `SECRET_KEY` über `itsdangerous.URLSafeSerializer` signiert und in einem kurzlebigen Cookie gespeichert. Der Callback stellt lokale JWTs aus und leitet auf `/login?access_token=...&refresh_token=...` weiter — das Frontend (`Login.tsx`) liest die Query-Parameter und speichert sie in `localStorage`. `OidcSettingsModel.admin_groups`/`moderator_groups` mappen OIDC-Gruppen auf Rollen, gleiche Admin-hat-Vorrang-Logik wie bei LDAP. `allowed_groups` (UI: „User-Gruppen“) bildet auch hier das Gate: nur Mitglieder von allowed/admin/moderator dürfen sich anmelden (403 sonst), ohne konfigurierte Gruppe niemand. Nutzer werden beim ersten Login auto-provisioniert; der OIDC-Button in `Login.tsx` erscheint nur, wenn `/oidc/status` `{"enabled": true}` liefert.

`_build_redirect_uri()` respektiert `X-Forwarded-Proto`/`X-Forwarded-Host` **nur**, wenn der unmittelbare Peer ein vertrauenswürdiger Reverse-Proxy ist (`TRUSTED_PROXY_IPS`) — sonst wären diese Header vom Client fälschbar und könnten den OIDC-Callback umleiten.

### Vergleich: Local vs. LDAP vs. OIDC

```
┌─────────────────────────────────────────────────────────────┐
│  🔐 AUTHENTICATION COMPARISON                               │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  Feature                │ Local │ LDAP           │ OIDC     │
│  ───────────────────────┼───────┼────────────────┼──────────│
│  Setup-Aufwand           │ ✅ einfach │ ⚠️ moderat  │ ⚠️ moderat│
│  Passwort-Verwaltung     │ ❌ manuell │ ✅ zentral  │ ✅ zentral│
│  Single Sign-On          │ ❌ nein    │ ❌ nein     │ ✅ ja     │
│  Gruppen→Rollen-Mapping  │ –          │ ✅ ja       │ ✅ ja     │
│  Auto-Provisioning       │ ❌ manuell │ ✅ ja       │ ✅ ja     │
│  Offline-fähig           │ ✅ ja      │ ✅ ja       │ ❌ nein   │
│                                                               │
│  Alle drei Methoden sind gleichzeitig aktivierbar — login()  │
│  probiert Local → LDAP → OIDC in dieser Reihenfolge.         │
└─────────────────────────────────────────────────────────────┘
```

---

## Kategorien & LLM-Prompt-Komposition

`Categories`-Zeilen (`backend/components/models/categories.py`) erfüllen vier Rollen pro Aufnahme, einmal beim Aufnahmestart gewählt (Kategorie-`<Select>` in `Dashboard.tsx`) und nachträglich änderbar über `PUT /record/{id}`:

1. **`whisper_prompt`** → als `initial_prompt` an Whisper übergeben (Vokabular-/Rechtschreib-Hinweise für die finale Transkription). Faster-whisper behält davon nur die letzten 224 Tokens (last-N-Truncation, ohne Warnung) — daher bewusst kurz halten.
2. **`glossary`** → Quelltext für die phonetische Fachbegriff-Korrektur (`term_correction_service.py`, Kölner Phonetik) — bewusst getrennt von `whisper_prompt`, da hier kein Längenlimit gilt. Wird zur Korrekturzeit mit dem privaten „Mein Wörterbuch" (`User.personal_glossary`, `GET`/`PUT /api/v1/settings/my-dictionary/`, nur für den jeweiligen User sichtbar, auch nicht für Admins) zusammengeführt.
3. **`system_prompt`** → der LLM-System-Prompt für die Zusammenfassung (`SummarizeModel.generate_response(custom_system_prompt=...)`). Fällt nur auf `SummarizeModel.get_system_prompt()` zurück (ein generischer, nicht-medizinischer „nur bereinigen und strukturieren"-Prompt), wenn `record.category_id` leer ist oder die Kategorie keinen `system_prompt` hat — in der Praxis selten, da die UI immer eine Kategorie vorbelegt.
4. **`llm_override_enabled`** + `llm_model`/`llm_api_endpoint`/`llm_api_key`/`llm_temperature`/`llm_max_tokens` → optionaler Per-Kategorie-LLM-Backend-Override, z. B. um „Kardiologie" auf ein anderes Modell/Endpoint zu routen als den globalen Default.

**Platzhalter-Halluzination wird im Code erzwungen, nicht im Prompt-Text:** `generate_response()` hängt unconditional eine Anti-Halluzinations-Regel an **jeden** Prompt an (keine erfundenen `[DATUM]`/`[WERT]`-Platzhalter für fehlende Informationen, aber bestehende EntityGuard-Token wie `[PERSON]`/`[LOCATION]` bleiben ausdrücklich erhalten) — direkt neben der bestehenden „Do not output your reasoning"-Unterdrückung. Grund: ein Admin, der über die Admin-UI eine neue Kategorie mit eigenem `system_prompt` anlegt, hat keine Möglichkeit zu wissen, dass das lokale Modell zu solchen Platzhaltern neigt — die Regel darf sich also nicht darauf verlassen, im Prompt-Text zu stehen.

---

## PII-Sanitizer (EntityGuard, optional)

Maskiert Klarnamen im Transkript, bevor der Text ein (ggf. externes) LLM erreicht, und injiziert sie danach wieder in die gespeicherte Zusammenfassung zurück. Vollständiger Ablauf inkl. Mermaid-Diagramm: [`docs/pii.md`](pii.md).

1. `background_transcription_service.py` transkribiert per Whisper → `record.content` (Klarnamen, verschlüsselt gespeichert).
2. Ist der Sanitizer aktiviert (`sanitizing_service.py`), wird der Text an den konfigurierten Sanitizer-Endpunkt gepostet, der `sanitized_text` (Token wie `[PERSON_1]`) und idealerweise ein `mapping`-Dict zurückgibt.
3. Fehlt `mapping`, rekonstruiert `_extract_mapping()` es per Wort-Level-Diff (`difflib.SequenceMatcher`) — best-effort, verwirft bewusst mehrdeutige benachbarte Treffer statt zu raten. Ergebnis verschlüsselt in `record.pii_mapping`.
4. Das LLM sieht nur `sanitized_text` + eine Instruktion, die Token unverändert zu lassen → `summary_anonymized`.
5. `reinject()` ersetzt die Token per String-Replace zurück durch Klarnamen → `record.summarize` (Klarnamen, verschlüsselt).

Konfiguriert über Admin-UI → LLM-Einstellungen → PII-Sanitizer. `sanitizer_endpoint` ist eine **vollständige URL** (kein automatisch angehängter Pfad). Tokens müssen pro Vorkommen eindeutig sein (`PERSON_1`/`PERSON_2`, nicht zweimal `PERSON`), sonst kollidieren mehrere Vorkommen im Mapping.

---

## Audio-Download (S3-kompatibler Objektspeicher)

Optionales Feature (`AudioSettingsModel`: `audio_download_enabled`, `audio_bitrate` bis `320k`, `audio_sample_rate`, `audio_format`), das eine komprimierte, verschlüsselte Kopie der finalen Aufnahme für den späteren Download aufbewahrt — getrennt vom rohen PCM/WAV.

1. Nach erfolgreicher finaler Transkription wandelt `background_transcription_service.py:_persist_audio()` das Audio per ffmpeg um (mono, konfigurierbare Bitrate/Sample-Rate/Format: MP3/WAV/FLAC/OGG) — in eine `tempfile.NamedTemporaryFile`, nie einen festen Pfad.
2. Die Bytes werden mit `field_encryption.encrypt_bytes()` verschlüsselt (gleicher `ENCRYPTION_KEY` wie Text-Felder) und über `audio_storage.py` (dünner boto3-Wrapper) unter dem Key `records/{id}.{ext}.enc` hochgeladen.
3. `record.file` speichert diesen **S3-Object-Key** (das `.{ext}.`-Segment ist die Quelle der Wahrheit für das gespeicherte Format), keinen Dateisystempfad.
4. `GET /record/{id}/audio` lädt das verschlüsselte Objekt, entschlüsselt und streamt zurück — der Klartext berührt serverseitig nie die Platte. `Content-Type`/Dateiendung werden aus dem Key abgeleitet, nicht hartkodiert.
5. `delete_record` löscht das S3-Objekt statt einer lokalen Datei.

Jedes S3-kompatible Backend funktioniert (generisches boto3); `docker-compose.yml`/`docker-swarm.yml` bündeln standardmäßig **Garage** (self-hosted, AGPL) statt MinIO (Lizenzeinschränkungen).

**Failsafe bei fehlgeschlagener Transkription:** Die rohe WAV-Datei wird nur bei **erfolgreicher** Verarbeitung gelöscht — bei einem Fehler wird sie stattdessen unverschlüsselt in `chunks/failed/task_{id}.wav` aufbewahrt (kein automatisches Ablaufdatum), damit nichts verloren geht. Admin-only `GET /tasks/failed` listet solche Tasks, `POST /tasks/{id}/retry` stößt die Pipeline erneut auf der aufbewahrten Datei an (Frontend: `FailedTranscriptions.tsx`, unterhalb der Audio-Einstellungen im Admin-„Audio"-Tab).

---

## System-Health-Check

`GET /api/v1/settings/services-health/` (`settings_routes.py`) treibt den Admin-„System"-Tab (`SystemSettings.tsx`, alle 10s gepollt) — ein `async def check_x()`-Closure pro Dienst (Postgres, Redis, Whisper, Parakeet, EntityGuard, S3, Verschlüsselungs-Key-Status), alle parallel über `asyncio.gather`. Jeder liefert `"online"`/`"offline"`/`"disabled"` — `"disabled"` wird zurückgegeben, **bevor** ein Netzwerk-Call versucht wird, wenn ein Feature gar nicht konfiguriert ist (z. B. `audio_storage.is_configured()` für S3), damit ein bewusst deaktiviertes Feature nicht als falsches „offline" erscheint. Das Frontend ist vollständig generisch — es rendert einfach die zurückgegebene `{name, status}`-Liste, ein neuer Check erfordert also nur Backend-Änderungen.

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

> **Wichtig:** `ENCRYPTION_KEY` ist Pflicht. Ist er nicht gesetzt, leer oder kein gültiger Fernet-Key, startet die App nicht (kritischer Log-Eintrag, `EncryptionKeyError`). Eine Klartext-Speicherung durch fehlende Konfiguration gibt es nicht.

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

    # 🔒 VERSCHLÜSSELT: Patientenbezogene Daten
    title: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    content: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    summarize: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    pii_mapping: Optional[str] = Field(sa_column=Column(EncryptedString, nullable=True))

    # Unverschlüsselt (Metadaten, kein Inhalt)
    timestamp: str
    file: str  # S3-Object-Key, kein Inhalt — das referenzierte Audio ist separat verschlüsselt
    archived: bool = Field(default=False)
```

`encrypt()`/`decrypt()` arbeiten auf `str` (Basis für `EncryptedString`). Die binärsicheren Geschwister `encrypt_bytes()`/`decrypt_bytes()` nutzen denselben Key für rohe Bytes — verwendet von `audio_storage.py` für die persistierten Audio-Downloads (siehe Abschnitt „Audio-Download" oben).

### Key-Rotation

`ENCRYPTION_KEY` ist rotierbar, ohne den Betrieb zu unterbrechen: `ENCRYPTION_KEY_PREVIOUS` (bzw. das `_FILE`-Pendant) neben dem neuen Key setzen, App neu starten. Beim Start erkennt die App über einen in `EncryptionKeyState` gespeicherten Fingerprint einen Key-Wechsel und **re-verschlüsselt** alle verschlüsselten Spalten in-place (`Record.title`/`content`/`summarize`/`pii_mapping`, `User.personal_glossary`, LDAP-Bind-Passwort, OIDC-Client-Secret) mit dem neuen Key (`backend/components/security/key_rotation.py`). Der Vorgang ist idempotent und unterbrechungssicher — ein abgebrochener Lauf setzt beim nächsten Start mit denselben Key-Werten fort. **Nicht** von diesem automatischen Pass erfasst: das persistierte Audio in S3 (`audio_storage.py`) — es wird bei Upload/Download ver-/entschlüsselt, nicht beim Rotieren erneut umverschlüsselt. Verifikation nach einer Rotation: `GET /api/v1/settings/services-health/` — der `"Verschlüsselung"`-Eintrag muss `"online"` sein.

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
│     ✅ ENCRYPTION_KEY ist Pflicht (App startet sonst nicht)   │
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
│     ⚠️  Altdaten im Klartext bleiben lesbar, nicht nachverschlüsselt │
│                                                               │
│  ✅ Dokumentation (Art. 30 DSGVO)                            │
│     - Datenfluss-Dokumentation: docs/data-mapping.md          │
│     - Sicherheitsmaßnahmen: SECURITY.md                       │
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
- `Record.title` – Titel der Aufnahme
- `Record.pii_mapping` – Token→Klarname-Mapping des PII-Sanitizers
- `User.personal_glossary` – privates Korrektur-Wörterbuch
- `LdapSettingsModel.bind_user_password`, `OidcSettingsModel.client_secret`
- Persistiertes Audio im Objektspeicher (`encrypt_bytes()`, siehe Audio-Download)

**Was ist NICHT verschlüsselt?**
- `Record.timestamp` – Zeitstempel (Metadaten)
- `User.name` – Benutzername (Referenz für Zugriffskontrolle)
- API-Keys in den Settings (`llm_api_key`, `sanitizer_api_key`, `live_api_key`, `final_api_key`, `Categories.llm_api_key`) – Klartext in der DB; per API nur für Admins lesbar
- PCM/WAV in `chunks/` – unverschlüsselt, aber kurzlebig (siehe Aufbewahrung in `docs/data-mapping.md`)

**Warum Feldweise Verschlüsselung?**
- 🔍 **Suche erhalten:** Nicht-verschlüsselte Felder bleiben durchsuchbar
- 📊 **Analytics:** Metadaten für Statistiken nutzbar
- 🔄 **Migration:** Abwärtskompatibel (Fallback auf Plaintext)

---

## Deployment-Reifegrad

Frühere Fassungen dieses Dokuments beschrieben Redis, LDAP und Multi-Instance-Deployment als zukünftige „Phase 2"-Ziele — das ist überholt: alle drei sind implementiert und Teil des Standard-Stacks. Aktueller Stand:

```mermaid
graph LR
    subgraph Compose["docker-compose.yml — lokal/Demo"]
        A[Browser] -->|HTTP/WebSocket| B["FastAPI (replicas: 1)"]
        B --> C[(PostgreSQL)]
        B --> R[(Redis)]
        B --> D[Whisper — Final, GPU]
        B --> E[Parakeet-Server — Live]
        B --> S[(Garage/S3)]
        B --> F[LDAP/OIDC]
        B --> G["LLM<br/>OpenAI-kompatibel"]
    end

    style Compose fill:#e8f5e9
```

**Bereits produktiv verfügbar (nicht mehr geplant):**
- ✅ Redis-Session-Store mit In-Memory-Fallback (`REDIS_URL`)
- ✅ LDAP- **und** OIDC/SSO-Integration, gleichzeitig aktivierbar, mit Gruppen→Rollen-Mapping
- ✅ Docker-Swarm-Produktionsdeploy (`docker-swarm.yml`, `create_docker_secrets.sh`) mit echten Secrets statt Klartext-Defaults, GPU-Placement-Constraints, versionsfixierten Images
- ✅ Verschlüsselungs-Key-Rotation ohne Downtime
- ✅ System-Health-Check-Endpoint für alle Kernservices

**Bewusst außerhalb des aktuellen Scopes** (`app` ist unter Swarm auf `replicas: 1` gepinnt — der PCM-Chunk-Ordner ist lokal-disk-only, siehe `chunks/`): horizontale Skalierung auf mehrere App-Instanzen. Voraussetzungen dafür wären u. a. Sticky-WebSocket-Routing, geteilter Storage für laufende Aufnahmen und Multi-Replica-Cache-Invalidierung.

---

## Production Readiness Checklist

```
┌─────────────────────────────────────────────────────────────┐
│  🚀 PRODUCTION READINESS CHECKLIST                           │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  SECURITY 🔐                                                 │
│  ├─ [✅] JWT Authentication                                 │
│  ├─ [✅] LDAP- und OIDC/SSO-Integration                     │
│  ├─ [✅] Field Encryption (Fernet) inkl. Key-Rotation       │
│  ├─ [✅] HTTPS Enforcement (Reverse-Proxy)                   │
│  ├─ [⚠️ ] Rate-Limiting (nur /login, in-process; sonst Proxy)│
│  ├─ [⚠️ ] Audit-Logging (TODO: who accessed what when)      │
│  └─ [⚠️ ] CSP Headers (TODO: Content-Security-Policy)       │
│                                                               │
│  RELIABILITY 🛡️                                              │
│  ├─ [✅] Health/Version-Endpoints (/api/endpoint,           │
│  │       /api/version, /api/v1/settings/services-health/)  │
│  ├─ [✅] Readiness-Probe /api/ready (503 bei DB/Redis-Ausfall) │
│  ├─ [✅] Redis Session Store (REDIS_URL → Redis, else In-Memory) │
│  ├─ [⚠️ ] Circuit Breaker (TODO: for external services)   │
│  └─ [⚠️ ] Retry Logic (TODO: exponential backoff, außer dem │
│  │       manuellen Transkriptions-Retry für fehlgeschlagene │
│  │       Tasks, siehe Audio-Download)                        │
│                                                               │
│  SCALABILITY 📈                                               │
│  ├─ [⚠️ ] Nicht stateless: laufende Aufnahmen liegen lokal │
│  ├─ [✅] Redis for Sessions (REDIS_URL, else In-Memory fallback) │
│  ├─ [⚠️ ] Load-Balancer Config (TODO: Traefik)              │
│  └─ [⚠️ ] Auto-Scaling Rules (TODO: K8s HPA)               │
│                                                               │
│  MONITORING 📊                                                │
│  ├─ [✅] Basic Logging (Python stdlib, uvicorn-Format)    │
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
│  ├─ [✅] Datenfluss-Dokumentation (Art. 30 DSGVO):        │
│  │       docs/data-mapping.md                               │
│  └─ [⚠️ ] Data Processing Agreement (TODO: DPA — hängt    │
│  │       von der konkreten Betreiber-Konfiguration ab)     │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Legend:
[✅] Implemented and tested
[⚠️ ] TODO or needs improvement
```

---

## API-Referenz

> Vollständig aus den aktuellen Router-Definitionen (`backend/views/*/`) erhoben — nicht handgepflegt. `/upload-chunk` aus früheren Doku-Fassungen ist **entfernt** (unbenutzt, leakte `.webm`-Dateien).

### Öffentlich (kein Router-Präfix)

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/api/endpoint` | Liveness |
| GET | `/api/version` | App-Version aus `pyproject.toml` |
| GET | `/api/ready` | Readiness-Probe (503, wenn DB oder Redis nicht erreichbar) |

### Authentication (`/api/v1/auth`)

| Methode | Pfad | Beschreibung | Auth |
|---------|------|--------------|------|
| POST | `/login` | Login (Local → LDAP → OIDC) | ❌ |
| POST | `/refresh` | Token refreshen | ❌ |
| POST | `/accept-disclaimer` | „Kein Medizinprodukt"-Hinweis bestätigen (Pflicht vor erster Nutzung) | ✅ |
| GET | `/me` | Aktueller Benutzer | ✅ |
| GET | `/users`, `/users/{id}` | Benutzerliste/-detail (Admin) | ✅ (Admin) |
| POST/PUT/DELETE | `/users`, `/users/{id}` | Benutzer anlegen/ändern/löschen (Admin) | ✅ (Admin) |

**OIDC** (`/api/v1/auth/oidc`): `GET /login`, `GET /callback`, `GET /status`.

### Records (`/api/v1/records`)

| Methode | Pfad | Beschreibung | Auth |
|---------|------|--------------|------|
| POST | `/create` | Neue Aufnahme anlegen (Recorder-Flow) | ✅ |
| POST | `/upload` | Vollständige Audiodatei hochladen (Alternative zum Live-Recorder) | ✅ |
| GET | `/active-session/{user_id}` | Aktive Session abrufen | ✅ |
| DELETE | `/cancel-session/{user_id}` | Session abbrechen | ✅ |
| WS | `/ws/record` | WebSocket für Live-Aufnahme + -Transkript (`?live=0`: nur aufzeichnen, keine Live-Transkription) | ✅ |
| GET | `/list-records/{user_id}` | Aufnahmen auflisten (`?archived=`) | ✅ |
| GET | `/by-session/{session_id}` | Nach Session-ID suchen | ✅ |
| GET | `/record/{id}` | Einzelne Aufnahme | ✅ |
| PUT | `/record/{id}` | Aufnahme updaten (Content/Summary/Titel/**Kategorie**) | ✅ |
| DELETE | `/record/{id}` | Aufnahme löschen | ✅ |
| PUT | `/record/{id}/archive`, `/record/{id}/unarchive` | Archivieren/De-Archivieren | ✅ |
| GET | `/record/{id}/audio` | Persistiertes Audio herunterladen (falls Feature aktiv) | ✅ |
| POST | `/record/{id}/summarize` | Zusammenfassung neu generieren | ✅ |
| GET | `/status/{task_id}` | Task-Status (Transkription/LLM) | ✅ |
| GET | `/tasks/failed` | Fehlgeschlagene Transkriptionen mit aufbewahrter Audiodatei | ✅ (Admin) |
| POST | `/tasks/{id}/retry` | Transkription auf aufbewahrter Audiodatei erneut anstoßen | ✅ (Admin) |

### Settings (`/api/v1/settings`, meist Admin only)

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET/PUT | `/whisper-settings/` | Whisper-Konfiguration |
| GET | `/asr-test/` | ASR-Endpunkt-Erreichbarkeit prüfen |
| GET/PUT | `/llm-settings/` | LLM-Konfiguration |
| GET | `/llm-test/` | Echter Chat-Completion-Probe gegen den konfigurierten LLM-Endpunkt |
| GET/PUT | `/audio-settings/` | Audio-Download-Konfiguration (Format/Bitrate/Sample-Rate) |
| GET/PUT | `/ldap-settings/` | LDAP-Konfiguration |
| POST | `/ldap-settings/test` | LDAP-Bind testen |
| POST | `/ldap-settings/upload-cert/` | LDAPS-CA-Zertifikat hochladen (landet in der DB, nicht auf Disk) |
| GET/PUT | `/oidc-settings/` | OIDC-Konfiguration |
| GET/POST/PUT/DELETE | `/categories/`, `/categories/{id}` | Kategorien (Whisper-/Glossar-/LLM-Prompts, siehe Abschnitt „Kategorien") |
| GET/PUT | `/my-language/` | UI-Sprache des angemeldeten Users (`User.ui_language`) |
| GET/PUT | `/client-config/` | Richtlinie für den Desktop-Client (GET ohne Login, PUT nur Admin) |
| GET | `/client-distribution/` | Installer-Links, `settings.json` und Intune-/SCCM-Befehle für den Desktop-Client (Admin) |
| GET/PUT | `/my-dictionary/` | Eigenes, privates Korrektur-Wörterbuch des angemeldeten Users (nie für Admins sichtbar) |
| GET/POST/PUT/DELETE | `/languages/`, `/languages/{id}` | Sprachen |
| GET | `/backup/` | Alle Settings-Tabellen als JSON exportieren |
| POST | `/backup/restore/` | Settings-Backup importieren |
| GET | `/services-health/` | Systemstatus aller Kerndienste (siehe Abschnitt „System-Health-Check") |

---

## Entwicklungsbefehle

### Backend

```bash
# Environment kopieren
cp .env.example .env

# Dependencies installieren (legt .venv aus uv.lock an)
uv sync

# Development Server mit Hot-Reload (ohne Reload: uv run main.py)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 5000

# Datenbank-Migrationen (nach jeder SQLModel-Änderung)
uv run alembic revision --autogenerate -m "Beschreibung"
uv run alembic upgrade head

# Lint (ruff-Config in pyproject.toml)
uv run ruff check --fix .
uv run ruff format .

# Tests
uv run pytest tests/         # alle Tests
uv run pytest tests/llm/     # ein Package
uv run pytest -k "test_name" # ein einzelner Test
```

CI (`.github/workflows/ci.yml`): Backend (ruff + pytest) und Frontend (vitest + eslint) laufen bei jedem Push/PR auf `master`.

### Frontend

```bash
cd frontend

# Dependencies installieren
npm install

# Development Server (Port 3000, Proxy zu :5000)
npm run dev

# Lint
npm run lint

# Tests (vitest)
npm run test

# Production Build (Output: ../backend/static/, NICHT frontend/dist)
npm run build
```

### Docker

`docker-compose.yml` liegt am **Repo-Root** (nicht in `docker/`) — das ist der lokale/Demo-Stack:

```bash
# Gesamter Stack (Postgres + Redis + Garage + Whisper + Parakeet + App)
docker compose up --build

# Logs / stoppen
docker compose logs -f app
docker compose down
docker compose down -v   # ⚠️ Datenverlust (Volumes)
```

`docker/docker-whisper.yml` und `docker/docker-parakeet.yml` sind ältere, eigenständige Standalone-Compose-Dateien für isolierte Dienst-Entwicklung (Ports 9100/9200) — vermutlich abgelöst durch `whisper_server/docker-compose.yml`, das denselben Port (5002) wie der Hauptstack erwartet.

**Produktion (Docker Swarm):** eigene `docker-swarm.yml` statt `docker-compose.yml` — echte Secrets statt Klartext-Defaults, versionsfixierte Images, GPU-Placement-Constraints:

```bash
docker swarm init                        # einmalig pro Manager-Node
./create_docker_secrets.sh               # einmalig — erzeugt alle benötigten Secrets
export OPENDOX_VERSION=$(python3 scripts/bump_version.py --current)
docker stack deploy -c docker-swarm.yml opendox
```

**App-Version bumpen** (einzige Quelle der Wahrheit: `pyproject.toml`, synct `frontend/package.json` + Lockfile):

```bash
python scripts/bump_version.py --current       # aktuelle Version anzeigen
python scripts/bump_version.py patch|minor|major
python scripts/bump_version.py patch --commit  # zusätzlich git add+commit+tag
```

---

## Bekannte Probleme & Lösungen

### 1. Dev-Server: Hot-Reload braucht den Import-String

✅ **Mit Reload:** `uv run uvicorn main:app --reload --host 0.0.0.0 --port 5000`  
✅ **Ohne Reload:** `uv run main.py` (startet die App genau einmal)

**Grund:** `main.py` erzeugt `app = create_app()` auf Modulebene und übergibt das Objekt an `uvicorn.run()`; Reload funktioniert nur mit dem Import-String `main:app`. Eine doppelte Initialisierung gibt es dabei nicht.

### 2. Port 9000 Konflikt (Whisper) — nur bei der alten Standalone-Compose

Betrifft `docker/docker-whisper.yml` (Port 9100 → Container 9000, Port 9000 ist oft von Jupyter belegt) — der Hauptstack (`docker-compose.yml` am Repo-Root) nutzt bereits Port 5002 intern und ist davon nicht betroffen.

**Lösung (nur für die Standalone-Datei):**
```yaml
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

❌ **Falsch:** `SummarizeModel` als Singleton wiederverwenden
✅ **Richtig:** `SummarizeModel()` in `background_transcription_service.py` pro Task frisch erstellen

**Grund:** DB-Settings werden sonst nicht neu eingelesen — Updates an LLM-Endpoint/Modell/Key würden erst nach einem Neustart greifen. Trotz des Namens ist `SummarizeModel` nicht auf Ollama beschränkt — jedes OpenAI-kompatible Backend funktioniert.

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

### 9. Parakeet-Build-Context (✅ behoben)

Frühere Fassungen dieser Doku beschrieben ein leeres `docker/parakeet-server/`-Verzeichnis als Build-Context-Problem. Das ist gelöst: `docker-compose.yml` (Repo-Root) nutzt für alle Services Build-Context `.` mit explizitem `dockerfile:`-Pfad (`parakeet_server/Dockerfile`, `whisper_server/Dockerfile`, `Dockerfile`).

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

### 14. App startet nicht: ENCRYPTION_KEY fehlt

Ohne gültigen `ENCRYPTION_KEY` (bzw. `ENCRYPTION_KEY_FILE`) bricht der Start mit `EncryptionKeyError` ab. Key erzeugen: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` und in `.env` (Entwicklung) oder als Docker-Secret eintragen. Beim Docker-Compose-Stack ist die Variable in `.env` Pflicht.

### 15. Frontend-Build: Output geht nach `../backend/static`, nicht `frontend/dist`

`vite.config.ts` konfiguriert `outDir: path.resolve(__dirname, "../backend/static")`. Das bedeutet `npm run build` schreibt direkt in `backend/static/`, nicht in `frontend/dist/`. Der Eintrag `frontend/dist/` in `.gitignore` ist daher überflüssig; stattdessen ist `static/` (im Backend-Verzeichnis) die relevante Ignore-Regel.

### 16. Apache-Reverse-Proxy + WebSocket: `mod_proxy_wstunnel` fehlt

Bricht die Live-Transkription hinter Apache nach 1-2 Sätzen ab, fehlt vermutlich `mod_proxy_wstunnel` — `mod_proxy_http` lässt das WS-Upgrade zwar durch, bricht aber bei binären Audio-Frames ab. Fix: `a2enmod proxy_wstunnel` und die WS-`ProxyPass`-Regel für `/api/v1/records/ws/record` **vor** dem Catch-all `ProxyPass /` deklarieren.

### 17. `docker stack config`/`deploy`-Interpolationsbug bei Bindestrichen

Ein wörtliches ` - ` (Leerzeichen-Bindestrich-Leerzeichen) innerhalb einer `${VAR:?Fehlermeldung}`-Klausel lässt den Compose-Spec-Interpolator die Substitution stillschweigend verstümmeln (liefert Datenmüll statt des Variablenwerts, selbst wenn die Variable gesetzt ist) — reproduziert, kein Theoriegebilde. In `:?`/`:-`-Default-/Fehlertexten in Swarm-Compose-Dateien Bindestriche vermeiden.

---

## Ressourcen

### Repositories

- **Quellcode:** [GitHub - s2a-open-technologies/openDox](https://github.com/s2a-open-technologies/openDox)
- **Docker Images:** App, Whisper, Parakeet, Garage-Init; multi-arch (amd64+arm64) über den manuellen Workflow `.github/workflows/docker-publish.yml` nach `ghcr.io/<owner>`
- **Weitere Dokumentation:** `docs/zweckbestimmung.md` (Zweckbestimmung, Abgrenzung zur MDR), `docs/client.md` (Desktop-Client), `docs/pii.md` (PII-Sanitizer-Ablauf), `docs/data-mapping.md` (Datenfluss/DSGVO), `SECURITY.md`, `AGENTS.md`/`CLAUDE.md` (technische Agenten-Referenz)

### Technologie-Dokumentation

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [React](https://react.dev/)
- [shadcn/ui](https://ui.shadcn.com/)
- [Whisper](https://github.com/openai/whisper)
- [LangChain](https://python.langchain.com/) (LLM-Orchestrierung, OpenAI-kompatible Backends)

---

## Danksagung

Entwickelt von **Christopher Abanilla** für den Einsatz in medizinischen Praxen und Kliniken.

Besonderer Dank an die Open-Source-Community:

- **Sebastián Ramírez** – FastAPI
- **Tiangolo** – SQLModel
- **shadcn** – shadcn/ui
- **OpenAI** – Whisper
- **Ollama/vLLM und das OpenAI-kompatible LLM-Ökosystem** – lokale wie Cloud-LLM-Inferenz

---

## Lizenz

```
openDox - Medical transcription platform
Copyright (C) 2025 S2A Open Technologies gGmbH

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

*Letzte Aktualisierung: August 2026*
*App-Version zum Zeitpunkt dieser Aktualisierung: siehe `pyproject.toml` (`[project].version`, einzige Quelle der Wahrheit) bzw. `GET /api/version`*
*Änderungen in diesem Update: PII-Sanitizer, Kategorien-System, S3-Audio-Download inkl. Retry-Failsafe, OIDC/SSO, System-Health-Check, Key-Rotation ergänzt; Parakeet-Live-Pfad auf VAD-Streaming korrigiert; veraltete "Ollama"-Framing generalisiert; API-Referenz, Docker-Befehle und Bekannte-Probleme-Liste gegen den aktuellen Code korrigiert*
