---
title: "openDox"
subtitle: "Installations- und Betriebshandbuch"
---

# Über dieses Handbuch

Dieses Handbuch richtet sich an den IT-Betrieb, der openDox installiert,
absichert, aktualisiert und sichert. Es setzt Grundkenntnisse in Linux,
Docker und Reverse-Proxy-Konfiguration voraus. Die Einrichtung in der
Weboberfläche (Dienste, Anmeldung, Kategorien) beschreibt das
*Administrationshandbuch*, die Bedienung das *Benutzerhandbuch*.

Befehle sind in `Schreibmaschinenschrift` gesetzt und werden, wenn nicht
anders angegeben, im Verzeichnis der openDox-Installation ausgeführt.

## Wichtiger Hinweis: Kein Medizinprodukt

openDox ist **kein zugelassenes Medizinprodukt** gemäß Medizinproduktegesetz
(MPG) oder vergleichbaren Regularien (z. B. EU-MDR, FDA). Es dient
ausschließlich der Unterstützung bei der Dokumentation. Alle maschinell
erstellten Texte müssen von qualifiziertem Fachpersonal geprüft werden.

Die betreibende Einrichtung ist für den rechtskonformen Betrieb
verantwortlich, insbesondere für Datenschutz (DSGVO, § 203 StGB),
Informationssicherheit, Zugriffsrechte und Löschfristen. Die Datei
`DISCLAIMER.md` im Quellcode enthält den vollständigen Betreiberhinweis,
`docs/data-mapping.md` eine Übersicht der Datenflüsse als Grundlage für das
Verzeichnis der Verarbeitungstätigkeiten.

# Systemüberblick

## Komponenten

openDox besteht aus mehreren Docker-Diensten. Alle außer der App sind nur im
internen Docker-Netz erreichbar.

| Dienst | Aufgabe | Port (intern) |
|:-----------|:-------------------------------|:-----|
| **app** | openDox-Server: Weboberfläche, API, Verarbeitung | 5000 |
| **postgres** | Datenbank (Benutzer, Einstellungen, verschlüsselte Texte) | 5432 |
| **redis** | Sitzungen laufender Aufnahmen, Sperren bei mehreren Instanzen | 6379 |
| **whisper** | Finale Transkription (faster-whisper, OpenAI-kompatibel) | 5002 |
| **parakeet** | Live-Vorschau (Streaming per WebSocket) | 5001 |
| **garage** | S3-kompatibler Objektspeicher für Audio-Downloads und ausgelagerte Fehlaufnahmen | 3900 |
| **garage-init** | Einmalige Einrichtung von Garage (Bucket, Zugangsschlüssel), beendet sich danach | |

Nach außen veröffentlicht werden nur die App (`APP_PORT`, Standard 20000)
und Parakeet (`PARAKEET_PORT`, Standard 5001, nur für einen Proxy auf einem
anderen Rechner nötig). Beide Ports per Firewall auf den Reverse Proxy
beschränken.

Nicht enthalten sind:

- das **Sprachmodell (LLM)** für die Zusammenfassungen, z. B. Ollama, vLLM
  oder ein interner LLM-Proxy mit OpenAI-kompatibler Schnittstelle,
- optional ein **PII-Sanitizer** (z. B. EntityGuard),
- der **Reverse Proxy** mit TLS-Zertifikat (Apache oder nginx).

![Systemarchitektur](bilder/installation/01-architektur.png)

## Datenfluss in Kürze

Browser bzw. Desktop-Client senden das Audio per WebSocket an die App. Die
App schreibt es als Rohdatei in das Volume `app-chunks` und leitet es für die
Live-Vorschau an Parakeet weiter. Nach dem Beenden schickt die App die
Sprachabschnitte an Whisper, korrigiert Fachbegriffe, anonymisiert optional
und lässt das LLM zusammenfassen. Transkript und Zusammenfassung werden
verschlüsselt in PostgreSQL gespeichert, die Rohaufnahme gelöscht. Ist der
Audio-Download aktiv, landet eine verschlüsselte Kopie in Garage.

Verschlüsselt wird mit dem `ENCRYPTION_KEY` (Fernet, AES-128-CBC mit HMAC)
innerhalb der App. Weder Datenbank noch Objektspeicher sehen Klartext.

# Voraussetzungen

## Hardware

Die Spracherkennung profitiert stark von einer NVIDIA-Grafikkarte. Gemessen
wurde auf einer RTX 3060 mit 12 GB:

| Komponente | GPU-Speicher | Bemerkung |
|:-----------|:-----|:-------------------------------|
| Whisper large-v3-turbo (int8) | ca. 1,1–1,9 GB | Standardmodell |
| Parakeet TDT 0.6B v3 (FP32) | ca. 3,5 GB | nur für die Live-Vorschau |
| LLM (falls auf demselben Server) | je nach Modell | z. B. 4B-Modell quantisiert ca. 3 GB |

Richtwerte für einen Einzelserver mit Live-Vorschau:

- NVIDIA-GPU mit mindestens 8 GB, besser 12 GB oder mehr, wenn das LLM auf
  derselben Karte laufen soll,
- 8 CPU-Kerne, 16 GB RAM, 100 GB SSD (zzgl. Speicher für Audio-Downloads),
- NVIDIA-Treiber **ab Version 580** (das Parakeet-Image basiert auf CUDA 13).

**Ohne GPU** läuft openDox ebenfalls, aber langsamer. Die Live-Vorschau ist
dann nicht echtzeitfähig und sollte abgeschaltet werden; ein reiner
CPU-Betrieb eignet sich für Demonstrationen und kleine Installationen.

## Software

- Linux-Server (z. B. Ubuntu 24.04 LTS), x86_64 oder arm64,
- Docker Engine mit Compose-Plugin (`docker compose`),
- bei GPU: NVIDIA Container Toolkit (`nvidia-ctk`),
- Reverse Proxy (Apache mit `mod_proxy_wstunnel` oder nginx) und ein
  TLS-Zertifikat,
- `git` und `openssl`.

## Netzwerk

- Ein DNS-Name für openDox, z. B. `opendox.klinik.example`.
- **HTTPS ist Pflicht:** Browser geben das Mikrofon nur über `https://` frei.
- Der Reverse Proxy muss WebSockets durchreichen (Aufnahme und Live-Text).
- Ausgehende Verbindungen von der App zum LLM, ggf. zu LDAP/AD, zum Identity
  Provider und zum PII-Sanitizer.
- Beim ersten Start laden die Images ggf. Modelle nach. Ohne Internetzugang
  vorher Images mit eingebauten Modellen aus einer erreichbaren Registry
  bereitstellen.

# Installation mit Docker Compose

Dies ist der einfachste Weg für einen einzelnen Server. Für Produktion mit
Docker-Secrets siehe Kapitel *Produktion mit Docker Swarm*.

## Quellcode holen

```bash
git clone https://github.com/s2a-open-technologies/openDox.git /opt/opendox
cd /opt/opendox
git checkout v<Version>         # z. B. v0.10.7, empfohlen statt master
cp .env.example .env
chmod 600 .env
```

## GPU vorbereiten

Auf Servern mit NVIDIA-GPU einmalig:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Der letzte Befehl muss die Grafikkarte anzeigen.

## Konfiguration in `.env`

Die Datei `.env` steuert die gesamte Installation. Mindestens diese Werte
müssen gesetzt bzw. geändert werden:

```bash
# Pflicht: Schlüssel für die Verschlüsselung der Patientendaten
ENCRYPTION_KEY=<Ausgabe von: openssl rand -base64 32 | tr '+/' '-_'>

# Pflicht für Produktion: Signaturschlüssel für Anmelde-Tokens
SECRET_KEY=<Ausgabe von: openssl rand -hex 32>

# Datenbank-Passwort
SQL_PASS=<starkes Passwort>

# Zugangsschlüssel der Spracherkennungsdienste
WHISPER_API_KEY=<openssl rand -hex 24>
PARAKEET_API_KEY=<openssl rand -hex 24>

# Objektspeicher Garage
S3_ACCESS_KEY_ID=GK<openssl rand -hex 12>
S3_SECRET_ACCESS_KEY=<openssl rand -hex 32>
GARAGE_RPC_SECRET=<openssl rand -hex 32>
GARAGE_ADMIN_TOKEN=<openssl rand -hex 32>
```

> **Den `ENCRYPTION_KEY` sicher aufbewahren.** Ohne ihn lassen sich
> Transkripte, Zusammenfassungen und gespeicherte Audiodateien nicht mehr
> entschlüsseln, auch nicht aus einer Datensicherung. Ohne gültigen
> Schlüssel startet die App nicht.

Ohne `SECRET_KEY` erzeugt die App bei jedem Start einen zufälligen Schlüssel;
alle Benutzer werden dann bei jedem Neustart abgemeldet.

Die vollständige Liste der Variablen steht im Kapitel
*Konfigurationsreferenz* und kommentiert in `.env.example`.

## Starten

```bash
docker compose pull          # fertige Images laden
docker compose up -d
docker compose ps            # alle Dienste "running"/"healthy",
                             # garage-init "exited (0)"
```

Alternativ baut `docker compose up -d --build` die Images selbst aus dem
Quellcode; das dauert beim ersten Mal deutlich länger.

Beim ersten Start legt die App die Datenbank an (Migrationen laufen
automatisch vor dem Start) und richtet ein Administratorkonto ein. Whisper
und Parakeet laden beim ersten Start ihre Modelle; die erste Transkription
kann deshalb etwas dauern.

Die App ist danach auf dem Server unter `http://localhost:20000` erreichbar
(Port über `APP_PORT` änderbar). Von außen wird sie über den Reverse Proxy
angesprochen (nächstes Kapitel).

## Betrieb ohne GPU

Auf Servern ohne NVIDIA-Grafikkarte:

1. In `.env` setzen: `WHISPER_DEVICE=cpu` und `PARAKEET_DEVICE=cpu`.
2. In `docker-compose.yml` bei `whisper` und `parakeet` die Blöcke
   `deploy: resources: reservations: devices: …` entfernen, falls Docker
   beim Start einen fehlenden `nvidia`-Treiber meldet.
3. CPU-Images verwenden: entweder selbst bauen (`docker compose build`, die
   Variablen oben wählen die CPU-Variante) oder die Image-Varianten mit dem
   Präfix `cpu-` aus der Registry nehmen.
4. Nach der Installation in der Administration unter **Dienste → Whisper /
   ASR → Live** die Live-Transkription auf **Deaktiviert** stellen.

## Ersteinrichtung in der Weboberfläche

1. Mit Benutzer `admin`, Passwort `admin` anmelden und den Hinweis „Kein
   Medizinprodukt“ bestätigen.
2. **Sofort** unter **Administration → Benutzer** das Passwort von `admin`
   ändern.
3. Unter **Administration → Dienste → Whisper / ASR** bei **Live** und
   **Final** den **API Key** eintragen: `PARAKEET_API_KEY` bzw.
   `WHISPER_API_KEY` aus der `.env`. Eine neue Installation ist mit dem
   Demo-Schlüssel `loc-123` vorbelegt. Die Adressen `http://parakeet:5001/v1`
   und `http://whisper:5002/v1` sind bereits eingetragen.
4. Unter **Dienste → LLM** Adresse, Modell und ggf. Schlüssel des
   Sprachmodells eintragen und **Verbindung testen**.
5. Unter **System** prüfen, dass alle benötigten Dienste **Online** sind.
6. Ein Probediktat aufnehmen.

Alles Weitere (Anmeldung über LDAP/SSO, Kategorien, Wörterbücher) beschreibt
das *Administrationshandbuch*.

![Systemstatus nach der Installation](bilder/installation/02-systemstatus.png)

# Reverse Proxy und HTTPS

Die App spricht selbst nur HTTP. TLS übernimmt ein Reverse Proxy auf dem
Server. Beispielkonfigurationen liegen in `docs/examples/`:

- `apache-vhost.conf.example`
- `nginx-vhost.conf.example`

## Worauf es ankommt

- **WebSocket:** Der Pfad `/api/v1/records/ws/record` muss als WebSocket
  weitergeleitet werden. Bei Apache braucht es `mod_proxy_wstunnel`, und die
  WebSocket-Regel muss **vor** der allgemeinen Regel für `/` stehen. Sonst
  bricht die Live-Vorschau nach ein, zwei Sätzen ab.
- **Zeitlimits:** Aufnahmen können lange dauern. Das Leerlauf-Zeitlimit des
  WebSockets muss deutlich über den Standardwerten liegen (Beispiele: 3600 s).
- **Weitergeleitete Header:** `X-Forwarded-Proto` und `X-Forwarded-Host`
  setzen. openDox baut daraus u. a. die Redirect-Adresse für SSO.
- **Upload-Größe:** Für **Audio hochladen** die maximale Anfragegröße
  ausreichend groß wählen (nginx: `client_max_body_size`, z. B. `500m`).
- **Sicherheits-Header:** HSTS, `X-Frame-Options`, `X-Content-Type-Options`
  und `Referrer-Policy` setzt der Proxy (siehe Beispiele). Eine strenge
  Content-Security-Policy würde Aufnahme und Unterpfad-Betrieb stören und
  ist deshalb im Beispiel bewusst nicht enthalten.

Apache-Module aktivieren:

```bash
sudo a2enmod proxy proxy_http proxy_wstunnel ssl headers rewrite
```

## Vertrauenswürdige Proxys

openDox wertet die `X-Forwarded-*`-Header nur aus, wenn die Anfrage von einem
vertrauenswürdigen Proxy kommt. Ohne Einstellung gelten Loopback und das
Docker-Gateway als vertrauenswürdig; das passt, wenn der Proxy auf demselben
Server läuft. Läuft der Proxy auf einem anderen Rechner, dessen Adresse
eintragen:

```bash
TRUSTED_PROXY_IPS=10.0.1.20            # auch Bereiche: 10.0.1.0/24
```

Optional begrenzt `CORS_ALLOWED_ORIGINS` die erlaubten Ursprünge, z. B.
`https://opendox.klinik.example`. Da Weboberfläche und API über dieselbe
Adresse laufen, ist das meist nicht nötig.

## Betrieb unter einem Unterpfad

Soll openDox unter `https://klinik.example/opendox` statt unter einer eigenen
Domain laufen:

```bash
ROOT_PATH=/opendox
VITE_ROOT_PATH=/opendox
```

Der Proxy leitet dann `/opendox/…` unverändert (mit Präfix) an die App weiter.
Ein Neubau der Weboberfläche ist nicht nötig. Die SSO-Redirect-Adresse und
die Server-Adresse für den Desktop-Client enthalten den Unterpfad
automatisch.

## Interne Zertifizierungsstelle

Erreicht die App interne Dienste (LLM, Whisper, Sanitizer) über HTTPS mit
Zertifikaten einer eigenen CA, muss die App dieser CA vertrauen. Dafür
**beide** Variablen auf dieselbe CA-Datei setzen, da verschiedene
Bibliotheken jeweils nur eine davon lesen:

```bash
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

und das Verzeichnis `/etc/ssl/certs` des Hosts (mit installierter CA)
schreibgeschützt in den App-Container einbinden. In `docker-swarm.yml` ist
das bereits so eingerichtet. Ist nur eine der beiden Variablen gesetzt,
funktioniert z. B. das LLM, während Transkription und Health-Check mit
`CERTIFICATE_VERIFY_FAILED` scheitern.

# Produktion mit Docker Swarm

Für den Produktivbetrieb gibt es `docker-swarm.yml`. Unterschiede zu Docker
Compose:

- Zugangsdaten liegen als **Docker-Secrets** vor, nicht im Klartext in einer
  `.env`.
- Images werden nicht gebaut, sondern in einer festen Version aus einer
  Registry gezogen.
- GPU-Dienste werden über ein Knoten-Label auf den GPU-Server gelegt.

## Schritt 1: Swarm und GPU-Knoten

```bash
docker swarm init                          # einmalig auf dem Manager
```

Auf dem Knoten mit GPU einmalig (Swarm kennt keine GPU-Zuteilung, die GPU
wird deshalb für alle Container des Knotens freigegeben):

```bash
sudo nvidia-ctk runtime configure --runtime=docker --set-as-default
sudo systemctl restart docker
docker node update --label-add gpu=true <knoten-name>
```

## Schritt 2: Secrets anlegen

```bash
./create_docker_secrets.sh
```

Das Skript erzeugt alle benötigten Secrets mit Zufallswerten
(Datenbankpasswort, `SECRET_KEY`, `ENCRYPTION_KEY`, Whisper- und
Parakeet-Schlüssel, Garage-Zugangsdaten).

> Die erzeugten Werte werden **nur einmal** angezeigt. Docker gibt den Inhalt
> eines Secrets später nicht mehr heraus. Übertragen Sie mindestens
> `opendox_encryption_key`, `opendox_whisper_api_key` und
> `opendox_parakeet_api_key` sofort in Ihren Passwort-Safe.

Vorhandene Werte (etwa bei einer Migration von Docker Compose) übernehmen
Sie, indem Sie sie vor dem Aufruf als Umgebungsvariable setzen, z. B.
`ENCRYPTION_KEY=<alter Schlüssel> ./create_docker_secrets.sh`. Bereits
existierende Secrets lässt das Skript unverändert.

## Schritt 3: Version und Registry festlegen

```bash
export OPENDOX_VERSION=0.10.7                  # gewünschte Version
export OPENDOX_REGISTRY=ghcr.io/<owner>        # nur falls abweichend
```

Alle vier Images (`opendox`, `opendox-whisper`, `opendox-parakeet`,
`opendox-garage-init`) müssen in dieser Version in der Registry liegen und
für alle Knoten abrufbar sein. Bei einer privaten Registry vorher
`docker login` ausführen und beim Deploy `--with-registry-auth` angeben.

Nicht geheime Einstellungen (`APP_PORT`, `ROOT_PATH`, `TRUSTED_PROXY_IPS`,
`WHISPER_MODEL` …) werden ebenfalls als Umgebungsvariablen in der Shell
gesetzt, bevor `docker stack deploy` aufgerufen wird.

## Schritt 4: Deployen

```bash
docker stack deploy -c docker-swarm.yml opendox
docker stack services opendox
```

Swarm wartet nicht auf Abhängigkeiten; Dienste, die zu früh starten, werden
automatisch neu gestartet, bis Datenbank und Speicher bereit sind. Nach ein
bis zwei Minuten sollten alle Dienste `1/1` zeigen (`garage-init` `0/1`,
nachdem es erfolgreich durchgelaufen ist).

Danach die *Ersteinrichtung in der Weboberfläche* wie bei Docker Compose
durchführen. Als API-Schlüssel für Whisper und Parakeet die Werte der
Secrets `opendox_whisper_api_key` und `opendox_parakeet_api_key` eintragen.

# Konfigurationsreferenz

Jede Variable kann statt direkt auch aus einer Datei gelesen werden: Endung
`_FILE` anhängen, z. B. `SECRET_KEY_FILE=/run/secrets/secret_key`.

## App

| Variable | Bedeutung | Standard |
|:----------------------|:------------------------|:----------|
| `ENCRYPTION_KEY` | Fernet-Schlüssel für Patientendaten. **Pflicht.** | – |
| `SECRET_KEY` | Signaturschlüssel für Anmelde-Tokens | zufällig je Start |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Gültigkeit des Zugangstokens | 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Gültigkeit des Erneuerungstokens | 7 |
| `APP_PORT` | Host-Port der App | 20000 |
| `ROOT_PATH` / `VITE_ROOT_PATH` | Unterpfad, z. B. `/opendox` | leer |
| `TRUSTED_PROXY_IPS` | Proxys, deren `X-Forwarded-*`-Header gelten (IPs oder CIDR) | Loopback + Docker-Gateway |
| `CORS_ALLOWED_ORIGINS` | Erlaubte Ursprünge, durch Kommas getrennt | alle (mit Warnung im Log) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `FAILED_AUDIO_RETENTION_DAYS` | Tage, bis fehlgeschlagene Aufnahmen in den Objektspeicher ausgelagert werden | 3 |
| `AUDIT_RETENTION_DAYS` | Tage, die Einträge im Audit-Log aufbewahrt werden (`0` = unbegrenzt) | 365 |
| `SETTINGS_CACHE_TTL_S` | Sekunden, bis Einstellungsänderungen andere Instanzen erreichen | 30 |
| `CLIENT_SERVER_URL` | Server-Adresse für die `settings.json` des Desktop-Clients | aus der Anfrage abgeleitet |
| `CLIENT_DOWNLOAD_BASE_URL` | Quelle der Client-Installer | neuestes GitHub-Release |

## Datenbank und Redis

| Variable | Bedeutung | Standard |
|:----------------------|:------------------------|:----------|
| `SQL_USER`, `SQL_PASS`, `SQL_HOST`, `SQL_PORT`, `SQL_DB` | PostgreSQL-Verbindung; `SQL_HOST` ist in Compose/Swarm fest `postgres` | `postgres`, `postgres`, `localhost`, 5432, `opendox` |
| `DATABASE_URI` | Vollständige Verbindungs-URI, überschreibt die Einzelwerte | leer |
| `REDIS_URL` | Redis für Sitzungen; in Compose/Swarm fest `redis://redis:6379/0` | leer = im Speicher |

## Spracherkennung

| Variable | Bedeutung | Standard |
|:-----------------------------|:---------------------|:--------|
| `WHISPER_MODEL` | Whisper-Modell | `large-v3-turbo` |
| `WHISPER_DEVICE` | `cuda` oder `cpu` | `cuda` |
| `WHISPER_COMPUTE_TYPE` | Rechengenauigkeit | `int8` |
| `WHISPER_API_KEY` | Schlüssel des Whisper-Dienstes | `loc-123` |
| `WHISPER_MAX_CONCURRENT_TRANSCRIPTIONS` | Gleichzeitige Transkriptionen | 4 |
| `PARAKEET_DEVICE` | Image-Variante beim Bauen: `gpu` oder `cpu` | `gpu` |
| `PARAKEET_API_KEY` | Schlüssel des Parakeet-Dienstes; leer = ohne Schutz | leer |
| `PARAKEET_MAX_CONCURRENT_DECODES` | Gleichzeitige Dekodierungen; bei großen GPUs und vielen gleichzeitigen Sprechern erhöhen | 2 |
| `PARAKEET_PORT` | Veröffentlichter Host-Port von Parakeet | 5001 |
| `PARAKEET_ROOT_PATH` | Unterpfad, falls Parakeet über einen separaten Proxy erreichbar ist | leer |

Die Adressen der Dienste werden in der Weboberfläche gepflegt, nicht hier.

## Objektspeicher

| Variable | Bedeutung | Standard (Compose) |
|:----------------------|:------------------------|:----------|
| `S3_ENDPOINT_URL` | Adresse des S3-Dienstes | `http://garage:3900` |
| `S3_BUCKET` | Bucket | `opendox-audio` |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Zugangsdaten | Demo-Werte, ändern |
| `S3_REGION` | Region | `garage` |
| `GARAGE_RPC_SECRET`, `GARAGE_ADMIN_TOKEN` | Nur für den mitgelieferten Garage-Dienst | Demo-Werte, ändern |

Statt Garage kann jeder S3-kompatible Speicher verwendet werden. Die Daten
werden vor dem Hochladen verschlüsselt; der Speicheranbieter sieht keinen
Klartext.

# Betrieb

## Protokolle

```bash
docker compose logs -f app          # Swarm: docker service logs -f opendox_app
docker compose logs -f whisper
docker compose logs --since 1h parakeet
```

Bei eingeschalteter Fachbegriff-Korrektur werden ersetzte Einzelwörter
protokolliert. Berücksichtigen Sie das bei der Aufbewahrung der Protokolle.

## Zustand prüfen

- `https://<host>/api/version` liefert die laufende Version.
- In der Weboberfläche unter **Administration → System** steht der Status
  aller Dienste.
- `docker compose ps` bzw. `docker stack ps opendox` zeigt
  Container-Zustand und Neustarts.

## Datensicherung

Zu sichern sind:

| Was | Wie | Häufigkeit |
|:-----------|:-------------------------------|:-----------|
| Datenbank | `pg_dump` (siehe unten) | täglich |
| `ENCRYPTION_KEY` | einmalig im Passwort-Safe, getrennt von den Daten | bei Änderung |
| Objektspeicher (Audio) | Volume `opendox-garage-data` oder Replikation des S3-Speichers | täglich, falls Audio-Download aktiv |
| `.env`, angepasste Compose-Dateien | Dateisicherung, enthält Zugangsdaten | bei Änderung |
| Einstellungen | zusätzlich **Administration → Backup** | nach Änderungen |

Datenbank sichern (Docker Compose):

```bash
docker compose exec -T postgres \
  pg_dump -U postgres -Fc opendox > opendox-$(date +%F).dump
```

Wiederherstellen in eine leere Datenbank:

```bash
docker compose stop app
docker compose exec -T postgres \
  pg_restore -U postgres -d opendox --clean --if-exists < opendox-2026-10-23.dump
docker compose start app
```

> Eine Sicherung ist nur zusammen mit dem passenden `ENCRYPTION_KEY`
> brauchbar. Testen Sie die Wiederherstellung regelmäßig auf einem
> getrennten System.

Die Volumes `opendox-redis-data` (laufende Sitzungen) und
`opendox-whisper-data` (heruntergeladene Modelle) müssen nicht gesichert
werden.

## Update

1. Änderungen im `CHANGELOG.md` der neuen Version lesen.
2. **Datenbank sichern** (siehe oben). Neue Versionen können das Schema
   ändern; ein Zurückrollen setzt es nicht zurück.
3. Update einspielen:

   Docker Compose:

   ```bash
   git fetch --tags && git checkout v<Version>
   docker compose pull
   docker compose up -d
   ```

   Docker Swarm:

   ```bash
   export OPENDOX_VERSION=<Version>
   docker stack deploy -c docker-swarm.yml opendox
   ```

4. Prüfen: `/api/version` zeigt die neue Version, unter **System** sind alle
   Dienste online.

Datenbank-Migrationen laufen beim Start der App automatisch.

## Zurückrollen

```bash
export OPENDOX_VERSION=<alte Version>
docker stack deploy -c docker-swarm.yml opendox
```

Hatte die neuere Version eine Datenbank-Migration, läuft die alte App gegen
das neue Schema. Im Zweifel die vor dem Update gesicherte Datenbank
zurückspielen.

## Verschlüsselungsschlüssel wechseln

Der `ENCRYPTION_KEY` lässt sich wechseln, etwa wenn er kompromittiert sein
könnte. Die App verschlüsselt dabei beim Start alle Daten vom alten auf den
neuen Schlüssel um.

**Docker Compose:**

1. Datenbank sichern.
2. In `docker-compose.yml` beim Dienst `app` unter `environment` ergänzen:
   `ENCRYPTION_KEY_PREVIOUS: ${ENCRYPTION_KEY_PREVIOUS}`.
3. In `.env` den bisherigen Schlüssel als `ENCRYPTION_KEY_PREVIOUS` und den
   neuen als `ENCRYPTION_KEY` eintragen.
4. `docker compose up -d app` und im Protokoll die erfolgreiche Umstellung
   prüfen.
5. `ENCRYPTION_KEY_PREVIOUS` wieder entfernen und neu starten.

**Docker Swarm:** Das Vorgehen mit dem Overlay `docker-swarm.rotation.yml`
steht im Kopfkommentar dieser Datei. Kurzfassung: Secret
`opendox_encryption_key_previous` mit dem alten Schlüssel anlegen, ein neues
Secret für den neuen Schlüssel anlegen und in `docker-swarm.yml` eintragen,
mit `-c docker-swarm.yml -c docker-swarm.rotation.yml` deployen, Erfolg im
Log prüfen, danach ohne Overlay deployen und das alte Secret löschen.

Den alten Schlüssel nicht länger als nötig aufbewahren; Datensicherungen von
vor dem Wechsel brauchen allerdings weiterhin den alten Schlüssel.

## Aufbewahrung und Löschung

| Daten | Ort | Löschung |
|:-----------|:-------------------------------|:-------------------------------|
| Rohaufnahme (PCM/WAV) | Volume `app-chunks` | nach erfolgreicher Verarbeitung sofort; abgebrochene Aufnahmen nach 30 Minuten Inaktivität |
| Rohaufnahme bei Fehler | `app-chunks/failed` bzw. Objektspeicher | nach erfolgreichem erneuten Versuch; sonst bleibt sie bis dahin erhalten |
| Audio-Download | Objektspeicher, verschlüsselt | beim Löschen der Aufnahme durch den Benutzer |
| Transkript, Zusammenfassung | Datenbank, verschlüsselt | beim Löschen der Aufnahme durch den Benutzer |

openDox löscht Aufnahmen nicht nach einer Frist. Die automatische
Archivierung verschiebt nur. Legen Sie Löschfristen organisatorisch fest.

## Skalierung

Eine Instanz der App reicht für viele gleichzeitige Diktate; Engpass ist in
der Regel die GPU. Für sehr viele gleichzeitige Sprecher lassen sich in
`docker-swarm.yml` mehrere App-Instanzen betreiben (`deploy.replicas`).
Solange alle Instanzen auf einem Knoten laufen, ist am Reverse Proxy nichts
zu ändern. Für mehrere Knoten ist ein Routing nach Sitzung nötig; Details in
`docs/scaling.md`.

Bei vielen gleichzeitigen Diktaten zuerst `PARAKEET_MAX_CONCURRENT_DECODES`
und `WHISPER_MAX_CONCURRENT_TRANSCRIPTIONS` an die GPU anpassen und unter
Last testen.

# Sicherheits-Checkliste

Vor der Freigabe für den Produktivbetrieb:

- [ ] `ENCRYPTION_KEY` gesetzt und getrennt von den Daten gesichert.
- [ ] `SECRET_KEY` gesetzt.
- [ ] Datenbank-, Garage- und S3-Zugangsdaten nicht mehr auf den Demo-Werten.
- [ ] `WHISPER_API_KEY` und `PARAKEET_API_KEY` gesetzt und in der
      Administration eingetragen.
- [ ] Passwort des Kontos `admin` geändert oder Konto deaktiviert.
- [ ] Zugriff nur über HTTPS; Port `APP_PORT` und `PARAKEET_PORT` von außen
      nicht erreichbar (Firewall).
- [ ] Sicherheits-Header am Reverse Proxy gesetzt.
- [ ] Erlaubte Gruppen für LDAP/SSO eng gefasst.
- [ ] Datensicherung eingerichtet und Wiederherstellung getestet.
- [ ] LLM und ggf. PII-Sanitizer laufen in einer Umgebung, die für
      Patientendaten zugelassen ist.
- [ ] Löschfristen und Audio-Aufbewahrung festgelegt und dokumentiert.

Schwachstellen in openDox melden Sie bitte wie in `SECURITY.md` beschrieben.

# Fehlersuche

**Die App startet nicht, im Log steht „EncryptionKeyError“.**
`ENCRYPTION_KEY` fehlt oder ist kein gültiger Fernet-Schlüssel (44 Zeichen,
URL-sicheres Base64). Neu erzeugen nur bei einer **neuen** Installation; bei
einer bestehenden den gesicherten Schlüssel eintragen.

**Nach jedem Neustart sind alle Benutzer abgemeldet.**
`SECRET_KEY` ist nicht gesetzt.

**Die Seite lädt, aber das Mikrofon wird nicht freigegeben.**
openDox muss über `https://` aufgerufen werden.

**Live-Vorschau bricht nach wenigen Sätzen ab.**
WebSocket-Weiterleitung am Proxy prüfen: bei Apache `mod_proxy_wstunnel`
aktiv und die Regel für `/api/v1/records/ws/record` vor der Regel für `/`;
Leerlauf-Zeitlimit erhöhen.

**Live-Vorschau hinkt stark hinterher.**
Parakeet läuft auf der CPU. GPU-Zugriff prüfen
(`docker compose exec parakeet nvidia-smi`, Treiber ab 580) oder die
Live-Transkription abschalten.

**„Transkription“ oder „Live“ unter System nicht erreichbar.**
`docker compose ps` und Protokolle der Dienste prüfen. Häufige Ursache: Der
API-Key in der Administration stimmt nicht mit `WHISPER_API_KEY` bzw.
`PARAKEET_API_KEY` überein.

**„Objekt-Speicher (S3)“ nicht erreichbar.**
Prüfen, ob `garage-init` erfolgreich beendet wurde
(`docker compose logs garage-init`) und die S3-Zugangsdaten in App und
`garage-init` übereinstimmen. Unter Swarm muss Garage die Secret-Dateien mit
Modus 0600 erhalten (in `docker-swarm.yml` bereits gesetzt).

**Verbindungen zu internen Diensten scheitern mit `CERTIFICATE_VERIFY_FAILED`.**
Siehe *Interne Zertifizierungsstelle*: `SSL_CERT_FILE` und
`REQUESTS_CA_BUNDLE` setzen und das Zertifikatsverzeichnis einbinden.

**SSO leitet auf eine falsche Adresse (http statt https, falscher Host).**
Der Proxy muss `X-Forwarded-Proto` und `X-Forwarded-Host` setzen; läuft er
auf einem anderen Rechner, dessen Adresse in `TRUSTED_PROXY_IPS`
eintragen.

**Unter `/api/health` kommt eine HTML-Seite.**
Diese Adresse existiert nicht. Für Überwachung `/api/version` verwenden.

# Impressum und Lizenz

openDox wird von der S2A Open Technologies gGmbH entwickelt und als freie
Software unter der GNU Affero General Public License, Version 3 oder später
(AGPL-3.0-or-later), veröffentlicht. Die Software wird ohne Gewährleistung
bereitgestellt; Einzelheiten regelt die Lizenz. Wer openDox verändert und
über ein Netzwerk bereitstellt, muss den Nutzern den geänderten Quellcode
zugänglich machen (§ 13 AGPL).

Für den Betrieb der jeweiligen Installation, einschließlich Datenschutz und
der Einhaltung medizinrechtlicher Vorschriften, ist die betreibende
Einrichtung verantwortlich.
