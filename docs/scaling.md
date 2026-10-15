# Mehrere App-Instanzen betreiben

Stand: 15.10.2026. Die Punkte unter „Was geändert wurde“ sind im Code umgesetzt
und getestet. Das nginx-Routing wurde mit Platzhalter-Backends getestet, nicht
mit der echten App und nicht in einem echten Swarm.

## Warum überhaupt mehrere Instanzen?

Eine Instanz hält alle WebSocket-Verbindungen der Aufnahmen, schreibt das PCM
(16 kHz, Float32 = 64 KB/s je Sprecher) auf die lokale Platte und führt die VAD
für die finale Transkription aus. Bei ca. 1.000–1.500 gleichzeitig Sprechenden
sind das 64–96 MB/s Schreiblast und rund 2–3 CPU-Kerne nur für VAD und
Dekodieren. Das trägt ein einzelner Python-Prozess nicht mehr.

## Was geändert wurde (Voraussetzung für mehrere Instanzen)

| Problem bei mehreren Instanzen | Lösung |
|---|---|
| Admin ändert eine Einstellung, nur eine Instanz sieht sie | Settings-Cache läuft nach `SETTINGS_CACHE_TTL_S` (Standard 30 s) ab; ASR-Backends werden danach neu gebaut |
| Login-Limit vervielfacht sich mit der Instanzzahl | Zähler liegt in Redis (fester Zeitraum je IP), ohne Redis oder bei Ausfall im Prozessspeicher |
| Zwei Instanzen starten gleichzeitig die Migration oder die Key-Rotation | Beide nehmen einen PostgreSQL-Advisory-Lock, die anderen warten und finden nichts mehr zu tun |
| Hintergrundschleifen (Session-Cleanup, Archiv, Auto-Archiv) laufen N-fach | Pro Durchlauf gewinnt eine Instanz einen Redis-Lock (`leader_lock.py`) |
| Start-Cleanup löschte alle `chunks/session_*` und damit laufende Aufnahmen anderer Instanzen | Gelöscht wird nur, was älter als 5 Minuten (Start) bzw. 30 Minuten (Schleife) ist **und** zu keiner Session im Store gehört |
| Fehlgeschlagene Aufnahme lag nur auf der Platte der ausführenden Instanz | Wird sofort verschlüsselt nach S3 (Garage) hochgeladen, der Retry funktioniert auf jeder Instanz. Ohne S3 oder bei Fehler bleibt es lokal wie bisher |
| Der Proxy-Header-Check kannte nur einzelne IPs | `TRUSTED_PROXY_IPS` akzeptiert auch CIDR-Bereiche (`10.0.1.0/24`) |

Ohne `REDIS_URL` verhält sich alles wie vorher (eine Instanz).

## Brauche ich ein spezielles Routing?

### Alle Instanzen auf einem Knoten: nein

Replicas auf demselben Knoten teilen sich das Volume `app-chunks`
(`/app/chunks`). Nach einem Verbindungsabbruch liest die Replica, die den
Wiederverbindungsversuch bekommt, den Pfad der PCM-Datei aus der Redis-Session
und findet dieselbe Datei. Dein vorhandener nginx bleibt also **unverändert**
und zeigt wie bisher auf `APP_PORT`.

Zu tun ist nur:

1. In `docker-swarm.yml` beim Dienst `app` die Replicas erhöhen und auf einen
   Knoten festlegen:

   ```yaml
   deploy:
     replicas: 3
     placement:
       constraints: [node.hostname == <knoten>]
   ```
2. Redis und S3 (Garage) laufen lassen (beide sind im Stack enthalten).

**Dein nginx läuft auf dem Host, nicht im Stack:** Für diesen Fall ändert sich
nichts. Er spricht weiter `127.0.0.1:APP_PORT` an, Swarm verteilt dahinter über das
Routing-Mesh auf die Replicas (WebSocket funktioniert dort wie bisher), und
`TRUSTED_PROXY_IPS` bleibt unverändert.

### Instanzen auf mehreren Knoten: ja, ein `hash` im nginx

Ein nginx **auf dem Host** kann das nicht leisten: Er erreicht die Replicas nur
über das Routing-Mesh (reihum, nicht festlegbar) und kann `tasks.app` nicht
auflösen (das gibt es nur im Docker-Netz). Das heißt: bei mehreren Knoten wird
ein zusätzlicher nginx als Swarm-Dienst im Stack nötig, den dein Host-nginx
anspricht. Für den einfachen Weg deshalb auf einem Knoten bleiben und dort
skalieren.


Jeder Knoten hat sein eigenes Volume. Eine Wiederverbindung muss bei der Instanz
landen, die die PCM-Datei hat. Landet sie woanders, **lehnt die App sie ab**:
Der WebSocket sendet `{"error": …, "code": "recording_audio_unavailable"}` und
schließt mit Code 1011; die Browser-App zeigt dazu eine eigene Meldung. Session und
Dateien bleiben unberührt, die richtige Instanz kann die Aufnahme also noch
fortsetzen. (Früher hätte `open(…, "ab")` dort still eine neue, leere Datei
angelegt, und die früheren Aufnahmeteile hätten gefehlt.) Die Prüfung ersetzt das
Routing nicht, sie macht aus einem stillen Datenverlust einen sichtbaren Fehler.

Die Wiederverbindung trägt dieselbe `session_id` in der URL
(`/api/v1/records/ws/record?session_id=…`), danach routet der nginx. Ein Cookie
oder eine IP-Bindung wäre schlechter: Hinter einer Klinik-NAT landen alle Clients
auf einer Instanz.

Voraussetzungen: nginx läuft **im Docker-Netz des Stacks** (als Swarm-Dienst, nur
dort löst `tasks.app` auf), Version ≥ 1.27.3. Nur der WebSocket-Block ändert sich:

```nginx
resolver 127.0.0.11 valid=5s ipv6=off;

upstream opendox_ws {
    zone opendox_ws 64k;
    hash $arg_session_id;        # NICHT "consistent", siehe unten
    server tasks.app:5000 resolve;
}

location /api/v1/records/ws/record {
    proxy_pass http://opendox_ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 3600s;
}
```

Der restliche nginx (`location /` usw.) bleibt wie bisher. Zwei Dinge dabei:

- **`TRUSTED_PROXY_IPS`** muss das Overlay-Netz des Stacks enthalten
  (`docker network inspect opendox_default`, Feld `Subnet`, z. B. `10.0.1.0/24`),
  weil die App den nginx dann als direkten Nachbarn mit wechselnder Adresse sieht.
  Sonst werden `X-Forwarded-Proto/-Host` für die OIDC-Weiterleitung ignoriert.
- Ändert sich die Instanzzahl (Ausfall, Zuschalten, jeder Schritt eines
  Rolling-Updates), wechseln rund drei Viertel der Sitzungen die Instanz (22 von 30
  im Test). Für bestehende Verbindungen ist das egal, nur eine Wiederverbindung
  genau in diesem Moment träfe die falsche Instanz. Deshalb besser außerhalb der
  Stoßzeiten skalieren.

### Was getestet wurde

Platzhalter-Backends in einem Docker-Netz mit DNS-Alias (wie Swarm/Compose):

| Variante | Klebt? | Sessions, die bei Ausfall oder Zuschalten wechseln |
|---|---|---|
| Swarm-Routing-Mesh (VIP) | nein, reihum | – |
| nginx, `server tasks.app:5000 resolve;` + `hash $arg_session_id;` | **ja** | 22 von 30 |
| nginx, `server tasks.app:5000 resolve;` + `hash $arg_session_id consistent;` | **nein**, fällt auf Reihum zurück | – |
| nginx, feste Serverliste + `hash … consistent;` | ja | nur die der betroffenen Instanz, braucht aber je Instanz einen eigenen Dienst |
| HAProxy (`server-template`, `hash-type consistent`) | ja | 3 von 12 (nur die der betroffenen Instanz) |

HAProxy wäre die Variante mit den wenigsten Verschiebungen, ist aber eine weitere
Komponente und für den einfachen Fall nicht nötig. Mit Docker Compose
(`--scale app=3`) gilt dasselbe, nur heißt der DNS-Name `app` statt `tasks.app`
(getestet mit HAProxy).

## Was noch offen ist

- **Grenzen der Resume-Prüfung:** Sie vergleicht die Dateigröße mit dem Wert, den
  die vorige Verbindung gespeichert hat. Ist das Backend dabei abgestürzt, bevor es
  die Größe gespeichert hat (Wert 0), lässt sich ein Verlust nicht erkennen. Der
  Desktop-Client (eigenes Repository) kennt den Fehlercode noch nicht und sieht nur
  einen geschlossenen Socket.
- **Nicht gemessen:** das Verhalten bei tausend gleichzeitigen WebSockets in einem
  Prozess und der Durchsatz der Platte bei 96 MB/s.
- Kubernetes: nicht getestet. `ingress-nginx` kennt laut Dokumentation die
  Annotation `nginx.ingress.kubernetes.io/upstream-hash-by: "$arg_session_id"`.

## Betrieb

- `SETTINGS_CACHE_TTL_S=0` schaltet den Ablauf des Settings-Caches ab. Das ist nur
  mit einer einzigen Instanz sinnvoll.
- Beim Hochfahren aller Instanzen auf einmal laufen Migrationen und Key-Rotation
  nur einmal (Advisory-Locks), die anderen warten.
