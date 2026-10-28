# Audit-Checkliste: openDox (Selbstauskunft)

> Simuliert, wie ein Auditor openDox tatsächlich abklopfen würde. Jede
> Zeile ist mit einer konkreten Fundstelle belegt — keine Vermutungen.
> Status: ✅ implementiert/vorhanden · ⚠️ teilweise/mit Einschränkung ·
> ❌ nicht implementiert/nicht vorhanden. Stand: Recherche vom 2026-09-18,
> aktualisiert am 2026-09-22 (Rate-Limiting `/login` implementiert,
> Frontend-Testabdeckung ausgebaut, Governance-Lücken geschlossen: CI/CD,
> Dependabot, CHANGELOG, CODE_OF_CONDUCT, Templates, Root-Symlinks,
> Git-Tag `v0.1.0`, Commit-Identitäten vereinheitlicht), aktualisiert am
> 2026-09-23 (alle 4 Container laufen jetzt als non-root `appuser`), am
> 2026-09-23 (freiwillige CycloneDX-SBOMs pro Image im Publish-Workflow);
> aktualisiert am 2026-10-08 (Settings-Endpunkte geben Geheimnisse nur noch an
> Admins, Fehlschlag-Audio-Archivierung, Client-Richtlinie, i18n, Tests/REUSE neu
> gemessen);
> vor Wiederverwendung gegen den dann aktuellen Code gegenprüfen — Status kann
> sich ändern.

## Security

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| Passwort-Hashing | ✅ | `User.hashed_password`, bcrypt, 12 Runden (`SECURITY.md`) | Salt automatisch pro Passwort |
| JWT-Signierung ohne unsicheren Fallback | ✅ | `backend/components/security/hashing.py`, `SECRET_KEY` — kein Hardcoded-Default, zufälliger Key + `logger.critical()` falls unset | Invalidiert alle Sessions bei jedem Neustart ohne festen `SECRET_KEY` |
| Feldverschlüsselung sensibler Daten | ✅ | `backend/components/security/field_encryption.py`, Fernet, `EncryptedString`-Spaltentyp | `record.content/summarize/pii_mapping/title`, `LdapSettingsModel.bind_user_password`, `OidcSettingsModel.client_secret` |
| Verschlüsselung ohne Key ausgeschlossen | ✅ | `field_encryption.py:_load_key()` — App startet nicht ohne gültigen `ENCRYPTION_KEY` (`EncryptionKeyError`); Tests: `tests/security/test_field_encryption.py` | Vorher nur Log-Warnung und Klartext-Betrieb. Altzeilen im Klartext bleiben lesbar und werden nicht nachverschlüsselt |
| `decrypt()` fällt bei `InvalidToken` still auf Klartext zurück | ⚠️ | `field_encryption.py` | Migrations-Komfort, maskiert aber auch Korruption/Falscher-Key-Fehler |
| Key-Rotation implementiert (nicht nur dokumentiert) | ✅ | `backend/components/security/key_rotation.py`, `docker-swarm.rotation.yml`, `EncryptionKeyState`-Tabelle | Idempotent, resumable nach Unterbrechung Re-verschlüsselt werden alle `EncryptedString`-Spalten (`record`, `user.personal_glossary`, LDAP-Bind-Passwort, OIDC-Secret); ein Test stellt sicher, dass neue Spalten nicht vergessen werden |
| Secrets nie im Repo | ✅ | `.env` `.gitignore`d, `git log --all -- .env` leer; nur `.env.example` getrackt | `_FILE`-Konvention in `env.py:env_or_file()` |
| RBAC mit mehreren Rollen | ✅ | `backend/components/models/user_model.py:27`, `ROLES = ("admin", "moderator", "demo_viewer", "user")` | Durchgesetzt via FastAPI-Dependencies in `auth_routes.py`/`settings_routes.py`/`record.py` |
| LDAP-Filter-Injection-Schutz | ✅ | `ldap.py`, `ldap3.utils.conv.escape_filter_chars()` vor Filteraufbau | |
| Leeres-Passwort-Bind-Bypass verhindert | ✅ | `ldap.py`, Empty-Password-Check vor Bind (RFC-4513-Guard) | |
| CSRF-Schutz | ✅ (strukturell) | Bearer-Token statt Cookie-Auth für API — klassischer CSRF-Vektor entfällt (`SECURITY.md`) | Einzige Cookie: signierter OIDC-`state` |
| CORS-Konfiguration | ⚠️ | `CORS_ALLOWED_ORIGINS`, fällt bei unset auf `*` zurück (mit Logwarnung) | Muss vom Betreiber gesetzt werden |
| Zugriffsschutz der Settings-Endpunkte (Geheimnisse) | ✅ (seit Unreleased) | `settings_routes.py`: `llm-`/`ldap-`/`oidc-settings` per `_require_secret_reader` nur Admin (Demo-Viewer ohne Geheimnisse); `whisper-settings` öffentlich, API-Keys nur für Admins; Schreiben nur `_require_admin` | **Vorher** waren diese GETs ohne Login lesbar (API-Keys, LDAP-Bind-Passwort, OIDC-Secret) — Eintrag unter Security in `CHANGELOG.md`; Betreiber sollten Zugangsdaten rotieren |
| Keine öffentliche Selbstregistrierung | ✅ | Es gibt keinen `/register`-Endpunkt mehr; Konten legt ein Admin an (`POST /api/v1/auth/users`) oder sie entstehen beim ersten LDAP-/OIDC-Login | Seit v0.8.3-Folgerelease (Unreleased); vorher konnte jeder ein aktives Konto mit Rolle `user` anlegen |
| Bewusst unauthentifizierte Endpunkte | ⚠️ | `GET /settings/client-config/` (Client braucht die Richtlinie vor dem Login, Inhalt nicht geheim), `GET /settings/whisper-settings/` (ohne Keys), `/api/version`, `/auth/oidc/status` | Liste bei neuen Endpunkten pflegen; `PUT` jeweils nur Admin |
| Rate-Limiting / Brute-Force-Schutz | ✅ (app-seitig, `/login`) | `backend/components/services/rate_limiter.py` — Sliding-Window-Limiter (5 Req/60s per Client-IP, `X-Forwarded-For`-bewusst), HTTP 429 bei Überschreitung; aufgerufen in `auth_routes.py:login()` vor jedem Login-Versuch; Tests: `tests/auth/test_rate_limiter.py` (8 Unit- + 2 Integrationstests) | Nur Login-Endpoint; andere Endpoints weiterhin über Reverse Proxy/Gateway zu schützen. In-Memory (per Prozess) — bei Multi-Instance-Deployments wirkt das Limit pro Instanz, Redis-basierte Ablage wäre der nächste Ausbauschritt |
| Audit-Log für Admin-Aktionen und Sicherheitsereignisse | ✅ (seit Unreleased) | `backend/components/services/audit_service.py`, Tabelle `auditevent`, Admin-UI → *Audit* (`AuditLog.tsx`), `GET /api/v1/settings/audit/` + CSV-Export; Tests: `tests/audit/test_audit_log.py` | Erfasst Benutzerverwaltung, Settings-Änderungen (nur Feldnamen), globale Kategorien/Wörterbücher, Backup, Retry, abgelehnte Logins, jedes HTTP 403 und Rollen-Sync. Bewusst **nicht**: eigene Aufnahmen, erfolgreiche Logins. Retention `AUDIT_RETENTION_DAYS` (365). Kein Manipulationsschutz gegen DB-Admins (keine Hash-Kette); Mitbestimmung (§ 87 BetrVG) liegt beim Betreiber |
| Multi-Faktor-Authentifizierung | ❌ | `SECURITY.md`: "not implemented anywhere in this app" | Weder lokal noch LDAP/OIDC-seitig |
| Security-Response-Header (HSTS, X-Frame-Options etc.) | ⚠️ (Betreiber-Konfig) | `SECURITY.md`: nur `Permissions-Policy` in `backend/run.py`; HSTS/X-Frame-Options/X-Content-Type-Options/Referrer-Policy jetzt als fertige Reverse-Proxy-Beispiele in `docs/examples/apache-vhost.conf.example` + `docs/examples/nginx-vhost.conf.example` | App setzt sie weiterhin nicht selbst — Betreiber muss die Beispiel-Config übernehmen. Bewusst keine CSP (Inline-Script/WS/AudioWorklet, siehe Beispieldateien) |
| Security-relevante Tests vorhanden | ✅ | `tests/security/test_field_encryption.py`, `tests/auth/test_rbac.py`, `tests/auth/test_oidc_routes.py`, `tests/auth/test_rate_limiter.py`, `tests/services/test_ldap_service.py`, `tests/services/test_oidc_service.py`, `tests/services/test_sanitizing_service.py` | |
| Vulnerability-Disclosure-Prozess | ✅ | `SECURITY.md` — E-Mail-Kontakt, 48h-Antwortzeit, 90-Tage-Policy | Dedizierte `security@`-Adresse laut Doku noch offen |
| Container läuft als Root | ✅ | `Dockerfile:69-72`, `parakeet_server/Dockerfile:99-102`, `whisper_server/Dockerfile:58-62`, `garage/init/Dockerfile:17-23` — alle 4 First-Party-Images laufen als `appuser` (UID/GID 1000); `SECURITY.md` aktualisiert | Gilt für neue Deployments/Volumes; bestehende (root-owned) Volumes bräuchten vor einem Upgrade einen einmaligen `chown` |
| DB/Redis nicht öffentlich erreichbar | ✅ | `docker-compose.yml`/`docker-swarm.yml`: keine `ports:`-Mappings für `postgres`/`redis` | |
| Redis-Authentifizierung | ❌ | Kein `requirepass` in beiden Compose-Dateien | Nur akzeptabel, weil nicht extern exponiert |

## Datenschutz / DSGVO

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| Datenflussdiagramm / ROPA-Ausgangspunkt | ✅ | [`docs/data-mapping.md`](data-mapping.md) inkl. Mermaid-Flowchart | Explizit als Startpunkt für Art. 30 DSGVO deklariert |
| Art.-32-Maßnahmentabelle | ✅ | `SECURITY.md` "Technical Measures (Article 32)" | Ehrlich mit ⚠️ markierte Zeilen (z. B. Verschlüsselung in Transit) |
| PII-Pseudonymisierung (EntityGuard) | ✅ (optional aktivierbar) | [`docs/pii.md`](pii.md) | Fail-closed bei nicht erreichbarem Sanitizer |
| Eindeutigkeit der PII-Tokens als Kollisionsrisiko dokumentiert | ✅ | `docs/pii.md`: Tokens müssen pro Vorkommen eindeutig sein, sonst Mapping-Kollision | Verantwortung liegt beim Sanitizer-Dienst |
| Datenminimierung bei Rohaudio | ⚠️ | `data-mapping.md`: PCM/WAV wird nach *erfolgreicher* Verarbeitung gelöscht; bei Fehlschlag unverschlüsselt in `chunks/failed/`, nach `FAILED_AUDIO_RETENTION_DAYS` (Standard 3) verschlüsselt in den Objektspeicher archiviert (`failed_audio_archival_service.py`) | Bewusster Trade-off (Retry-Fähigkeit vs. Minimierung). Ohne Objektspeicher entfällt die Archivierung, die Datei bleibt unverschlüsselt lokal |
| Recht auf Berichtigung | ✅ | `PUT /record/{id}`, `PUT /users/{id}` (`SECURITY.md`) | |
| Recht auf Löschung | ⚠️ | `DELETE /record/{id}` — Hard-Delete, aber kein Bulk-"alles zu Patient X löschen" | |
| Recht auf Auskunft | ❌ | `SECURITY.md`: kein Self-Service-Export-Endpoint | Nur manuelle DB-Abfrage |
| Recht auf Datenübertragbarkeit | ❌ | `SECURITY.md`: kein JSON/strukturierter Export | Gleiche Lücke wie Auskunftsrecht |
| Widerspruchsrecht (Opt-out LLM-Verarbeitung) | ❌ | `SECURITY.md`: kein Consent-Flag pro Datensatz/Patient | LLM-Schritt läuft immer, wenn Kategorie konfiguriert ist |
| Verschlüsselung in Transit zu externen Endpunkten erzwungen | ❌ (nicht erzwungen) | `data-mapping.md`: hängt von eingetragener URL ab (`https://`/`ldaps://`), Anwendung erzwingt nichts | Betreiberverantwortung |
| Externe Auftragsverarbeiter dokumentiert | ✅ | `data-mapping.md` "Externe Stellen / mögliche Auftragsverarbeiter" | Unterscheidet default-self-hosted vs. betreiberkonfiguriert |
| Aufbewahrungsfristen dokumentiert und durchsetzbar | ✅ (seit Unreleased) | `data-mapping.md` "Aufbewahrung & Löschung"; `auto_delete_service.py`: globale Höchstfrist (Admin) + kürzere persönliche Frist pro Nutzer, inkl. Audio, Löschläufe im Audit-Log (`records.auto_delete`); Tests: `tests/services/test_auto_delete_service.py` | Standardmäßig aus — der Betreiber muss die Frist seines Löschkonzepts eintragen |
| "Bekannte Lücken" explizit benannt | ✅ | `data-mapping.md` eigener Abschnitt "Bekannte Lücken" | Vorbildlich für Auditierbarkeit — Lücken werden nicht versteckt |

## Lizenz / Compliance

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| Root-`LICENSE`-Datei vorhanden, konsistent und vollständig | ✅ | `LICENSE` (voller AGPL-3.0-Text, 661 Zeilen), `LICENSES/AGPL-3.0-or-later.txt` (REUSE-Pfad, identischer Text), `pyproject.toml`: `license = {text = "AGPL-3.0-or-later"}` | War vorher unvollständig (nur der "How to Apply"-Anhang, 33 Zeilen) — beim Beheben der SPDX-Header mit aufgefallen und korrigiert |
| Copyright-Angabe konsistent | ✅ | `LICENSE` ist der unveränderte AGPL-Text; der Rechteinhaber (S2A Open Technologies gGmbH) steht in den Quelldateien (`Copyright (C)` + `SPDX-FileCopyrightText`), in `REUSE.toml` und `README.md`; Urheber/Autor siehe `AUTHORS`; `frontend/package.json`: `"license": "AGPL-3.0-or-later"` | War vorher inkonsistent — `frontend/package.json` deklarierte fälschlich `"Apache-2.0"`, ebenfalls beim Beheben der SPDX-Header entdeckt und korrigiert |
| Datei-Lizenzheader | ✅ | Alle Quelldateien (`.py`/`.ts`/`.tsx`/`.css`/Dockerfiles) tragen den vollständigen AGPL-Header; `scripts/add_spdx_headers.py` hält das mechanisch nach | Volltext-Header **plus** SPDX-Kurzform-Tags (siehe unten) |
| Lizenz-Header auch in Dockerfiles | ✅ | gleiche Header-Form als Kommentarblock, jetzt in allen 4 Dockerfiles (vorher nur im Root-`Dockerfile`) | |
| `AUTHORS`-Datei | ✅ | listet einen "Primary Developer" | Contributions-Abschnitt aspirational, keine tatsächlichen externen Contributor |
| Dependency-Lockfiles vorhanden | ✅ | `pyproject.toml` (75 Einträge) + `uv.lock`; `frontend/package.json` (75 Pakete) + `package-lock.json` | Reproduzierbare Installationen |
| Third-Party-Notices-Datei | ✅ | [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) (Root), generiert via `python scripts/check_licenses.py --write-notices` | 90 Backend- + 368 Frontend-Pakete mit Name/Version/Lizenz; regenerierbar, nicht von Hand gepflegt (gleiches Muster wie `scripts/bump_version.py`) |
| Automatisierte Lizenzkompatibilitäts-Prüfung | ✅ | `scripts/check_licenses.py` (nutzt `pip-licenses` + `license-checker-rseidelsohn`, Allowlist AGPL-3.0-kompatibler Lizenzen) | Manuell auszuführen, nicht CI-erzwungen — konsistent mit `safety check`/`npm audit` in `CONTRIBUTING.md`. Aktuell 3 Pakete zur manuellen Prüfung markiert (2 davon nur eigene Dev-Tools: `reuse`, `python-debian`) |
| SPDX-konforme Kurzform-Header | ✅ | `SPDX-FileCopyrightText`/`SPDX-License-Identifier`-Zeilen in allen Quelldateien; `REUSE.toml` deckt Tests, Migrationen, Lockfiles, Config/Doku-Dateien pauschal ab | |
| REUSE-Spec-Konformität | ✅ | `reuse lint` (REUSE Tool 6.2.0) läuft für alle versionierten Dateien grün (Stand 2026-10-08; die i18n-Übersetzungsdateien `frontend/src/i18n/locales/**` sind seit diesem Datum über `REUSE.toml` abgedeckt, nur die untracked Scratch-Datei `.scratch_fw/` wird bemängelt; `.github/**` + Root-Governance-Dateien über `REUSE.toml` abgedeckt) | Direkter Nachweis, nicht nur Behauptung — Tool ist als Dev-Dependency in `pyproject.toml` |
| SBOM (Software-Stückliste) pro Container-Image | ✅ (freiwillig) | `.github/workflows/docker-publish.yml`: `anchore/sbom-action` (syft, v0.24.2) erzeugt bei jedem Publish-Lauf CycloneDX-JSON-SBOMs für alle 6 Image-Varianten, gepinnt auf den exakten Manifest-Digest, als herunterladbare Artifacts; zusätzlich `provenance: true` + `sbom: true` im build-push-Step | **Bewusst freiwillig, keine Pflicht**: CRA-Pflichten entfallen für nicht-kommerzielles AGPL-v3-OSS (siehe `docs/hospital-audit-frameworks.md` §7) — die SBOM ist ein fertiges Nachweis-Artifact für Audits/Krankenhaus-Beschaffung, nicht Compliance-Zwang. Kein CVE-Scan-Gate dahinter (bewusst, siehe CRA-Abschnitt) |

## Projekt-Health / Governance

| Prüfpunkt | Status | Fundstelle/Beleg | Kommentar |
|---|---|---|---|
| CI/CD-Pipeline | ✅ | `.github/workflows/ci.yml` — GitHub Actions: Backend-Job (uv sync, ruff check + format, pytest) und Frontend-Job (npm ci, vitest, ESLint) bei jedem Push/PR auf `master` | Erster CI-Lauf erfolgt beim nächsten Push |
| Dependency-Scanning automatisiert (Dependabot o. ä.) | ✅ | `.github/dependabot.yml` — wöchentliche PRs für pip (Root, `parakeet_server/`, `whisper_server/`), npm (`frontend/`), Docker-Base-Images und GitHub Actions selbst; gruppierte Updates, PR-Limits pro Ökosystem | Ergänzt die manuellen `safety check`/`npm audit`-Empfehlungen aus `CONTRIBUTING.md` |
| `CONTRIBUTING.md` | ✅ | Root-`CONTRIBUTING.md` ist Symlink auf `CONTRIBUTING.md` | GitHub erkennt Root-Ebene automatisch; keine Duplikatpflege nötig |
| CODE_OF_CONDUCT.md | ✅ | Root-`CODE_OF_CONDUCT.md`, adaptiert vom Contributor Covenant 2.1 | Enforce­ment-Kontakt = Maintainer-Adresse |
| `SECURITY.md` an Standard-Ort | ✅ | `SECURITY.md` liegt direkt im Repo-Root (bis 2026-09-23 Symlink auf `docs/SECURITY.md`, jetzt die kanonische Datei selbst — Referenzen in anderen Docs entsprechend angepasst) | GitHub's Security-Tab-Erkennung greift |
| CHANGELOG.md | ✅ | Root-`CHANGELOG.md`, Keep-a-Changelog-Format; `[Unreleased]` plus versionierte Abschnitte bis 0.8.x; `bump_version.py` verschiebt `[Unreleased]` automatisch, `release.yml` übernimmt den Abschnitt als GitHub-Release-Notes | Pflege-Empfehlung: Eintrag pro Feature/Fix im zugehörigen PR |
| Issue-/PR-Templates | ✅ | `.github/ISSUE_TEMPLATE/bug_report.yaml`, `feature_request.yaml` (Formulare, inkl. "Kein Medizinprodukt"/Patientendaten-Warnhinweis), `.github/PULL_REQUEST_TEMPLATE.md` (Checkliste: Tests, Alembic-Migration, Lizenz-Header, Disclaimer-Integrität) | |
| Versionierungs-Tooling vorhanden | ✅ | `scripts/bump_version.py`, synct `pyproject.toml` + `frontend/package.json` + Lockfile | |
| Versionierung tatsächlich genutzt (Git-Tags) | ✅ | Tags `v0.1.0` bis `v0.8.3` (Stand 2026-10-08) auf `master`; ein `vX.Y.Z`-Tag löst `.github/workflows/release.yml` (GitHub Release) aus | Version nur auf Zuruf des Maintainers bumpen, siehe AGENTS.md → Release rule |
| Testabdeckung Backend | ✅ | Testdateien unter `tests/` (Stand 2026-10-08: Backend 265 pytest-Tests grün, Frontend 286 vitest-Tests grün, 1 übersprungen), u. a. Security/Auth/Services inkl. Rate-Limiter | pytest, `tests/conftest.py` mit geteilten Fixtures; jetzt auch CI-erzwungen |
| Testabdeckung Frontend | ✅ | 31 `.test.tsx`/`.test.ts`-Dateien unter `frontend/src/**/__tests__/` (209 Tests grün, 1 skipped) | Colocated-Konvention (Vitest); Skip ist jsdom-Bug in Radix-Dialog-Fokus-Trap, Funktionalität manuell verifiziert; jetzt auch CI-erzwungen |
| Commit-/Maintainer-Aktivität | ✅ (aktiv) | 148 Commits (Stand 2026-10-08), aktuelle Feature-Cadence (Rate-Limiting, Governance-Aufbau, Licensing) | Projekt ist nicht verwaist |
| Bus-Faktor | ❌ (=1) | Alle 148 Commits (Stand 2026-10-08) stammen von einer Person; Git-Identitäten per `git filter-repo` auf `Christopher Abanilla <christopher.abanilla@gmx.de>` vereinheitlicht | Kein zweiter Maintainer, kein dokumentierter Nachfolgeprozess |
| Docker-Reproduzierbarkeit | ⚠️ | Dockerfiles für alle 4 Services vorhanden; Base-Images gemischt gepinnt (`dxflrs/garage:v1.0.1` exakt vs. `node:22-slim`/`python:3.12-slim` mit floatendem Minor/Patch) | Keine Digest-Pins (`@sha256:...`) — Builds nicht bit-identisch reproduzierbar |
| Health-Check-Endpoint für Betrieb | ✅ | `GET /api/v1/settings/services-health/`, prüft Postgres/Redis/Whisper/Parakeet/EntityGuard/S3/Encryption-Key-Status | 