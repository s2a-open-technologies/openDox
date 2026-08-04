# Härtungs-Roadmap für openDox (Docker Compose, on-premise)

**Update (Juli 2026): Kubernetes ist zurückgestellt.** openDox ist auf
On-Premise-Betrieb für einzelne Praxen/Kliniken ausgelegt, nicht auf
zentral gehostetes Multi-Tenant-SaaS. Kubernetes' eigentlicher Mehrwert
(horizontale Skalierung über mehrere Nodes, Self-Healing über ein
Node-Fleet, Resource-Isolation über viele heterogene Workloads) greift bei
"ein Server, eine GPU, eine Praxis" nicht — der reale Flaschenhals
(Whisper/LLM-Inferenz) skaliert ohnehin nicht durch mehr Nodes, sondern nur
durch mehr GPU-Kapazität. Dem stünde der operative Preis eines
K8s-Clusters (Control-Plane, CNI, Ingress-Controller, PV-Provisioning,
GPU-Device-Plugin) gegenüber, der für dieses Einsatzszenario nicht durch
entsprechenden Nutzen gedeckt ist. Diese Liste bleibt als Referenz stehen
(K8s-spezifische Aktionen sind entsprechend markiert), der **aktuelle
Fokus liegt auf Tier 1 gegen die bestehende `docker-compose.yml`** — die
meisten Punkte sind unabhängig vom Deployment-Ziel sinnvolle Härtung.
Kubernetes wird erst wieder relevant, falls sich das Modell tatsächlich
Richtung zentral gehostetes Multi-Tenant-Hosting verschiebt.

**Ursprüngliche Annahme (falls doch relevant)**: vorerst nur **eine
Replica** des App-Pods (keine horizontale Skalierung). Punkte, die nur bei
mehreren Replicas relevant werden, stehen explizit in Tier 4 als
zurückgestellte Zukunftsarbeit.

---

## Tier 1 — Muss vor dem Deploy erledigt werden

### 1.1 Den unechten `/api/health`-Endpoint reparieren, bevor ein Probe darauf zeigt — ✅ erledigt

**Update:** `/api/ready` existierte bereits, war aber kaputt — `readiness_check()`
importierte `RedisSessionStore` aus dem falschen Modul (`session_store`
statt `session_store_redis`), jeder Aufruf warf einen `ImportError` (500).
Fix: korrekter Import, mit `TestClient` gegen eine echte Postgres-Instanz
verifiziert (`GET /api/ready` → 200 `{"status": "ready"}`). Der tote
`root_view`-Code (`/api/health`) wurde bewusst nicht angefasst, wie in der
ursprünglichen Aktion vorgesehen.

- **Problem (historisch)**: `/api/health` ist nirgends registriert; der Request fällt
  durch `SPAStaticFiles`s 404→`index.html`-Fallback in `backend/run.py` und
  liefert HTTP 200 mit der SPA-Shell zurück — egal wie kaputt Backend/DB
  gerade sind. Die echten, funktionierenden Endpoints sind `/api/endpoint`
  und `/api/version`, direkt in `create_app()` registriert.
  `backend/views/root_view/`s `/health` und ein doppeltes `/api/endpoint`
  auf `root_bp` sind toter Code — werden nie per `include_router()`
  eingebunden.
- **Warum**: Ein Liveness-/Readiness-Probe auf `/api/health` würde den Pod
  als gesund melden, selbst wenn App/DB komplett hinüber sind — Kubernetes
  würde einen hängenden Pod nie neu starten.
- **Aktion**: `/api/endpoint` für Liveness verwenden. Einen neuen
  `/api/ready`-Endpoint hinzufügen, der die DB-Verbindung prüft (Vorbild:
  `check_postgres()` in `backend/views/settings_api/settings_routes.py`,
  `db.exec(select(1))`). Den toten `root_view`-Code in Ruhe lassen bzw.
  entfernen — Readiness nicht darauf aufbauen.
- **Betrifft**: `backend/run.py`,
  `backend/views/settings_api/settings_routes.py` (Vorbild),
  `backend/views/root_view/`.

### 1.2 Alembic-Migrationen aus dem Pod-Start herauslösen — ✅ erledigt

**Update:** `backend/run.py` hat keine `_run_alembic_migrations()`-Funktion
mehr, keine Alembic-Aufrufe irgendwo unter `backend/` — Migrationen laufen
nur noch über `entrypoint.sh: alembic upgrade head`, an genau einer Stelle.
Ursprüngliches Problem unten als Referenz stehen gelassen.

- **Problem (historisch)**: Migrationen liefen **zweimal** pro Boot — einmal über
  den Dockerfile-`CMD` (`Dockerfile:61`,
  `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 5000`),
  und nochmal über `_run_alembic_migrations()`, synchron in `create_app()`
  aufgerufen (`backend/run.py`), noch bevor das FastAPI-App-Objekt
  überhaupt existiert.
- **Warum**: Migrationen an den App-Container-Start zu koppeln bedeutet:
  eine langsame/fehlschlagende Migration äußert sich als App-Crash-Loop
  statt als eigener, klar erkennbarer Fehler, und kann Startup-Probes zum
  Timeout bringen. Lohnt sich auch bei replicas:1 als Sauberkeits-/
  Korrektheits-Fix (aktuell schlicht doppelte Arbeit).
- **Aktion**: Für Docker Compose: einen eigenen `migrate`-Service in
  `docker-compose.yml` (gleiches Image, `command: alembic upgrade head`),
  `app` bekommt `depends_on: migrate: condition: service_completed_successfully`.
  (Bei einem künftigen K8s-Deploy wäre das Äquivalent ein `Job` oder
  `initContainer`, der vor dem App-Container abgeschlossen sein muss.) In
  beiden Fällen: den In-App-Migrationsaufruf und den
  Dockerfile-`CMD`-Migrationsschritt entfernen, sobald der separate Schritt
  existiert — Migrationslogik soll an genau einer Stelle leben.
- **Betrifft**: `backend/run.py` (`_run_alembic_migrations`,
  `create_app()`), `Dockerfile:61`, `alembic.ini`, `alembic/`.

### 1.3 Secrets und Konfiguration trennen — ✅ erledigt (für den Produktionspfad)

**Update:** `docker-compose.yml` bleibt bewusst der lokale Dev-/Demo-Stack
mit schwachen Klartext-Defaults (unten als Problem beschrieben — für diesen
Zweck jetzt explizit so gewollt, nicht mehr offen). Für Produktion gibt es
stattdessen **`docker-swarm.yml`** + **`create_docker_secrets.sh`**: alle
sensiblen Variablen (`SECRET_KEY`, `SQL_PASS`, `ENCRYPTION_KEY`,
`WHISPER_API_KEY`, S3-/Garage-Credentials) laufen über Swarms native
`secrets:` + die bestehende `{VAR}_FILE`-Konvention, keine Klartext-Defaults
im Manifest. `ENCRYPTION_KEY_PREVIOUS` ist bewusst **nicht** Teil des
Standard-Deploys (ein zufällig generierter „vorheriger" Schlüssel wäre
sinnlos) — stattdessen ein optionales Overlay `docker-swarm.rotation.yml`,
das nur während einer aktiven Schlüsselrotation dazugeschaltet wird (siehe
Kommentar dort für den vollen Rotations-Ablauf). OIDC-Client-Secret bleibt
unangetastet, liegt DB-seitig in `OidcSettingsModel`, nicht als Env-Var.
Der auf srv01 hartkodierte `ENCRYPTION_KEY`/LangSmith-Key (Gespräch vom
2026-07-13) ist davon unberührt — das ist eine separate, manuelle Migration
auf dem echten Produktivserver, kein Code-/Manifest-Thema.

- **Problem (historisch, gilt für `docker-compose.yml` als Dev-Stack weiter)**: `docker-compose.yml` liefert schwache Defaults direkt mit
  (`SECRET_KEY: ${SECRET_KEY:-ChangeThisInProduction}`,
  `SQL_PASS: ${SQL_PASS:-postgres}`,
  `WHISPER_API_KEY: ${WHISPER_API_KEY:-loc-123}`) — für lokales
  Compose/Demo okay, aber nicht sicher für ein Cluster-Manifest.
- **Warum**: Medizinnahe Anwendung (PHI-Daten) — Default-Secrets in
  Produktion sind ein echtes Compliance- und Sicherheitsrisiko, nicht nur
  Kosmetik.
- **Aktion**: Sensible Variablen (`SECRET_KEY`, `SQL_PASS`,
  `ENCRYPTION_KEY`, `ENCRYPTION_KEY_PREVIOUS`, `WHISPER_API_KEY`,
  OIDC-Client-Secret) auf Docker Composes native
  [`secrets:`](https://docs.docker.com/compose/how-tos/use-secrets/)
  abbilden (dateibasiert, gemountet unter `/run/secrets/`) statt als
  Klartext-Defaults in `docker-compose.yml`. Die bestehende
  `{VAR}_FILE`-Konvention in `env_or_file()`
  (`backend/components/modules/env.py`) passt direkt dazu — für die
  Encryption-Keys speziell dieser Variante den Vorzug geben vor reinen
  Env-Vars. (Bei einem künftigen K8s-Deploy: gleiches Prinzip über
  `Secret`/`ConfigMap`.) Kein Deploy darf jemals die Fallback-Werte aus der
  Compose-Datei in Produktion verwenden — genau das ist auf dem
  Produktivserver aktuell noch der Fall (`ENCRYPTION_KEY` und ein
  LangSmith-Key standen im Klartext in der Server-Compose-Datei, siehe
  Gespräch vom 2026-07-13).
- **Betrifft**: `backend/components/modules/env.py` (Referenz, keine
  Änderung), `docker-compose.yml`, künftige k8s-Manifeste (falls relevant).

### 1.4 Reverse-Proxy-Header-Vertrauen absichern — ✅ erledigt (Teil a bleibt Apache-seitig offen)

**Update:** Teil (c), `CORSMiddleware.allow_origins`, ist erledigt —
`CORS_ALLOWED_ORIGINS` (komma-getrennt, `backend/run.py`) statt hartkodiertem
`"*"`; leer/nicht gesetzt fällt weiterhin auf `"*"` zurück, loggt aber jetzt
eine Warnung. In `docker-compose.yml`/`docker-swarm.yml`/`.env.example`
verdrahtet. Konkreter Origin-Wert für srv01 noch nicht gesetzt (unbekannt,
folgt sobald klar).

Teil (b) ist erledigt, aber anders gelöst als ursprünglich skizziert: statt
uvicorns `--proxy-headers`/`--forwarded-allow-ips` (das hätte
`request.url.scheme` korrigiert, aber `_build_redirect_uri` liest
`X-Forwarded-Host` direkt aus den Headern — Starlette hat dafür keinen
eingebauten Trust-Mechanismus) gibt es jetzt eine eigene
`mark_trusted_proxy`-Middleware (`backend/run.py`), die `request.state.trusted_proxy`
setzt, bevor irgendein Downstream-Code den Peer sieht. `_build_redirect_uri`
(`oidc_routes.py`) ignoriert `X-Forwarded-Proto`/`-Host` komplett, wenn der
direkte Peer kein vertrauenswürdiger Proxy ist. Vertrauenswürdige IPs kommen
aus `TRUSTED_PROXY_IPS` (komma-getrennt) — leer/nicht gesetzt erkennt
automatisch Loopback + die Docker-Gateway-IP des Containers
(`get_trusted_proxy_ips()`/`_detect_docker_gateway()` in
`backend/components/modules/env.py`, parst `/proc/net/route`, kein
`ip`-Binary nötig). Wichtiger Fund dabei: eine auf **demselben Host**
laufende Reverse-Proxy-Verbindung (`Apache → 127.0.0.1:APP_PORT`) kommt im
Container **nicht** als `127.0.0.1` an, sondern als die Docker-Gateway-IP
(NAT durch das Port-Publishing) — empirisch verifiziert, `127.0.0.1` allein
als Trust-Wert hätte hier nicht funktioniert.

**Teil (a) — dass Apache selbst `X-Forwarded-For` kontrolliert statt
Client-Werte durchzureichen — ist reine VHost-Konfiguration, kann nicht aus
diesem Repo heraus behoben werden, bleibt offen.**

- **Problem (historisch)**: Nirgends `ProxyHeadersMiddleware`/`TrustedHostMiddleware`.
  `_build_redirect_uri` in `backend/views/auth_api/oidc_routes.py` liest
  `X-Forwarded-Proto`/`X-Forwarded-Host` direkt aus den rohen
  Request-Headern, ohne Validierung. `CORSMiddleware` ist mit
  `allow_origins=["*"]` konfiguriert (`backend/run.py`).
- **Warum**: Hinter jedem Reverse-Proxy (aktuell produktiv: Apache auf
  srv01, siehe `opendox.vireva.eu`-VHost) werden diese Header Teil der
  Vertrauensgrenze für den OIDC-Redirect. Überschreibt der Proxy
  client-seitig mitgeschickte Werte nicht zwingend, kann ein Client sie
  fälschen und die OIDC-Redirect-URL manipulieren — eine echte
  Auth-Flow-Schwachstelle. **Bereits jetzt relevant**, nicht erst bei K8s.
- **Aktion**: (a) Sicherstellen, dass Apache (aktuell `RequestHeader set
  X-Forwarded-Proto`/`X-Forwarded-Port` in der VHost-Config)
  `X-Forwarded-For` ebenfalls kontrolliert statt Client-Werte
  durchzureichen. (b) Explizites Proxy-Vertrauen in der App ergänzen
  (uvicorn `--proxy-headers --forwarded-allow-ips=...`, begrenzt auf
  `127.0.0.1`/den internen Proxy, oder `TrustedHostMiddleware`).
  (c) `CORSMiddleware`s `allow_origins` auf die tatsächliche(n)
  Deploy-Origin(s) einschränken statt `"*"`.
- **Betrifft**: `backend/views/auth_api/oidc_routes.py`, `backend/run.py`
  (`CORSMiddleware`, uvicorn-Startparameter), Apache-VHost-Config.

---

**Ab hier (Tier 2-4): zurückgestellt.** Die folgenden Punkte sind
größtenteils K8s-/Multi-Replica-spezifisch (Ingress-Manifeste,
Pod-Anti-Affinity, HPA, Registry-Tagging für Cluster-Rollouts) und werden
erst wieder relevant, falls sich das Deployment-Modell Richtung
zentral gehostetes Multi-Tenant-Hosting verschiebt — siehe Hinweis am
Dokumentanfang. Als Referenz belassen, nicht als aktuelle Aufgabenliste.

## Tier 2 — Sollte gemacht werden, echtes Risiko (kurz vor/nach Go-Live)

### 2.1 Graceful Shutdown für laufende WebSocket-Aufnahmesessions

- **Problem**: `lifespan()` in `backend/run.py` fährt an sich schon sauber
  herunter (bricht `_stale_session_cleanup_loop` ab und wartet darauf), aber
  es gibt keine Drain-Logik für aktive `/ws/record`-Verbindungen
  (`backend/views/record_api/record.py`), wenn der Pod terminiert wird
  (Rolling Deploy, Node-Drain, OOM). Kubernetes' Standard-
  `terminationGracePeriodSeconds` ist 30s. Eine Session, die genau dann
  mitten in der Aufnahme ist, wird hart getrennt; ein Reconnect gegen einen
  frischen Prozess kann auf den bekannten Bug treffen, bei dem
  `create_session()` die PCM-Datei leert, wenn der Store nichts von der
  Session weiß.
- **Warum**: Bei replicas:1 ist **jedes** Rolling Deploy oder jeder Restart
  eine potenzielle Unterbrechung für alle, die gerade aktiv aufnehmen — ein
  echtes, nutzerspürbares Verfügbarkeitsproblem, unabhängig von Skalierung.
- **Aktion**: `terminationGracePeriodSeconds` auf einen Wert erhöhen, der
  realistische Aufnahmelängen abdeckt; einen `preStop`-Hook erwägen, der
  neue Aufnahmen blockiert, laufende aber zu Ende laufen/finalisieren lässt;
  sicherstellen, dass der Reconnect-Pfad im Frontend den
  PCM-Truncation-Bug nicht auch bei einem normalen Deploy auslöst (nicht
  nur bei einem Crash).
- **Betrifft**: `backend/run.py` (`lifespan`),
  `backend/views/record_api/record.py` (`/ws/record`,
  `create_session()`-Aufrufstellen), künftiges Deployment-Manifest.

### 2.2 Resource Requests/Limits, inklusive GPU-Scheduling für Whisper

- **Problem**: Aktuell keine Resource Requests/Limits; der
  GPU-Reservierungsblock für Whisper in `docker-compose.yml` ist
  auskommentiert. Drei Workloads brauchen unterschiedliche Profile: App
  (moderat CPU/RAM), Whisper (`whisper_server/`, GPU-gebunden), Parakeet
  (`parakeet_server/`, nur CPU).
- **Warum**: Ohne Requests/Limits kann der Scheduler unruhige Nachbarn
  zusammenlegen und unvorhersehbar per OOM killen; ohne explizites
  `nvidia.com/gpu`-Request landet Whisper gar nicht erst auf einem
  GPU-Node.
- **Aktion**: Requests/Limits pro Workload definieren; Whisper bekommt
  `nvidia.com/gpu: 1` plus `nodeSelector`/`tolerations` für den GPU-Pool;
  sicherstellen, dass der NVIDIA-Device-Plugin auf diesem Pool installiert
  ist.
- **Betrifft**: `whisper_server/Dockerfile`, `parakeet_server/Dockerfile`,
  `Dockerfile`, künftige Deployment-Manifeste.

### 2.3 Ingress-/WebSocket-Konfiguration

- **Problem**: `/ws/record` braucht WebSocket-Upgrade-Unterstützung und
  großzügige Idle-Timeouts auf Ingress-Ebene — dieselbe Problemklasse, die
  AGENTS.md bereits für Apache + `mod_proxy_wstunnel` dokumentiert.
- **Warum**: Standard-Ingress-Timeouts (oft 60s) killen sonst
  lang laufende Aufnahme-Verbindungen stillschweigend.
- **Aktion**: Ingress-Controller/-Class wählen, WS-taugliche
  Timeout-Annotations setzen, über `ROOT_PATH` routen (zur Laufzeit bereits
  unterstützt via `_inject_root_path` in `backend/run.py` — passt gut zu
  Ingress-Pfad-Routing, keine App-Änderung nötig).
- **Betrifft**: künftiges Ingress-Manifest; `backend/run.py` (nur Referenz).

### 2.4 Image-/Registry- und Tagging-Strategie

- **Problem**: Drei Images (App, Whisper, Parakeet) werden aus diesem Repo
  gebaut und per lokalem Build/Push-Skript nach `registry.nutsolution.de`
  gepusht, in `docker-compose.yml` mit fließenden Tags referenziert
  (`:latest`, `:demo`).
- **Warum**: Fließende Tags sind für lokales Compose/Demo okay, aber ein
  Antipattern für k8s — Deployments brauchen unveränderliche,
  versionsfixierte Tags für verlässliche Rollouts/Rollbacks.
- **Aktion**: Fixierte Tags (die vorhandene `bump_version.py --current`
  Version, oder Git-SHA-basiert) für alle drei Images in
  Cluster-Manifesten verwenden, `imagePullPolicy` entsprechend setzen
  (`IfNotPresent` bei fixierten Tags).
- **Betrifft**: `docker-compose.yml` (Referenz), künftige k8s-Manifeste.

### 2.5 Persistent Volumes: was einen Pod-Restart wirklich überleben muss

- **Problem**: Compose definiert `app-chunks` (`/app/chunks`),
  `app-models-cache`, `app-certs`, `app-logs`, plus `postgres-data`,
  `redis-data`, `whisper-data`. Nicht alle brauchen zwingend eine k8s-PVC.
  `app-logs` wird offenbar gar nicht genutzt — die App loggt ausschließlich
  auf stdout über uvicorns Logger
  (`backend/components/modules/logger.py` hat nirgends einen
  `FileHandler`, nur Weiterleitung über `uvicorn.error`s Handler).
- **Warum**: Jedes Compose-Volume unbesehen als PVC zu übernehmen
  verschwendet Storage und bringt unnötige zustandsbehaftete Komplexität.
- **Aktion**: Jedes Volume einordnen in "PVC (wirklich zustandsbehaftet —
  `app-chunks` braucht das auch bei replicas:1)" oder "nicht nötig
  (`app-logs`, da Logs stattdessen an den Cluster-Log-Agent gehen sollten)",
  bevor Manifeste geschrieben werden.
- **Betrifft**: `docker-compose.yml` (Referenz),
  `backend/components/modules/logger.py` (bestätigt reines
  Stdout-Logging), `backend/run.py`/`backend/views/record_api/record.py`
  (Nutzung von `chunks/`).

---

## Tier 3 — Nice to have / Härtung (nach Go-Live, opportunistisch)

### 3.1 Logging / Observability

Reines Stdout-Logging ist bereits das richtige Container-Muster; das
`app-logs`-Volume ist ein Überbleibsel und sollte beim Umzug nach k8s
wegfallen. Optional: strukturiertes (JSON-)Log-Format, falls der
Log-Stack des Clusters davon profitiert. Nicht blockierend.

### 3.2 Container-Healthcheck aufräumen

`Dockerfile:55-56`s `HEALTHCHECK` zeigt bereits korrekt auf
`/api/endpoint` (anders als die `/api/health`-Falle aus 1.1), wird aber
rein informativ, sobald k8s' eigene Probes übernehmen — keine Änderung
nötig, nur im Cluster nicht darauf verlassen.

### 3.3 Security-Header-Review

`backend/run.py` setzt `Permissions-Policy: microphone=(self),
camera=(self)` auf jeder Antwort. Lohnt sich als Durchgang zusammen mit der
Härtung aus 1.4 — z. B. `Strict-Transport-Security`,
`X-Content-Type-Options`, `Content-Security-Policy`, sobald TLS am
Cluster-Rand terminiert. Niedrige Priorität.

### 3.4 Integrationstests gegen echte LDAP-/OIDC-Instanzen (erst mit CI/CD sinnvoll)

- **Problem**: `tests/services/test_ldap_service.py` sowie
  `tests/services/test_oidc_service.py` und `tests/auth/test_oidc_routes.py`
  mocken `ldap3.Connection` bzw. `httpx`/JWKS komplett weg. Sie verifizieren
  openDox' eigene Logik (Suchfilter-Aufbau, State-/CSRF-Handling,
  Rollen-Mapping, JWT-Signaturprüfung mit einem echten generierten
  Schlüsselpaar), aber nicht, ob ein echter LDAP-Server oder OIDC-Provider
  sich tatsächlich so verhält wie angenommen.
- **Warum**: Ein zweiter Test-Tier mit echten, containerisierten Diensten
  (z. B. ein `openldap`-Container mit LDIF-Testdaten, Keycloak oder ein
  leichterer `mock-oauth2-server` für OIDC) ist möglich, lohnt sich aber nur,
  wenn eine Pipeline ihn automatisch bei jedem Push ausführt — manuell
  gepflegt verrottet er (Container-Setup wird nicht aktuell gehalten, läuft
  irgendwann gegen falsche Annahmen oder gar nicht mehr mit).
- **Aktion**: Zurückstellen, bis eine CI/CD-Pipeline existiert. Dann: ein
  separates `tests/integration/`-Verzeichnis mit eigenem Pytest-Marker (z. B.
  `@pytest.mark.integration`) und Docker-Compose-Fixtures für
  OpenLDAP/Keycloak anlegen, das ausschließlich in der Pipeline läuft — nicht
  im schnellen lokalen `uv run pytest`-Lauf, der weiterhin ohne externe
  Abhängigkeiten funktionieren soll.
- **Betrifft**: `tests/services/test_ldap_service.py`,
  `tests/services/test_oidc_service.py`, `tests/auth/test_oidc_routes.py`,
  künftiges `tests/integration/`, künftige CI/CD-Pipeline-Konfiguration.

---

## Tier 4 — Explizit außerhalb des Scopes bei replicas:1 (nur Zukunftsarbeit)

Bewusst aufgeführt, damit hier nichts versehentlich schon jetzt mitgeplant
wird, und damit eine spätere Skalierung eine Startcheckliste hat:

- **Session-Store / Audio-Chunk-Handling**: `RedisSessionStore` vs.
  In-Memory-Fallback (`backend/components/services/session_store.py`) hält
  nur Session-*Metadaten* — die eigentliche PCM-Audiodatei landet immer
  lokal auf der Platte (`chunks/session_{id}.pcm`, direkt vom
  `/ws/record`-WebSocket-Handler in
  `backend/views/record_api/record.py` geschrieben), was nur funktioniert,
  weil es genau einen Pod gibt. Bei einem Reconnect, wenn der Store nichts
  von der Session weiß (z. B. Redis-TTL abgelaufen), wird
  `create_session()` erneut aufgerufen und **leert die PCM-Datei** —
  bereits aufgenommenes Audio geht dabei stillschweigend verloren, aktuell
  verdeckt durch die Tatsache, dass es immer nur einen Pod/Prozess gibt.
  Eine Skalierung auf N Replicas bräuchte entweder Sticky-WebSocket-Routing
  (Ingress `sessionAffinity`) oder einen Umbau auf gemeinsam genutzten
  Storage/Objektspeicher für laufende Aufnahmen, plus einen Fix für diesen
  Reconnect-Bug im Mehr-Pod-Fall.
- **Startup-Cleanup-Sicherheit**: `_cleanup_orphaned_chunk_files()` in
  `backend/run.py` löscht bei jedem Boot alle `chunks/session_*.pcm/.wav`,
  unter der Annahme, dass noch keine Sessions existieren. Sicher bei einem
  einzelnen neu startenden Pod; würde bei einem gemeinsam genutzten
  ReadWriteMany-Volume mit mehreren Replicas die laufenden Session-Dateien
  eines Nachbar-Pods löschen.
- **Settings-Cache-Invalidierung**: `SettingsService` und die
  ASR-Backend-Factory (`backend/components/services/settings_service.py`,
  `backend/components/services/asr_factory.py`) sind Singletons pro
  Prozess; `invalidate_cache()`/`reset_backends()` leeren nur den Cache des
  aktuellen Prozesses. Bei einem Prozess unproblematisch; bräuchte bei
  replicas>1 Redis-Pub/Sub o. Ä.
- **HPA / Pod-Anti-Affinity / Multi-Replica-Resourcen-Sizing**: hier
  überhaupt nicht behandelt.

**Verwandtes, aber unabhängiges Thema**: Durchsatz der ASR-/LLM-Backends
selbst (Whisper/Parakeet/LLM serialisieren aktuell pro Server auf eine
Anfrage gleichzeitig) ist in `docs/scaling-model-serving.md` behandelt —
nicht Teil dieser Kubernetes-Roadmap, da orthogonal zur Pod-Replica-Frage.

---

## Referenzierte Dateien

- `backend/run.py` — `create_app()`, `lifespan()`, Migrationen, Health-Routen
- `backend/views/record_api/record.py` — `/ws/record`, Chunk-Datei-Handling
- `backend/views/settings_api/settings_routes.py` — `/services-health/`,
  Vorbild `check_postgres()` für `/api/ready`
- `backend/views/auth_api/oidc_routes.py` — `_build_redirect_uri`
- `backend/components/services/session_store.py`,
  `backend/components/services/settings_service.py`,
  `backend/components/services/asr_factory.py` — Tier-4-Punkte
- `backend/components/modules/logger.py` — bestätigt reines Stdout-Logging
- `Dockerfile`, `docker-compose.yml` — aktuelles Single-Host-Deployment,
  Ausgangsbasis für die Übersetzung nach k8s-Manifesten
