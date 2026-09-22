# Audit-Checkliste: openDox (Selbstauskunft)

> Simuliert, wie ein Auditor openDox tatsächlich abklopfen würde. Jede
> Zeile ist mit einer konkreten Fundstelle belegt — keine Vermutungen.
> Status: ✅ implementiert/vorhanden · ⚠️ teilweise/mit Einschränkung ·
> ❌ nicht implementiert/nicht vorhanden. Stand: Recherche vom 2026-09-18,
> aktualisiert am 2026-09-22 (Rate-Limiting `/login` implementiert,
> Frontend-Testabdeckung ausgebaut); vor Wiederverwendung gegen den dann
> aktuellen Code gegenprüfen — Status kann sich ändern.

## Security

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| Passwort-Hashing | ✅ | `User.hashed_password`, bcrypt, 12 Runden (`docs/SECURITY.md`) | Salt automatisch pro Passwort |
| JWT-Signierung ohne unsicheren Fallback | ✅ | `backend/components/security/hashing.py`, `SECRET_KEY` — kein Hardcoded-Default, zufälliger Key + `logger.critical()` falls unset | Invalidiert alle Sessions bei jedem Neustart ohne festen `SECRET_KEY` |
| Feldverschlüsselung sensibler Daten | ✅ (bei gesetztem Key) | `backend/components/security/field_encryption.py`, Fernet, `EncryptedString`-Spaltentyp | `record.content/summarize/pii_mapping/title`, `LdapSettingsModel.bind_user_password`, `OidcSettingsModel.client_secret` |
| Verschlüsselung fällt bei fehlendem Key still auf Klartext zurück | ⚠️ | `field_encryption.py` — nur geloggte Warnung, kein Hard-Fail | Audit-Risiko: Betreiber merkt es ggf. nicht |
| `decrypt()` fällt bei `InvalidToken` still auf Klartext zurück | ⚠️ | `field_encryption.py` | Migrations-Komfort, maskiert aber auch Korruption/Falscher-Key-Fehler |
| Key-Rotation implementiert (nicht nur dokumentiert) | ✅ | `backend/components/security/key_rotation.py`, `docker-swarm.rotation.yml`, `EncryptionKeyState`-Tabelle | Idempotent, resumable nach Unterbrechung |
| Secrets nie im Repo | ✅ | `.env` `.gitignore`d, `git log --all -- .env` leer; nur `.env.example` getrackt | `_FILE`-Konvention in `env.py:env_or_file()` |
| RBAC mit mehreren Rollen | ✅ | `backend/components/models/user_model.py:27`, `ROLES = ("admin", "moderator", "demo_viewer", "user")` | Durchgesetzt via FastAPI-Dependencies in `auth_routes.py`/`settings_routes.py`/`record.py` |
| LDAP-Filter-Injection-Schutz | ✅ | `ldap.py`, `ldap3.utils.conv.escape_filter_chars()` vor Filteraufbau | |
| Leeres-Passwort-Bind-Bypass verhindert | ✅ | `ldap.py`, Empty-Password-Check vor Bind (RFC-4513-Guard) | |
| CSRF-Schutz | ✅ (strukturell) | Bearer-Token statt Cookie-Auth für API — klassischer CSRF-Vektor entfällt (`docs/SECURITY.md`) | Einzige Cookie: signierter OIDC-`state` |
| CORS-Konfiguration | ⚠️ | `CORS_ALLOWED_ORIGINS`, fällt bei unset auf `*` zurück (mit Logwarnung) | Muss vom Betreiber gesetzt werden |
| Rate-Limiting / Brute-Force-Schutz | ✅ (app-seitig, `/login`) | `backend/components/services/rate_limiter.py` — Sliding-Window-Limiter (5 Req/60s per Client-IP, `X-Forwarded-For`-bewusst), HTTP 429 bei Überschreitung; aufgerufen in `auth_routes.py:login()` vor jedem Login-Versuch; Tests: `tests/auth/test_rate_limiter.py` (8 Unit- + 2 Integrationstests) | Nur Login-Endpoint; andere Endpoints weiterhin über Reverse Proxy/Gateway zu schützen. In-Memory (per Prozess) — bei Multi-Instance-Deployments wirkt das Limit pro Instanz, Redis-basierte Ablage wäre der nächste Ausbauschritt |
| Multi-Faktor-Authentifizierung | ❌ | `docs/SECURITY.md`: "not implemented anywhere in this app" | Weder lokal noch LDAP/OIDC-seitig |
| Security-Response-Header (HSTS, X-Frame-Options etc.) | ❌ (app-seitig) | `docs/SECURITY.md`: nur `Permissions-Policy` in `backend/run.py`, Rest muss Reverse Proxy liefern | |
| Security-relevante Tests vorhanden | ✅ | `tests/security/test_field_encryption.py`, `tests/auth/test_rbac.py`, `tests/auth/test_oidc_routes.py`, `tests/auth/test_rate_limiter.py`, `tests/services/test_ldap_service.py`, `tests/services/test_oidc_service.py`, `tests/services/test_sanitizing_service.py` | |
| Vulnerability-Disclosure-Prozess | ✅ | `docs/SECURITY.md` — E-Mail-Kontakt, 48h-Antwortzeit, 90-Tage-Policy | Dedizierte `security@`-Adresse laut Doku noch offen |
| Container läuft als Root | ❌ | `docs/SECURITY.md`: aktuelles `Dockerfile` implementiert kein `USER`-Downgrade | Dokumentiert als bekannte Lücke |
| DB/Redis nicht öffentlich erreichbar | ✅ | `docker-compose.yml`/`docker-swarm.yml`: keine `ports:`-Mappings für `postgres`/`redis` | |
| Redis-Authentifizierung | ❌ | Kein `requirepass` in beiden Compose-Dateien | Nur akzeptabel, weil nicht extern exponiert |

## Datenschutz / DSGVO

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| Datenflussdiagramm / ROPA-Ausgangspunkt | ✅ | [`docs/data-mapping.md`](data-mapping.md) inkl. Mermaid-Flowchart | Explizit als Startpunkt für Art. 30 DSGVO deklariert |
| Art.-32-Maßnahmentabelle | ✅ | `docs/SECURITY.md` "Technical Measures (Article 32)" | Ehrlich mit ⚠️ markierte Zeilen (z. B. Verschlüsselung in Transit) |
| PII-Pseudonymisierung (EntityGuard) | ✅ (optional aktivierbar) | [`docs/pii.md`](pii.md) | Fail-closed bei nicht erreichbarem Sanitizer |
| Eindeutigkeit der PII-Tokens als Kollisionsrisiko dokumentiert | ✅ | `docs/pii.md`: Tokens müssen pro Vorkommen eindeutig sein, sonst Mapping-Kollision | Verantwortung liegt beim Sanitizer-Dienst |
| Datenminimierung bei Rohaudio | ⚠️ | `data-mapping.md`: PCM/WAV wird nach *erfolgreicher* Verarbeitung gelöscht, bei Fehlschlag unverschlüsselt in `chunks/failed/` ohne automatisches Ablaufdatum | Bewusster Trade-off (Retry-Fähigkeit vs. Minimierung) |
| Recht auf Berichtigung | ✅ | `PUT /record/{id}`, `PUT /users/{id}` (`docs/SECURITY.md`) | |
| Recht auf Löschung | ⚠️ | `DELETE /record/{id}` — Hard-Delete, aber kein Bulk-"alles zu Patient X löschen" | |
| Recht auf Auskunft | ❌ | `docs/SECURITY.md`: kein Self-Service-Export-Endpoint | Nur manuelle DB-Abfrage |
| Recht auf Datenübertragbarkeit | ❌ | `docs/SECURITY.md`: kein JSON/strukturierter Export | Gleiche Lücke wie Auskunftsrecht |
| Widerspruchsrecht (Opt-out LLM-Verarbeitung) | ❌ | `docs/SECURITY.md`: kein Consent-Flag pro Datensatz/Patient | LLM-Schritt läuft immer, wenn Kategorie konfiguriert ist |
| Verschlüsselung in Transit zu externen Endpunkten erzwungen | ❌ (nicht erzwungen) | `data-mapping.md`: hängt von eingetragener URL ab (`https://`/`ldaps://`), Anwendung erzwingt nichts | Betreiberverantwortung |
| Externe Auftragsverarbeiter dokumentiert | ✅ | `data-mapping.md` "Externe Stellen / mögliche Auftragsverarbeiter" | Unterscheidet default-self-hosted vs. betreiberkonfiguriert |
| Aufbewahrungsfristen dokumentiert | ⚠️ | `data-mapping.md` "Aufbewahrung & Löschung" | Transkript/Summary ohne automatisches Ablaufdatum — manuelle Löschung nötig |
| "Bekannte Lücken" explizit benannt | ✅ | `data-mapping.md` eigener Abschnitt "Bekannte Lücken" | Vorbildlich für Auditierbarkeit — Lücken werden nicht versteckt |

## Lizenz / Compliance

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| Root-`LICENSE`-Datei vorhanden, konsistent und vollständig | ✅ | `LICENSE` (voller AGPL-3.0-Text, 661 Zeilen), `LICENSES/AGPL-3.0-or-later.txt` (REUSE-Pfad, identischer Text), `pyproject.toml`: `license = {text = "AGPL-3.0-or-later"}` | War vorher unvollständig (nur der "How to Apply"-Anhang, 33 Zeilen) — beim Beheben der SPDX-Header mit aufgefallen und korrigiert |
| Copyright-Angabe konsistent | ✅ | `LICENSE`: "Copyright (C) 2025 openDox Contributors" / "Christopher Abanilla"; `frontend/package.json`: `"license": "AGPL-3.0-or-later"` | War vorher inkonsistent — `frontend/package.json` deklarierte fälschlich `"Apache-2.0"`, ebenfalls beim Beheben der SPDX-Header entdeckt und korrigiert |
| Datei-Lizenzheader | ✅ | Alle Quelldateien (`.py`/`.ts`/`.tsx`/`.css`/Dockerfiles) tragen den vollständigen AGPL-Header; `scripts/add_spdx_headers.py` hält das mechanisch nach | Volltext-Header **plus** SPDX-Kurzform-Tags (siehe unten) |
| Lizenz-Header auch in Dockerfiles | ✅ | gleiche Header-Form als Kommentarblock, jetzt in allen 4 Dockerfiles (vorher nur im Root-`Dockerfile`) | |
| `AUTHORS`-Datei | ✅ | listet einen "Primary Developer" | Contributions-Abschnitt aspirational, keine tatsächlichen externen Contributor |
| Dependency-Lockfiles vorhanden | ✅ | `pyproject.toml` (75 Einträge) + `uv.lock`; `frontend/package.json` (75 Pakete) + `package-lock.json` | Reproduzierbare Installationen |
| Third-Party-Notices-Datei | ✅ | [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) (Root), generiert via `python scripts/check_licenses.py --write-notices` | 90 Backend- + 368 Frontend-Pakete mit Name/Version/Lizenz; regenerierbar, nicht von Hand gepflegt (gleiches Muster wie `scripts/bump_version.py`) |
| Automatisierte Lizenzkompatibilitäts-Prüfung | ✅ | `scripts/check_licenses.py` (nutzt `pip-licenses` + `license-checker-rseidelsohn`, Allowlist AGPL-3.0-kompatibler Lizenzen) | Manuell auszuführen, nicht CI-erzwungen (kein CI im Repo) — konsistent mit `safety check`/`npm audit` in `docs/CONTRIBUTING.md`. Aktuell 3 Pakete zur manuellen Prüfung markiert (2 davon nur eigene Dev-Tools: `reuse`, `python-debian`) |
| SPDX-konforme Kurzform-Header | ✅ | `SPDX-FileCopyrightText`/`SPDX-License-Identifier`-Zeilen in allen Quelldateien; `REUSE.toml` deckt Tests, Migrationen, Lockfiles, Config/Doku-Dateien pauschal ab | |
| REUSE-Spec-Konformität | ✅ | `reuse lint` (REUSE Tool 6.2.0) läuft grün: 265/265 Dateien mit Copyright- und Lizenzinformation | Direkter Nachweis, nicht nur Behauptung — Tool ist als Dev-Dependency in `pyproject.toml` |

## Projekt-Health / Governance

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| CI/CD-Pipeline | ❌ | Kein `.github/`-Verzeichnis im gesamten Repo | Kein automatisierter Test-/Lint-/Security-Lauf bei PRs |
| Dependency-Scanning automatisiert (Dependabot o. ä.) | ❌ | Kein Dependabot-Config, kein CI | `safety check`/`npm audit` nur als manuelle Empfehlung in `docs/CONTRIBUTING.md`/`docs/SECURITY.md` dokumentiert |
| `CONTRIBUTING.md` | ⚠️ | Existiert nur unter `docs/CONTRIBUTING.md`, nicht an der Root (GitHub erkennt Root-Ebene automatisch) | |
| `CODE_OF_CONDUCT.md` | ❌ | Nicht vorhanden | |
| `SECURITY.md` an Standard-Ort | ⚠️ | Liegt unter `docs/SECURITY.md` statt Root — GitHub's automatische Security-Tab-Erkennung greift nur bei Root- oder `.github/`-Pfad | Inhaltlich sehr umfangreich, nur der Pfad ist unüblich |
| `CHANGELOG.md` | ❌ | Nicht vorhanden | Änderungen nur über `git log` nachvollziehbar |
| Issue-/PR-Templates | ❌ | Kein `.github/ISSUE_TEMPLATE`/`PULL_REQUEST_TEMPLATE.md` | |
| Versionierungs-Tooling vorhanden | ✅ | `scripts/bump_version.py`, synct `pyproject.toml` + `frontend/package.json` + Lockfile | |
| Versionierung tatsächlich genutzt (Git-Tags) | ❌ | `git tag` → 0 Ergebnisse trotz `--commit`-Flag im Tooling | Releases nicht an Commits festgemacht |
| Testabdeckung Backend | ✅ | 19 Testdateien unter `tests/` (174 Tests, alle grün), u. a. Security/Auth/Services inkl. Rate-Limiter | pytest, `tests/conftest.py` mit geteilten Fixtures |
| Testabdeckung Frontend | ✅ | 31 `.test.tsx`/`.test.ts`-Dateien unter `frontend/src/**/__tests__/` (209 Tests grün, 1 skipped) | Colocated-Konvention (Vitest); Skip ist jsdom-Bug in Radix-Dialog-Fokus-Trap, Funktionalität manuell verifiziert |
| Commit-/Maintainer-Aktivität | ✅ (aktiv) | 112 Commits, aktuelle Feature-Cadence (LLM-Sampling-Parameter, Concurrency-Limits, CORS/Security) | Projekt ist nicht verwaist |
| Bus-Faktor | ❌ (=1) | Alle 112 Commits stammen von einer Person unter vier Git-Identitäten (`crizz`, `Daemolition` ×2, `christopher.abanilla`) | Kein zweiter Maintainer, kein dokumentierter Nachfolgeprozess |
| Docker-Reproduzierbarkeit | ⚠️ | Dockerfiles für alle 4 Services vorhanden; Base-Images gemischt gepinnt (`dxflrs/garage:v1.0.1` exakt vs. `node:22-slim`/`python:3.12-slim` mit floatendem Minor/Patch) | Keine Digest-Pins (`@sha256:...`) — Builds nicht bit-identisch reproduzierbar |
| Health-Check-Endpoint für Betrieb | ✅ | `GET /api/v1/settings/services-health/`, prüft Postgres/Redis/Whisper/Parakeet/EntityGuard/S3/Encryption-Key-Status | |

## Zusammenfassung für den Vortrag

**Stärken, die openDox als Beispiel für gute Auditierbarkeit tragen**:
durchgängige Verschlüsselungsarchitektur, sauberes Secrets-Handling,
implementierte (nicht nur beschriebene) Key-Rotation, umfangreiche und vor
allem *ehrliche* Sicherheits-/Datenschutzdokumentation mit explizit
markierten Lücken, vollständige Lizenz-Header.

**Lücken, die die Gegenthese im Vortrag liefern** ("auch ein
security-fokussiertes Projekt hat blinde Flecken"): kein Audit-Log,
keine CI/CD-gestützte Dependency-Prüfung, Bus-Faktor 1,
ungenutzte Versionierung, fehlende Access-/Portability-Rechte nach DSGVO.

Beide Listen zusammen sind der eigentliche Beweis für die These des
Vortrags: **Auditierbarkeit zeigt sich nicht daran, keine Lücken zu haben,
sondern daran, dass man sie findet, weil sie dokumentiert sind.**
