# openDox API

Vollständige Referenz der HTTP- und WebSocket-Schnittstelle von openDox (Stand: v0.12.0).

Die automatisch erzeugte, maschinenlesbare Fassung liefert FastAPI selbst: `{ROOT_PATH}/docs` (Swagger UI),
`{ROOT_PATH}/redoc` und `{ROOT_PATH}/openapi.json`. Dieses Dokument ergänzt sie um das, was daraus nicht hervorgeht:
Rollen, Fehlercodes, Seiteneffekte, den WebSocket und das Zusammenspiel der Endpunkte.

## Inhalt

1. [Grundlagen](#1-grundlagen)
2. [Ablauf einer Diktat-Sitzung](#2-ablauf-einer-diktat-sitzung)
3. [System](#3-system)
4. [Authentifizierung und Benutzer](#4-authentifizierung-und-benutzer)
5. [Aufnahmen (Records)](#5-aufnahmen-records)
6. [WebSocket `/ws/record`](#6-websocket-wsrecord)
7. [Fehlgeschlagene Transkriptionen](#7-fehlgeschlagene-transkriptionen-admin)
8. [Kategorien](#8-kategorien)
9. [Wörterbücher](#9-wörterbücher)
10. [Persönliche Einstellungen](#10-persönliche-einstellungen)
11. [Globale Einstellungen](#11-globale-einstellungen)
12. [Desktop-Client, Handbücher, Update-Hinweis](#12-desktop-client-handbücher-update-hinweis)
13. [Backup und Restore](#13-backup-und-restore)
14. [Audit-Log](#14-audit-log)

---

## 1. Grundlagen

### Basis-URL

Alle Pfade gelten ohne `ROOT_PATH`. Bei einer Sub-Pfad-Installation (`ROOT_PATH=/opendox`) steht der Prefix davor,
also `/opendox/api/v1/...`. Die Fachrouten liegen unter `/api/v1/`:

| Prefix | Bereich |
|---|---|
| `/api/v1/records` | Aufnahmen, Upload, Status, WebSocket |
| `/api/v1/auth` | Login, Token, Benutzer, OIDC |
| `/api/v1/settings` | Einstellungen, Kategorien, Wörterbücher, Audit |
| `/api/endpoint`, `/api/version`, `/api/ready` | Betrieb, ohne Login |

### Authentifizierung

Geschützte Routen erwarten `Authorization: Bearer <access_token>`. Tokens kommen aus `POST /api/v1/auth/login`
(oder dem OIDC-Redirect) und werden mit `POST /api/v1/auth/refresh` erneuert.

- Access-Token: 30 Minuten (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Refresh-Token: 7 Tage (`REFRESH_TOKEN_EXPIRE_DAYS`), rotiert bei jeder Erneuerung. Das alte ist danach nicht
  mehr nutzbar.
- Der WebSocket nimmt den Access-Token als Query-Parameter `token` (Browser können dort keinen Header setzen).

### Rollen

`admin`, `moderator`, `demo_viewer`, `user`.

| Rolle | Kann |
|---|---|
| `admin` | alles in den Einstellungen und der Benutzerverwaltung; sieht **keine** fremden Aufnahmen |
| `moderator` | globale Kategorien und Wörterbücher verwalten |
| `demo_viewer` | Lesezugriff auf die Einstellungen und Benutzer; Zugangsdaten sind in den Antworten geschwärzt |
| `user` | eigene Aufnahmen, eigene Kategorien/Wörterbücher, eigene Einstellungen |

Aufnahmen gehören ausschließlich ihrem Besitzer. Auch Admins erhalten für fremde Records `403`. Die einzigen
admin-seitigen Eingriffe in Audiodaten sind die Routen aus [Abschnitt 7](#7-fehlgeschlagene-transkriptionen-admin).

In den Tabellen steht in der Spalte **Zugriff**:

| Kürzel | Bedeutung |
|---|---|
| öffentlich | kein Login nötig |
| Login | jeder angemeldete Benutzer |
| Besitzer | angemeldet **und** Eigentümer des Records bzw. `user_id` im Pfad = eigene ID |
| Admin | nur `admin` |
| Admin/Demo | `admin` und `demo_viewer` |
| Mod+ | `moderator`, `admin`, `demo_viewer` (für globale Kategorien und Wörterbücher) |

### Fehlerformat

Fachliche Fehler kommen als

```json
{"detail": {"code": "admin_required", "message": "Admin role required", "params": {}}}
```

`code` ist stabil und wird im Frontend übersetzt (`errors:<code>`). Ältere Routen liefern `detail` noch als
String. Validierungsfehler sind FastAPI-üblich `422` mit einer Liste unter `detail`.

| Status | Bedeutung |
|---|---|
| `401` | kein oder ungültiger/abgelaufener Token |
| `403` | Rolle oder Besitz reicht nicht. Jeder `403` unter `/api/` landet als `access.denied` im Audit-Log |
| `404` | nicht gefunden. Fremde persönliche Kategorien/Wörterbücher antworten ebenfalls `404`, damit ihre Existenz nicht verraten wird |
| `429` | Login-Rate-Limit |

Häufige `code`-Werte: `admin_required`, `moderator_required`, `account_locked`, `rate_limited`,
`personal_categories_disabled`, `builtin_category_locked`, `dictionary_scope_mismatch`, `retention_exceeds_global`,
`password_managed_externally`, `role_managed_externally`, `translation_not_available`,
`translation_target_in_sources`, `task_no_retry_audio`, `archived_audio_gone`, `retained_audio_gone`,
`unsupported_file_type`.

### Paginierung

Listen mit `offset` (Standard 0) und `limit` (Standard je Route, meist 100). Das Audit-Log liefert zusätzlich
`total`.

### Zeitstempel

Datenbankfelder sind UTC mit Zeitzone (ISO 8601). `Record.timestamp` ist dagegen ein deutsch formatierter
Anzeige-String und kein ISO-Wert.

---

## 2. Ablauf einer Diktat-Sitzung

```text
POST /records/create            → Record + session_id
WS   /records/ws/record?...     → PCM-Frames hoch, Live-Text runter
     "stop"                     → {"status":"finished","task_id":…}
GET  /records/status/{task_id}  → pending → running → transcribing → (translating) → processing_llm → done | error
GET  /records/record/{id}       → fertiger Text, Zusammenfassung, ggf. Übersetzung
```

Alternativ ohne Live-Aufnahme: `POST /records/upload` mit einer fertigen Audiodatei, danach derselbe Status-Weg.

Die Task-Stati `pending`, `running`, `transcribing`, `translating`, `processing_llm` gelten als aktiv. Solche Records
werden von der automatischen Löschung übersprungen.

---

## 3. System

| Methode und Pfad | Zugriff | Zweck |
|---|---|---|
| `GET /api/endpoint` | öffentlich | Liveness: `{"status":"ok"}` |
| `GET /api/version` | öffentlich | `{"version":"0.12.0"}`, Quelle `pyproject.toml` |
| `GET /api/ready` | öffentlich | Readiness; `503`, wenn DB oder Redis nicht erreichbar sind |
| `GET /api/v1/settings/services-health/` | öffentlich | Status der Dienste, siehe unten |

Einen Pfad `/api/health` gibt es nicht; er liefert über den SPA-Fallback die Startseite mit `200`.

### `GET /api/v1/settings/services-health/`

```json
{
  "services": [
    {"name": "PostgreSQL", "status": "online"},
    {"name": "LLM", "status": "disabled"}
  ],
  "encryption_key": "match"
}
```

`status` ist `online`, `offline` oder `disabled` (nicht konfiguriert, bewusst aus). `encryption_key` ist `match`
oder `mismatch` (konfigurierter Schlüssel gegen den gespeicherten Fingerabdruck). Der Admin-Tab „System“ ruft das
alle 10 Sekunden ab.

---

## 4. Authentifizierung und Benutzer

Prefix `/api/v1/auth`.

| Methode und Pfad | Zugriff | Zweck |
|---|---|---|
| `POST /login` | öffentlich | Anmeldung (lokal, LDAP) → Token-Paar |
| `POST /refresh` | öffentlich (Refresh-Token) | neues Token-Paar |
| `GET /me` | Login | aktueller Benutzer |
| `POST /accept-disclaimer` | Login | Erstanmelde-Hinweis „Kein Medizinprodukt“ bestätigen |
| `GET /users` | Admin/Demo | Benutzerliste (`offset`, `limit`) |
| `POST /users` | Admin | Benutzer anlegen |
| `GET /users/{user_id}` | Admin/Demo | ein Benutzer |
| `PUT /users/{user_id}` | Admin | Benutzer ändern |
| `DELETE /users/{user_id}` | Admin | Benutzer löschen (nicht sich selbst) |
| `GET /oidc/login` | öffentlich | Redirect zum OIDC-Anbieter |
| `GET /oidc/callback` | öffentlich | Rücksprung vom Anbieter, stellt Tokens aus |
| `GET /oidc/status` | öffentlich | `{"enabled": true\|false}` |

### `POST /login`

Reihenfolge: lokale Datenbank, dann LDAP. Bei Erfolg:

```json
{"access_token": "…", "refresh_token": "…", "token_type": "bearer"}
```

Body `{"name": "...", "password": "..."}`. Leere Passwörter werden abgewiesen. Fehler: `401` falsche Zugangsdaten,
`403 account_locked` (Konto in openDox gesperrt, oder LDAP-Gruppe nicht zugelassen), `429 rate_limited`. Fehlgeschlagene
Logins werden auditiert, erfolgreiche nicht.

### `POST /refresh`

Body `{"refresh_token": "…"}`. Die Query-Variante `?refresh_token=` existiert nur für ältere Desktop-Clients, weil
URLs in Proxy-Logs landen. Gelöschte oder inaktive Benutzer erhalten `401`. LDAP- und OIDC-Benutzer werden dabei
gegen ihr Verzeichnis neu geprüft (Rolle und Gruppen); ist das Verzeichnis nicht erreichbar, bleibt die Sitzung bestehen.

### `GET /me`, Benutzerobjekt

```json
{
  "id": 3, "name": "mmustermann", "role": "user", "is_active": true,
  "disclaimer_accepted_at": "2026-11-26T09:12:00Z",
  "ui_language": "de", "auth_source": "local", "translation_allowed": false
}
```

`auth_source` ist `local`, `ldap` oder `oidc`. Für LDAP/OIDC-Benutzer verweigert `PUT /users/{id}` ein neues
Passwort (`400 password_managed_externally`) und eine Rollenänderung (`400 role_managed_externally`), weil die Rolle bei
jeder Anmeldung aus den Gruppen neu gesetzt wird.

### `POST /users` und `PUT /users/{user_id}`

```json
{"name": "mmustermann", "password": "…", "role": "user", "translation_allowed": false}
```

`PUT` nimmt alle Felder optional, zusätzlich `is_active`. Eine unbekannte Rolle beim Anlegen wird zu `user`.

### OIDC

Authorization-Code-Flow mit Discovery (`{provider_url}/.well-known/openid-configuration`). `/oidc/login` setzt ein
kurzlebiges, signiertes State-Cookie. `/oidc/callback` leitet auf `/login?access_token=…&refresh_token=…` um, das
Frontend übernimmt die Tokens aus der Query. Fehler im Callback sind bewusst Klartext-JSON, weil der Browser sie nach
dem Redirect direkt anzeigt. Die Redirect-URI wird aus `X-Forwarded-Proto/-Host` nur gebildet, wenn die Anfrage von
einem vertrauenswürdigen Proxy kommt (`TRUSTED_PROXY_IPS`).

---

## 5. Aufnahmen (Records)

Prefix `/api/v1/records`. Alle Routen verlangen Login und Besitz.

| Methode und Pfad | Zweck |
|---|---|
| `POST /create` | neue Aufnahme anlegen, liefert `session_id` |
| `POST /upload` | fertige Audiodatei einreichen |
| `GET /active-session/{user_id}` | unfertige Aufnahme des Benutzers |
| `DELETE /cancel-session/{user_id}` | unfertige Aufnahme verwerfen |
| `GET /list-records/{user_id}` | Records des Benutzers (`archived`) |
| `GET /by-session/{session_id}` | Record zu einer Session |
| `GET /record/{record_id}` | ein Record |
| `PUT /record/{record_id}` | Text, Titel, Kategorie, Übersetzung ändern |
| `DELETE /record/{record_id}` | Record und Audio endgültig löschen |
| `POST /record/{record_id}/summarize` | Zusammenfassung neu erzeugen |
| `PUT /record/{record_id}/archive` | archivieren |
| `PUT /record/{record_id}/unarchive` | Archivierung aufheben |
| `GET /record/{record_id}/audio` | gespeichertes Audio herunterladen |
| `GET /status/{task_id}` | Stand der Transkription |

### `POST /create`

```json
{"user_id": 3, "title": "Visite", "category_id": 1, "source_language": null}
```

Antwort ist der Record (siehe unten) mit `session_id` (UUID), die der WebSocket verlangt. `source_language` ist ein
ISO-639-1-Code und nur erlaubt, wenn die Übersetzung freigegeben ist (sonst `403 translation_not_available`).

### `POST /upload` (multipart/form-data)

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `file` | ja | ffmpeg-lesbare Audiodatei; sonst `415 unsupported_file_type` |
| `category_id` | ja | Kategorie |
| `user_id` | ja | Besitzer, muss der angemeldete Benutzer sein |
| `title` | nein | Titel |
| `source_language` | nein | Diktiersprache wie bei `/create` |

Antwort: `{"task_id": 12, "session_id": "…", "record_id": 7}`. Die Verarbeitung läuft im Hintergrund.

### Record-Objekt (`RecordRead`)

```json
{
  "id": 7, "session_id": "…", "user_id": 3, "title": "Visite", "category_id": 1,
  "content": "Originaltranskript", "summarize": "Zusammenfassung",
  "summary_enabled": true, "timestamp": "26.11.2026 09:12",
  "has_audio": true, "archived": false, "task_id": 12,
  "source_language": null, "translation_language": null,
  "translation": "", "translation_segments": []
}
```

Zwei Lesezeit-Regeln, auf die sich der Desktop-Client verlässt:

- Ist für den Record kein LLM aktiv (globaler Schalter oder Kategorie aus), liefert die API das **Transkript** als
  `summarize` und `summary_enabled: false`. Eine gespeicherte Zusammenfassung hat Vorrang.
- Bei Übersetzungen ist `content` das Original, `summarize` ohne Zusammenfassung die Übersetzung.

### `PUT /record/{record_id}`

Alle Felder optional:

```json
{"title": "…", "content": "…", "summarize": "…", "category_id": 2,
 "translation_segments": [{"index": 4, "target": "korrigierter Satz"}]}
```

`category_id` muss existieren (sonst `404`). Ein `summarize`, das dem alten oder neuen Transkript entspricht, wird
ignoriert, solange keine Zusammenfassung gespeichert ist (kein Kopieren von `content` nach `summarize`).
`translation_segments` korrigiert einzelne Sätze der Übersetzung; Zahlen werden neu geprüft und `translation` neu
zusammengesetzt.

### `POST /record/{record_id}/summarize`

Erzeugt die Zusammenfassung aus dem aktuellen Text neu (inklusive PII-Maskierung, falls aktiv).

```json
{"summarize": "…", "summary_enabled": true, "task_status": "done", "has_audio": true}
```

Ohne aktives LLM wird keine Anfrage gestellt: eine gespeicherte Zusammenfassung wird gelöscht und das Transkript
zurückgegeben. Eine erfolgreiche Zusammenfassung löst einen fehlgeschlagenen Task auf (`error` → `finished`).

### `GET /active-session/{user_id}`

```json
{"active": false}
```
oder
```json
{"active": true, "session_id": "…", "record_id": 7, "title": "Visite", "category_id": 1, "status": "recording"}
```

Damit setzt ein Client eine unterbrochene Aufnahme fort (Redis hält die Session 30 Minuten über Neustarts).

### `DELETE /cancel-session/{user_id}`

Verwirft Session, Record und PCM-Dateien. Antwort `{"status": "cancelled", "session_id": "…"}` oder
`{"status": "no_active_session"}`.

### `GET /list-records/{user_id}?archived=false`

Liste von Record-Objekten. `archived=true` liefert das Archiv.

### `GET /status/{task_id}`

```json
{"task_id": 12, "status": "done", "result": "…", "error": null}
```

`status`: `pending`, `running`, `transcribing`, `translating`, `processing_llm`, `done`/`finished`, `error`. Ein
unbekannter Task liefert `{"error": "Task not found"}` mit `200`.

### `GET /record/{record_id}/audio`

Liefert das entschlüsselte Audio direkt als Antwort (`Content-Type` und Dateiendung aus dem gespeicherten Format).
Das Audio wird nie auf die Platte des Servers geschrieben. Ohne gespeichertes Audio `404`. Voraussetzung: Audio-Download
ist aktiv und ein S3-kompatibler Speicher konfiguriert.

### `DELETE /record/{record_id}`

Löscht den Record und das Audio-Objekt (nach dem DB-Commit). Antwort `{"status": "success", "message": "Record deleted"}`.

### `PUT /record/{record_id}/archive` und `/unarchive`

Setzen bzw. entfernen das Archiv-Flag. Antwort ist der Record. Zusätzlich archiviert ein Hintergrundjob automatisch
nach `auto_archive_days`.

---

## 6. WebSocket `/ws/record`

`WS /api/v1/records/ws/record?session_id=<uuid>&user_id=<int>&token=<access_token>[&live=0]`

Aufnahme in Echtzeit. Eine Sitzung hängt für ihre gesamte Dauer an einer App-Instanz; bei mehreren App-Instanzen muss der Proxy denselben
`session_id` an dieselbe Instanz leiten (`hash $arg_session_id;`, siehe `docs/scaling.md`).

### Verbindungsaufbau

Alle drei Parameter sind Pflicht, `token` ist ein Access-Token und muss zu `user_id` gehören, der Benutzer muss aktiv
sein. Bei einem Fehler sendet der Server `{"error": "…"}` und schließt mit Code `1008`:

| Meldung | Ursache |
|---|---|
| `session_id, user_id and token required` | Parameter fehlt |
| `user_id must be an integer` | `user_id` nicht numerisch |
| `Invalid or expired token` | Token ungültig, abgelaufen oder kein Access-Token |
| `Not authorized for this session` | Benutzer unbekannt/inaktiv oder `user_id` ≠ Token |

`live=0` nimmt nur Audio auf und überspringt jede Live-Erkennung (Desktop-Client ohne Live-Ansicht). Die
Endtranskription ist davon unberührt.

### Client → Server

| Frame | Inhalt |
|---|---|
| Binär | rohe PCM-Frames, **float32**, mono (der Server schreibt sie als 16-kHz-WAV) |
| Text, enthält `stop` | beendet die Aufnahme und startet die Verarbeitung |

Andere Textnachrichten werden ignoriert. Leere Binärframes ebenfalls.

### Server → Client (JSON)

| Nachricht | Bedeutung |
|---|---|
| `{"session_id", "text": "<delta>"}` | neuer, festgeschriebener Textabschnitt, im Client anhängen |
| `{"session_id", "partial": "<text>"}` | laufender, noch veränderlicher Satz am Ende |
| `{"session_id", "text": "<alles bisher>", "restored": true}` | nach Wiederaufnahme: bisheriger Live-Text |
| `{"status": "finished", "task_id": 12, "session_id": "…"}` | Aufnahme übernommen, Verarbeitung läuft; danach `GET /status/{task_id}` |
| `{"status": "error", "message": "No audio data received"}` | es kam kein Audio an |
| `{"error": "…", "code": "recording_audio_unavailable"}` | Wiederaufnahme nicht möglich (siehe unten), Schließcode `1011` |

Fehlt die Parakeet-Verbindung, läuft die Aufnahme ohne Live-Text weiter; die Endtranskription bleibt unberührt.
Bei Sprachen, die das Live-Modell nicht kennt, bleibt der Live-Text server-seitig aus (`live_languages` in
`GET /settings/translation/me`).

### Wiederaufnahme

Verbindet sich ein Client mit einer bekannten `session_id` erneut, hängt der Server an die vorhandene PCM-Datei an.
Fehlt das frühere Audio auf dieser Instanz oder ist es kürzer als gespeichert, antwortet er mit
`recording_audio_unavailable` und rührt nichts an, statt in eine neue leere Datei zu schreiben.

---

## 7. Fehlgeschlagene Transkriptionen (Admin)

Prefix `/api/v1/records`, Zugriff **Admin**. Die Routen zeigen weder Transkriptinhalt noch Besitzdaten.

| Methode und Pfad | Zweck |
|---|---|
| `GET /tasks/failed` | Tasks mit Status `error` und aufbewahrtem Audio (`offset`, `limit`) |
| `POST /tasks/{task_id}/retry` | Pipeline erneut auf dem aufbewahrten Audio starten |
| `DELETE /tasks/{task_id}/retained-audio` | aufbewahrtes Audio verwerfen, statt es zu wiederholen |

`GET` liefert pro Eintrag `task_id`, `record_id`, `title`, `error`, `updated_at` und `archived` (Audio liegt schon im
Objektspeicher). `POST …/retry` holt archiviertes Audio zurück, setzt den Task auf `pending` und antwortet sofort
`{"task_id": 12, "status": "pending"}`. Fehler: `409 task_no_retry_audio`, `410 archived_audio_gone`,
`410 retained_audio_gone`, `404 record_for_task_missing`. `DELETE` antwortet `{"task_id": 12, "discarded": true}`; der
Task bleibt `error`, der Record bleibt beim Besitzer. Beide Aktionen werden auditiert (`task.retry`, `task.discard`).

---

## 8. Kategorien

Prefix `/api/v1/settings/categories`. Eine Kategorie steuert Whisper-Prompt, Wörterbücher, LLM-System-Prompt, optional
ein eigenes LLM und ob überhaupt eine Zusammenfassung entsteht.

| Methode und Pfad | Zugriff | Zweck |
|---|---|---|
| `GET /` | Login | globale plus eigene Kategorien (`offset`, `limit`) |
| `GET /{category_id}` | Login | eine Kategorie, fremde persönliche → `404` |
| `POST /` | Login | anlegen (global nur Mod+, persönlich nur wenn erlaubt) |
| `PUT /{category_id}` | Login | ändern (Besitzer bzw. Mod+) |
| `DELETE /{category_id}` | Login | löschen (Besitzer bzw. Mod+); „Standard“ nie |
| `PUT /{category_id}/default` | Mod+ | globale Kategorie als Vorauswahl für alle setzen |

Sortierung der Liste: `is_default` zuerst, dann `is_builtin`, dann `id`. Der Desktop-Client verlässt sich darauf.

### Body (`CategoriesCreate`)

```json
{
  "name": "Kardiologie", "description": "…", "system_prompt": "…",
  "whisper_prompt": null, "dictionary_ids": [1, 4],
  "llm_enabled": true, "llm_override_enabled": false,
  "llm_model": null, "llm_api_endpoint": null, "llm_api_key": null,
  "llm_temperature": null, "llm_max_tokens": null, "llm_top_p": null,
  "llm_frequency_penalty": null, "llm_enable_thinking": null,
  "scope": "personal"
}
```

- `scope: "personal"` legt eine persönliche Kategorie an. Ohne Angabe legen `moderator`, `admin` und `demo_viewer`
  globale an, `user` persönliche.
- Persönliche Kategorien verlangt der Betreiber ausdrücklich ab: `403 personal_categories_disabled`, solange
  `category-policy` es nicht erlaubt. Dann fehlen sie auch in `GET /`, und bestehende laufen als „unkategorisiert“.
- Die integrierte Kategorie „Standard“ ist schreibgeschützt für `name`, `description`, `system_prompt` und nicht
  löschbar (`403 builtin_category_locked`). `is_builtin` und `is_default` werden aus Bodies nicht angenommen.
- `dictionary_ids`: eine globale Kategorie nimmt nur globale Wörterbücher (`400 dictionary_scope_mismatch`).
- `llm_api_key` fehlt in Listen und Einzelabfragen (`CategoriesListRead`).

Antwort ist `CategoriesRead` bzw. in Listen `CategoriesListRead` (ohne Key), mit `id`, `user_id` (`null` = global),
`is_builtin`, `is_default`.

---

## 9. Wörterbücher

Prefix `/api/v1/settings/dictionaries`. Begriffslisten für die phonetische Fachwort-Korrektur der Endtranskription.
Globale Wörterbücher wirken nur über angehängte Kategorien, persönliche immer für alle Aufnahmen ihres Besitzers.
Persönliche sind für niemand sonst sichtbar, Admins eingeschlossen.

| Methode und Pfad | Zugriff | Zweck |
|---|---|---|
| `GET /` | Login | globale plus eigene, ohne Begriffe |
| `GET /{dictionary_id}` | Login | eines mit Begriffen |
| `POST /` | Login | anlegen; global nur Mod+ |
| `PUT /{dictionary_id}` | Login | umbenennen und/oder Begriffe ersetzen (Besitzer bzw. Mod+) |
| `DELETE /{dictionary_id}` | Login | löschen; wird von allen Kategorien gelöst |
| `POST /{dictionary_id}/upload` | Login | Begriffe aus Datei übernehmen |

`POST /`: `{"name": "Kardiologie", "scope": "global", "terms": ["Metoprolol", "Ramipril"]}`. Antwort mit `id`,
`term_count`, `updated_at`, `category_ids`, in der Einzelabfrage zusätzlich `terms`.

### `POST /{dictionary_id}/upload` (multipart/form-data)

| Feld | Bedeutung |
|---|---|
| `file` | `.txt` oder `.csv`, UTF-8, höchstens 5 MB |
| `mode` | `replace` (Standard) oder `append` |

Eine Zeile je Begriff, `#` leitet einen Kommentar ein, Kommas im Begriff bleiben erhalten. Bei CSV zählt die erste
Spalte (`;` oder `,` wird erkannt). Grenzen: 50 000 Begriffe, je höchstens 200 Zeichen.

---

## 10. Persönliche Einstellungen

Prefix `/api/v1/settings`, Zugriff **Login**, wirkt immer auf den aufrufenden Benutzer.

| Methode und Pfad | Zweck |
|---|---|
| `GET /my-language/` | UI-Sprache → `{"ui_language": "de"}` |
| `PUT /my-language/` | UI-Sprache setzen: `{"ui_language": "en"}`. Erlaubt: `de`, `en`, `es` |
| `GET /my-retention/` | eigene Aufbewahrung → `{"personal_days": 90, "global_enabled": true, "global_days": 365}` |
| `PUT /my-retention/` | `{"personal_days": 90}`, `null` hebt auf |
| `GET /session-config/` | Sitzungs-Richtlinie → `{"idle_timeout_minutes": 15}` (`0` = aus) |
| `GET /category-policy/` | `{"personal_categories_allowed": false}` |
| `GET /translation/me` | Übersetzung für den Aufrufer, siehe unten |

`PUT /my-retention/` darf eine aktive globale Grenze nicht überschreiten (`400 retention_exceeds_global`). Es gilt
je Benutzer der kürzere Wert aus global und persönlich.

`GET /translation/me`:

```json
{"available": true, "languages": ["tr", "ar"], "target_language": "de", "live_languages": ["tr"]}
```

`target_language` ist immer die Instanzsprache (Whisper-Einstellung `language`), nie eine Diktiersprache.

---

## 11. Globale Einstellungen

Prefix `/api/v1/settings`. Jede Speicherung (`PUT`) wird als `settings.<schlüssel>.update` auditiert, mit den Namen
der geänderten Felder, nie mit Werten. Danach wird der Settings-Cache geleert und die ASR-Backends werden neu
aufgebaut; weitere App-Instanzen übernehmen die Änderung nach `SETTINGS_CACHE_TTL_S` (Standard 30 s).

| Pfad | `GET` | `PUT` | Inhalt |
|---|---|---|---|
| `/whisper-settings/` | öffentlich¹ | Admin | ASR: Live-Backend (Parakeet), Final-Backend (Whisper), Sprache, VAD, Fachwort-Korrektur |
| `/llm-settings/` | Admin/Demo² | Admin | LLM, PII-Sanitizer, Schalter für persönliche Kategorien |
| `/ldap-settings/` | Admin/Demo² | Admin | LDAP-Anbindung und Gruppen |
| `/oidc-settings/` | Admin/Demo² | Admin | OIDC-Anbindung und Gruppen |
| `/audio-settings/` | öffentlich | Admin | Audio-Download, Auto-Archivierung, Auto-Löschung |
| `/session-config/` | Login | Admin | Leerlauf-Abmeldung |
| `/category-policy/` | Login | Admin | persönliche Kategorien erlauben |
| `/translation/` | Admin/Demo² | Admin | Übersetzung: `enabled`, `access` (`all`/`selected`), `languages` |
| `/languages/` | öffentlich | Admin | Sprachliste (siehe unten) |

¹ Ohne Login fehlen die API-Keys; mit Admin-Token sind sie enthalten.
² Für `demo_viewer` sind Schlüssel, Passwörter und Zertifikate geschwärzt.

Die vollständigen Felder jedes Modells stehen im OpenAPI-Schema (`WhisperSettingsModel`, `LlmSettingsModel`,
`LdapSettingsModel`, `OidcSettingsModel`, `AudioSettingsModel`, `TranslationConfig`). Alle `PUT` nehmen das
komplette Objekt entgegen.

`PUT /translation/` ignoriert `target_language` (nur lesbar). `PUT /audio-settings/` akzeptiert die Formate `mp3`,
`wav`, `flac`, `ogg`.

### Verbindungstests (Admin)

| Pfad | Zweck |
|---|---|
| `GET /asr-test/?backend=live\|final` | Erreichbarkeit des ASR-Servers; `/models` erreichbar **und** das konfigurierte Modell gelistet |
| `GET /llm-test/` | echte kurze Chat-Anfrage an das konfigurierte LLM |
| `POST /ldap-settings/test` | LDAP-Verbindung mit den im Body übergebenen Werten |
| `POST /ldap-settings/upload-cert/` | CA-Zertifikat hochladen (multipart, Feld `file`), wird in der DB gespeichert |

Test-Antworten haben die Form `{"ok": true}` oder `{"ok": false, "code": "…", "error": "…"}`. Die Whisper-Maske
speichert vor dem Test, weil `/asr-test/` die gespeicherten Werte prüft.

### Sprachen (`/languages/`)

`GET /` und `GET /{language_id}` sind öffentlich, `POST`, `PUT /{id}`, `DELETE /{id}` nur Admin.
Body `{"name": "Deutsch", "country_code": "de", "system_prompt": "…"}`. Diese Liste ist unabhängig von der UI-Sprache
und der Diktiersprache.

---

## 12. Desktop-Client, Handbücher, Update-Hinweis

| Methode und Pfad | Zugriff | Zweck |
|---|---|---|
| `GET /api/v1/settings/client-config/` | öffentlich | Client-Richtlinie plus neueste Client-Version |
| `PUT /api/v1/settings/client-config/` | Admin | Richtlinie speichern |
| `GET /api/v1/settings/client-distribution/` | Admin/Demo | Server-URL, Download-Basis und Dateinamen für die Verteilung |
| `GET /api/v1/settings/manuals/` | Login | Handbuch-Links der laufenden Version |
| `GET /api/v1/settings/update-check/` | Admin/Demo | neueres openDox-Release vorhanden? |

### `client-config`

Bewusst ohne Login, weil der Client sie vor der Anmeldung liest. Enthält keine personenbezogenen Daten.

```json
{
  "clipboard_exclude_from_history": true, "clipboard_clear_after_seconds": 30,
  "insert_allowlist": ["notepad.exe"], "dictation_mic_mode": "hold",
  "live_view": true, "latest_client_version": "0.9.0"
}
```

`latest_client_version` kommt aus der GitHub-API (Cache 6 h, nach Fehler 15 min), `CLIENT_LATEST_RELEASE_URL=""`
schaltet das ab (dann `null`). `dictation_mic_mode` ist `hold` (Standard) oder `toggle`. `PUT` nimmt dieselben Felder ohne `latest_client_version`. Siehe `docs/client.md`.

### `GET /manuals/`

```json
{"version": "0.12.0", "release_url": "…/releases/tag/v0.12.0",
 "manuals": [{"key": "benutzer", "file": "openDox-Benutzerhandbuch-0.12.0.pdf", "url": "…"}]}
```

Admin und `demo_viewer` erhalten alle drei Handbücher (`benutzer`, `administration`, `installation`) und
`release_url`. Alle anderen nur das Benutzerhandbuch, `release_url` ist dann leer. `MANUALS_DOWNLOAD_BASE_URL`
(mit Platzhalter `{version}`) leitet die Links auf einen Mirror um.

### `GET /update-check/`

Grundlage des Update-Banners im Dashboard.

| Feld | Typ | Bedeutung |
|---|---|---|
| `current` | string | laufende Version (wie `GET /api/version`) |
| `latest` | string \| null | neueste veröffentlichte Version ohne `v`; `null`, wenn unbekannt |
| `update_available` | bool | `true`, wenn `latest` numerisch größer als `current` ist |
| `release_url` | string | Link zum Release (`…/releases/tag/vX.Y.Z`), sonst zur Release-Übersicht |

```json
{
  "current": "0.12.0", "latest": "0.13.0", "update_available": true,
  "release_url": "https://github.com/s2a-open-technologies/openDox/releases/tag/v0.13.0"
}
```

- Der Server fragt `https://api.github.com/repos/s2a-open-technologies/openDox/releases/latest` ab, nicht der Browser.
  Die Anfrage enthält keine Nutzer- oder Instanzdaten.
- Cache pro App-Prozess: 6 Stunden nach Erfolg, 15 Minuten nach einem Fehler.
- Fail-open: ist GitHub nicht erreichbar oder die Abfrage abgeschaltet, kommt `200` mit `latest: null` und
  `update_available: false`, nie ein Fehler.
- Versionen werden numerisch verglichen (`0.12` = `0.12.0`, `0.9.0` < `0.12.0`). Nicht auswertbare Versionen,
  etwa `unknown`, ergeben `update_available: false`. Pre-Releases erscheinen nicht, weil GitHubs `releases/latest`
  sie auslässt.
- `OPENDOX_LATEST_RELEASE_URL=""` schaltet die Abfrage ab (Netze ohne Internet). Die Variable kann auf eine andere
  Quelle im GitHub-API-Format (`tag_name`) zeigen. Für ausgehende Verbindungen gelten `SSL_CERT_FILE` und
  `REQUESTS_CA_BUNDLE` wie bei den übrigen Diensten.

```bash
curl -s -H "Authorization: Bearer $TOKEN" https://opendox.example/api/v1/settings/update-check/
```

---

## 13. Backup und Restore

Zugriff **Admin**.

| Methode und Pfad | Zweck |
|---|---|
| `GET /api/v1/settings/backup/` | alle globalen Einstellungen als JSON-Download (`Content-Disposition: attachment`) |
| `POST /api/v1/settings/backup/restore/` | Einstellungen aus einer hochgeladenen JSON-Datei wiederherstellen (multipart, Feld `file`) |

Enthalten sind die Einstellungstabellen (Whisper, LLM, LDAP, OIDC, Audio, Sitzung, Client), Kategorien, Sprachen und
**globale** Wörterbücher. **Nicht** enthalten: Benutzer, persönliche Kategorien und Wörterbücher, und sämtliche
Zugangsdaten (API-Keys, LDAP-Bind-Passwort und CA-Zertifikat, OIDC-Client-Secret, Kategorie-`llm_api_key`). Beim
Restore bleiben die auf dem Server gespeicherten Zugangsdaten erhalten. Singletons werden per Upsert gesetzt, Listen
(Kategorien, Sprachen, globale Wörterbücher) komplett ersetzt. Die integrierte Kategorie „Standard“ bleibt bestehen;
nur ihre editierbaren Felder werden übernommen. Beide Aktionen werden auditiert (`backup.export`, `backup.restore`).

---

## 14. Audit-Log

Zugriff **Admin**, nicht `demo_viewer` (dessen `GET` würden `403` liefern und das Log selbst füllen).

| Methode und Pfad | Zweck |
|---|---|
| `GET /api/v1/settings/audit/` | eine Seite Einträge, neueste zuerst |
| `GET /api/v1/settings/audit/export/` | gefilterte Einträge als CSV |

Filter (beide Routen): `since`, `until` (ISO 8601), `actor` (Benutzername), `action` (Präfix, z. B. `settings.`),
`outcome`. `GET /` nimmt zusätzlich `offset` und `limit`.

```json
{
  "items": [{
    "id": 41, "timestamp": "2026-11-26T09:12:00Z",
    "actor_user_id": 1, "actor_name": "admin", "actor_role": "admin",
    "action": "settings.llm.update", "outcome": "success",
    "target_type": null, "target_id": null, "ip": "10.0.0.5",
    "details": {"fields": ["llm_model"]}
  }],
  "total": 1
}
```

Der CSV-Export ist `;`-getrennt, mit BOM, und stellt Zellen, die mit einer Formel beginnen, ein `'` voran. Das Lesen
des Logs ist nicht auditiert, der Export schon (`audit.export`).

**Protokolliert:** Benutzerverwaltung, jede Einstellungsänderung (nur Feldnamen), globale Kategorien und Wörterbücher,
Sprachen, Backup, `task.retry`/`task.discard`, fehlgeschlagene Anmeldungen, Rollenabgleich durch LDAP/OIDC, jede
abgewiesene Anfrage (`access.denied`).
**Nie protokolliert:** was Benutzer mit eigenen Aufnahmen tun, erfolgreiche Anmeldungen, Token-Erneuerungen,
Hintergrundjobs. `details` enthält nur IDs, Feldnamen und Grundcodes, nie Titel, Transkripte, Passwörter oder Schlüssel.

Aufbewahrung: `AUDIT_RETENTION_DAYS` (Standard 365, `0` = unbegrenzt). Das Log ist aus der App heraus nur
anfügbar, es gibt keine Änderungs- oder Löschroute.

---

## Verwandte Dokumente

- `docs/scaling.md`: mehrere App-Instanzen und WebSocket-Routing
- `docs/client.md`: Desktop-Client
- `docs/pii.md`: PII-Sanitizer
- `docs/data-mapping.md`: Datenflüsse nach Art. 30 DSGVO
