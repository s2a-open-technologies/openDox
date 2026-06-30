# Bugfix: WebSocket-Verbindungsabbruch unter Apache2 Reverse Proxy

## Symptom

- Aufnahme startet, Parakeet live transkribiert 1-2 Saetze, dann bricht die WebSocket-Verbindung ab.
- Stop-Button funktioniert nicht mehr ("Verarbeite Aufnahme" endlos-Spinner).
- Backend transkribiert weiter und schreibt in die DB, aber Frontend bekommt nichts mehr.
- Apache Error Log zeigt: `[proxy_http:error] AH01102: error reading status line from remote server` und `[proxy:error] AH00898: Error reading from remote server`.

## Root Cause

`mod_proxy_wstunnel` ist nicht geladen. Apache verwendet `mod_proxy_http` fuer die WebSocket-Verbindung, obwohl der `ProxyPass` das `ws://`-Schema verwendet. `mod_proxy_http` kann das anfaengliche WebSocket-Upgrade durchlassen, bricht aber ein, sobald der Backend binare WebSocket-Frames (Audio-PCM) schickt. Das erklaert "1-2 Saetze, dann Abbruch".

Der Error Log bestatigt dies: alle Fehler kommen von `[proxy_http:error]`, nicht von `[proxy_wstunnel]`.

## Fix

### 1. Apache-Modul aktivieren (Server-seitig)

```bash
a2enmod proxy_wstunnel
systemctl restart apache2
```

Verifikation:

```bash
apache2ctl -M | grep wstunnel
# Sollte ausgeben: proxy_wstunnel_module (shared)
```

### 2. Apache VHost-Config (bereits korrekt)

Die aktuelle Config ist scharf gestellt:

```apache
ProxyPreserveHost On
ProxyTimeout 600

# WebSocket-Endpoint EXPLIZIT — muss VOR ProxyPass / stehen!
ProxyPass        /api/v1/records/ws/record ws://127.0.0.1:20000/api/v1/records/ws/record timeout=600
ProxyPassReverse /api/v1/records/ws/record ws://127.0.0.1:20000/api/v1/records/ws/record

# Alles andere ueber HTTP
ProxyPass / http://127.0.0.1:20000/
ProxyPassReverse / http://127.0.0.1:20000/
```

Die RewriteRules (`RewriteCond %{HTTP:Upgrade}...`) wurden entfernt — sie waren redundant und konfligierten mit ProxyPass.

### 3. Frontend-Resilienz (Recorder.tsx)

Unabhaengig vom Proxy-Fix sollte das Frontend Verbindungsabbrueche bemerken:

- **`ws.onclose`** (`Recorder.tsx:152-154`): Derzeit leer. Soll `isRecording`/`isProcessing` zuruecksetzen und Toast anzeigen.
- **`stopRecording()`** (`Recorder.tsx:258`): Vor `send()` pruefen ob `readyState === WebSocket.OPEN`.
- **`isProcessing`-Timeout**: Nach 90s ohne `{"status":"finished"}` Spinner abbrechen.

### 4. Backend-Loop (optional)

`record.py:368` — `await asyncio.to_thread(backend.transcribe, ...)` blockiert den WebSocket-Receive-Loop waehrend Parakeet transkribiert. Langfristig: Transkription als `asyncio.create_task()` im Hintergrund starten.