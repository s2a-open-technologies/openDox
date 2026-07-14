# Skalierung der Modell-Verarbeitung (Whisper / Parakeet / LLM)

Diese Notiz hält fest, was für "mehrere Aufnahmen gleichzeitig verarbeiten"
nötig ist — als Ergänzung zu `docs/TODO.md` (dort geht's um
Kubernetes/Multi-Replica der App selbst; hier um den Durchsatz der
ASR-/LLM-Backends dahinter, ein unabhängiges Thema).

## Ausgangslage

Auf einer einzelnen GPU/einem einzelnen Modell-Server fällt die
Serialisierung kaum auf. Bei mehreren gleichzeitigen Nutzern serialisiert
sich die Verarbeitung an drei unabhängigen Stellen:

1. **Whisper (finale Transkription)** — ein Server, ein Modell, eine
   Anfrage nach der anderen.
2. **Parakeet (Live-Transkription)** — dieselbe Situation, betrifft aber
   *alle* gerade aufnehmenden Nutzer gleichzeitig (jeder Audio-Chunk läuft
   durch denselben Server).
3. **LLM (Zusammenfassung)** — eine Ollama-Instanz mit einem (oft großen,
   lokalen) Modell verarbeitet ebenfalls nur eine Anfrage nach der anderen.

## Stufe 1 — Blockierende Event-Loops behoben ✅ erledigt

`whisper_server/app.py` (`whisper_model.transcribe(...)`) und
`parakeet_server/main.py` (`m.recognize(...)`) riefen die eigentliche
Modell-Inferenz **synchron direkt im `async def`-Handler** auf — das
blockierte den kompletten Event-Loop des jeweiligen Servers für die Dauer
jeder einzelnen Transkription, sodass währenddessen nicht mal ein
Health-Check durchkam.

Fix: beide Server führen die blockierende Arbeit jetzt über
`asyncio.to_thread(...)` aus (`_run_transcription()` in
`whisper_server/app.py`, `_run_recognition()` in `parakeet_server/main.py`).
Wichtige Detail bei Whisper: `WhisperModel.transcribe()` gibt sofort einen
*lazy generator* zurück — die eigentliche Arbeit passiert erst beim
Iterieren der `segments`. Beide Schritte (Aufruf **und** Iteration) mussten
deshalb zusammen in denselben `to_thread`-Call.

Effekt: **Parakeet (CPU)** profitiert direkt — ONNX Runtime gibt den GIL
während der Inferenz frei, mehrere Chunks können jetzt tatsächlich auf
verschiedenen CPU-Kernen parallel laufen. **Whisper (GPU)** profitiert
kleiner — eine einzelne GPU serialisiert Inferenz meist ohnehin auf
Treiberebene, aber Health-Checks und Anfrage-Annahme frieren während einer
laufenden Transkription nicht mehr komplett ein.

## Stufe 2 — Mehr CPU-Worker für Parakeet (optional, bei Bedarf)

`uvicorn --workers N` für `parakeet_server` — mehrere Prozesse, je ein
eigenes Modell im RAM (Parakeet ist klein genug dafür, kein GPU nötig).
Aktuell nicht dringend, da Parakeet auf CPU bereits gut performt — erst
relevant, wenn Live-Transkriptionslatenz bei vielen gleichzeitigen
Aufnahmen spürbar ansteigt.

## Stufe 3 — vLLM als Serving-Backend

vLLM ist ein OpenAI-kompatibler Server mit Continuous Batching — eine
einzelne GPU verarbeitet mehrere gleichzeitige Anfragen effizient
gebündelt, statt sie strikt nacheinander abzuarbeiten. Skaliert Durchsatz
auf **derselben** Hardware, ohne dass mehr GPUs nötig wären.

Da sowohl `backend/components/services/asr_backends/openai_compatible.py`
als auch `OllamaModel`/`ChatOpenAI` (`backend/components/llm/llm_model.py`)
bereits rein auf generische OpenAI-kompatible HTTP-Endpoints ausgelegt
sind, wäre die Umstellung auf App-Seite größtenteils eine
**Config-Änderung** (`WHISPER_API_ENDPOINT` / `llm_api_endpoint` in der
Admin-UI bzw. den Whisper-/LLM-Settings umbiegen), kein Code-Rewrite. Zwei
konkrete Kompatibilitätslücken (Stand: recherchiert Juli 2026, vor der
eigentlichen Umsetzung nochmal gegen die dann aktuelle vLLM-Version
verifizieren) müssen aber vorher geklärt werden:

### Lücke 1 — Whisper-Anti-Halluzinations-Parameter

`whisper_server/app.py` reicht aktuell diese Parameter durch:
`vad_filter`, `vad_min_silence_ms`, `condition_on_previous_text`,
`no_speech_threshold`, `compression_ratio_threshold`,
`log_prob_threshold`, `hallucination_silence_threshold`, `beam_size`.

vLLMs `/v1/audio/transcriptions`-Endpoint unterstützt **keinen** davon.
Stattdessen: `use_beam_search`, `n` (Beam-Anzahl), `length_penalty`,
`top_p`, `top_k`, `min_p`, `seed`, `frequency_penalty`,
`repetition_penalty`, `presence_penalty`, `max_completion_tokens`,
`hotwords`.

Konsequenz: ein direkter Wechsel von `WHISPER_API_ENDPOINT` auf einen
vLLM-Server würde die aktuelle Anti-Halluzinations-Konfiguration
(`WhisperSettingsModel`, Admin-UI → Whisper-Settings) stillschweigend
wirkungslos machen — die Felder würden einfach ignoriert oder von vLLM
abgelehnt, je nachdem wie strikt der Server unbekannte Formularfelder
behandelt (nicht verifiziert, vor dem Wechsel testen). Vor einer echten
Migration müsste entweder (a) geprüft werden, ob vLLMs eigene
Sampling-Parameter ähnliche Ergebnisse liefern, oder (b) die
Admin-UI/`WhisperSettingsModel` um die vLLM-Parameter erweitert werden,
mit einem klaren Cutover statt stillem Feature-Verlust.

Quellen: [vLLM Speech-to-Text-Doku](https://docs.vllm.ai/en/latest/serving/online_serving/speech_to_text/),
[vLLM Transcription-Protokoll-Doku](https://docs.vllm.ai/en/latest/contributing/model/transcription/)

### Lücke 2 — Ollama-spezifisches `think`-Flag beim LLM

`OllamaModel.reload()` (`backend/components/llm/llm_model.py`) setzt
`model_kwargs={"think": False}` — ein Ollama-spezifisches Feld auf
`/v1/chat/completions`, das Reasoning-Modelle das interne "Denken"
abschalten lässt. vLLM kennt dieses Feld nicht; dort heißt das Äquivalent
`thinking_token_budget` (bzw. modell-/versionsabhängig andere Mechanismen).

Das ist aber **kein harter Blocker**: `_strip_thinking()` plus der
Prompt-Zusatz "Do not output your reasoning..." (`generate_response()`,
gleiche Datei) sind bereits ein modellunabhängiges Sicherheitsnetz, das
unabhängig vom Backend funktioniert. Ohne das explizite `think: False`
verlässt sich die Unterdrückung nur stärker auf dieses Netz statt auf
einen expliziten API-Schalter — für einen Test-Umstieg unkritisch, für
einen produktiven vLLM-Umstieg trotzdem einmal gegenprüfen, ob das Modell
die Prompt-Anweisung zuverlässig befolgt.

Quellen: [vLLM OpenAI-Compatible-Server-Doku](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/),
[Ollama OpenAI-Compatibility-Doku](https://docs.ollama.com/api/openai-compatibility)

### Was reine Ops-Arbeit ist (außerhalb dieses Repos)

- vLLM-Server mit dem Ziel-Whisper-Modell aufsetzen, GPU-VRAM-Bedarf für
  Continuous Batching dimensionieren (mehr Headroom nötig als bei
  Ein-Request-zu-einer-Zeit).
- Gleiches für ein LLM-Serving mit vLLM anstelle von Ollama.
- Erst nach Lücke 1 (und optional Lücke 2) klären: `WHISPER_API_ENDPOINT`
  / `llm_api_endpoint` umstellen.

## Empfohlene Reihenfolge

1. ~~Stufe 1~~ — erledigt.
2. Stufe 3 zuerst beim **LLM** angehen (weniger Kompatibilitätslücken als
   Whisper), Stufe 3 bei **Whisper** erst nach Klärung von Lücke 1.
3. Stufe 2 (Parakeet-Worker) nur bei Bedarf, unabhängig von den anderen
   beiden Stufen.

Auslöser für Stufe 3 sollte echter Durchsatzbedarf sein (mehrere Nutzer
warten spürbar aufeinander), nicht vorauseilende Infrastruktur.
