# Vortragsgliederung: Auditierbarkeit von Open Source (openDox als Fallbeispiel)

> Vorbereitungsmaterial für einen Symposium-Vortrag. Kein fertiges Skript,
> sondern eine didaktische Gliederung mit konkreten openDox-Beispielen pro
> Abschnitt — jede Aussage über openDox ist gegen den tatsächlichen Code/die
> tatsächliche Doku verifiziert (siehe [`docs/audit-checklist-opendox.md`](audit-checklist-opendox.md)
> für die Detailbelege).

## 1. Was ist ein Audit?

Ein Audit ist eine **systematische, dokumentierte Prüfung** eines Systems
gegen einen definierten Maßstab (Standard, Gesetz, interne Policy, Best
Practice) durch eine Partei, die nicht selbst das System gebaut hat. Drei
Dinge unterscheiden es von verwandten Praktiken:

- **Code-Review**: informell, kontinuierlich, von Peers, kein formaler
  Bericht — ein Audit ist einmalig/periodisch, formal, mit Findings-Bericht.
- **Penetrationstest**: aktiver Angriffsversuch gegen eine Instanz — ein
  Audit prüft breiter (Code, Prozesse, Doku, Governance), nicht nur "kann
  man reinkommen".
- **Zertifizierung**: ein Audit ist oft die *Grundlage* für eine
  Zertifizierung, aber nicht dasselbe — Zertifizierung ist ein
  formaler Status, den ein Audit-Ergebnis erst ermöglicht.

**Typische Auslöser**: gesetzliche Pflicht (DSGVO, MedTech-Regulatorik),
Kundenanforderung (Enterprise-Kunde verlangt Nachweis vor Kauf),
Sicherheitsvorfall (Post-Mortem-Audit), oder freiwillig (Vertrauensaufbau
bei Open Source, wo es keinen Hersteller mit Haftung gibt).

## 2. Die vier Audit-Dimensionen bei Open Source

Bei kommerzieller Closed-Source-Software prüft ein Audit oft nur Security.
Bei Open Source kommen weitere Dimensionen dazu, weil es *keinen Vertrag*
gibt, der diese Fragen sonst regeln würde:

| Dimension | Kernfrage | openDox-Beispiel |
|---|---|---|
| **Security/Code-Audit** | Ist die Implementierung sicher? | Fernet-Feldverschlüsselung, RBAC, Docker-Secrets-Konvention — siehe [`SECURITY.md`](../SECURITY.md) |
| **Datenschutz/DSGVO-Audit** | Ist die Datenverarbeitung rechtmäßig und nachvollziehbar? | [`docs/data-mapping.md`](data-mapping.md) als ROPA-Ausgangspunkt, EntityGuard-PII-Pipeline ([`docs/pii.md`](pii.md)) |
| **Lizenz-/Compliance-Audit** | Darf ich das nutzen/verändern/weitergeben? | AGPL-3.0-or-later, vollständige Lizenz-Header in fast jeder Datei |
| **Projekt-Health/Governance-Audit** | Überlebt das Projekt den nächsten Bus-Unfall des Maintainers? | Bus-Faktor 1 (alle Commits von einer Person unter vier Git-Identitäten) — CI/CD und Dependabot inzwischen vorhanden, ersetzen die Lücke nicht |

Der Kern der Vortragsbotschaft: **bei Open Source ist die vierte Dimension
(Governance) genauso auditierbar wie Code — und wird am häufigsten
übersehen**, obwohl sie am direktesten beantwortet, ob man dem Projekt
langfristig vertrauen kann.

**Im konkreten Einsatzumfeld Krankenhaus** kommen zusätzliche, teils
verpflichtende Rahmenwerke oberhalb dieser vier generischen Dimensionen
dazu (ISO 27001, B3S, § 75c SGB V, KHZG, NIS2, EU-CRA, EU-MDR-Abgrenzung)
— vertieft mit konkretem openDox-Bezug in
[`docs/hospital-audit-frameworks.md`](hospital-audit-frameworks.md).

## 3. Was ein Auditor braucht

Ein Auditor kann nur das prüfen, was **dokumentiert und auffindbar** ist —
nicht das, was implizit im Kopf des Maintainers steckt. Typische
Dokumentenliste:

- **Threat Model / Sicherheitsarchitektur-Doku** — openDox: [`SECURITY.md`](../SECURITY.md)
- **Datenflussdiagramm** — openDox: [`docs/data-mapping.md`](data-mapping.md) (inkl. Mermaid-Diagramm)
- **Dependency-Manifest/Lockfile + Image-SBOMs** — openDox: `pyproject.toml`/`uv.lock`, `frontend/package.json`/`package-lock.json`, dazu CycloneDX-SBOMs pro Container-Image aus dem Publish-Workflow (`.github/workflows/docker-publish.yml`, freiwillig)
- **Lizenztext + Datei-Header** — openDox: `LICENSE`, AGPL-Header in 115/117 stichprobenartig geprüften Quelldateien
- **Testberichte / Testabdeckung** — openDox: 26 Backend-Testdateien (u. a. `tests/security/`, `tests/auth/`), aber nur 2 Frontend-Tests
- **Zugriffs-/Rollenkonzept** — openDox: `User.ROLES = (admin, moderator, demo_viewer, user)`, durchgesetzt in FastAPI-Dependencies
- **Vulnerability-Disclosure-Prozess** — openDox: Security-Kontakt + 90-Tage-Policy in `SECURITY.md`

Pointe für den Vortrag: openDox hat **die meisten dieser Dokumente
tatsächlich vorliegen** — das ist ungewöhnlich für ein Ein-Personen-Projekt
und genau der Punkt, den man am Beispiel zeigen will. Die SBOM existiert als
freiwilliges Artifact (CycloneDX pro Image, siehe
[`docs/audit-checklist-opendox.md`](audit-checklist-opendox.md)) — die CRA-
*Pflicht* dazu entfällt für nicht-kommerzielles AGPL-v3-OSS (siehe
[`docs/hospital-audit-frameworks.md`](hospital-audit-frameworks.md) §7),
weshalb kein CVE-Scan-Gate dahinter steht. Diese Abgrenzung wird ehrlich
benannt.

## 4. Wie ein Audit generell abläuft

1. **Scoping** — welcher Teil des Systems, welcher Maßstab (z. B. "DSGVO
   Art. 32" oder "OWASP ASVS Level 1")?
2. **Dokumentenprüfung** — existiert die Doku überhaupt, ist sie aktuell?
   (Ein Datum wie "Last updated: 2026-08-02" in `SECURITY.md` ist
   selbst ein Prüfpunkt — Staleness ist ein häufiger Findings-Typ.)
3. **Technische Prüfung** — Code lesen, Konfiguration prüfen, Secrets-Handling
   verifizieren, ggf. automatisierte Scans (SAST, Dependency-Scan).
4. **Interviews** — Maintainer/Team befragen, wo Doku und Realität
   auseinanderklaffen könnten.
5. **Findings-Bericht** — pro Prüfpunkt: Pass / Fail / Gap, mit Belegstelle
   (Dateipfad, Zeile, Commit). Kein Audit ohne nachvollziehbare Evidenz.
6. **Re-Audit** — nach Behebung der Findings, oder periodisch (z. B.
   jährlich, wie openDox es für Encryption-Key-Rotation selbst empfiehlt).

## 5. openDox als Fallbeispiel: was gut vorbereitet ist

Konkrete Stärken, die man im Vortrag zeigen kann (alle mit Fundstelle):

- **Verschlüsselung als Architekturentscheidung, nicht nachträglich**:
  Fernet-Feldverschlüsselung für alle patientenbezogenen Felder
  (`record.content`, `.summarize`, `.pii_mapping`, `.title`) sowie für
  gespeichertes Audio — `backend/components/security/field_encryption.py`.
- **Secrets-Handling nach Docker-Best-Practice**: `env_or_file()` in
  `backend/components/modules/env.py` implementiert die `_FILE`-Konvention
  für alle Secrets; `.env` ist seit jeher `.gitignore`d, nie committed.
- **Key-Rotation ist kein Lippenbekenntnis**: `key_rotation.py` +
  `docker-swarm.rotation.yml` implementieren einen tatsächlichen,
  idempotenten Rotationsprozess mit Fingerprint-Tracking.
- **PII-Sanitizer mit fail-closed-Verhalten**: ist der Sanitizer nicht
  erreichbar, geht die Aufgabe auf `error` statt unsanitisiert ans LLM zu
  gehen — bewusste Entscheidung gegen Verfügbarkeit zugunsten Datenschutz
  (siehe [`docs/pii.md`](pii.md)).
- **Ehrliche eigene Dokumentation als Kulturmerkmal**: `SECURITY.md`
  markiert explizit, was *nicht* implementiert ist (keine MFA, keine
  Redis-Authentifizierung, kein Audit-Log) — das ist genau das Verhalten,
  das man von einem auditierbaren Projekt erwartet, aber selten in freier
  Wildbahn sieht.
- **Vollständige Lizenz-Transparenz**: AGPL-Header in praktisch jeder Datei,
  konsistente Lizenzangabe in `pyproject.toml`, `LICENSE`, `AUTHORS`.
- **Freiwillige SBOM pro Container-Image**: der Publish-Workflow erzeugt bei
  jedem Lauf CycloneDX-SBOMs für alle 6 Image-Varianten, gepinnt auf den
  exakten Manifest-Digest (`.github/workflows/docker-publish.yml`,
  `anchore/sbom-action`) — bewusst freiwillig, weil die CRA-Pflicht für
  nicht-kommerzielles AGPL-v3-OSS entfällt, aber fertig als Nachweis-Artifact
  für Audit-/Beschaffungsfragen.

## 6. openDox als Fallbeispiel: ehrlich benannte Lücken

Genauso wichtig für die Vortragsbotschaft — ein auditierbares Projekt
versteckt seine Lücken nicht, es benennt sie:

- **Keine Digest-Pins bei Docker-Base-Images**: `node:22-slim`/
  `python:3.12-slim` floaten auf Minor/Patch, nur `dxflrs/garage:v1.0.1`
  ist exakt gepinnt — Builds sind nicht bit-identisch reproduzierbar
  (`docs/audit-checklist-opendox.md`, "Docker-Reproduzierbarkeit").
- **Kein technisches Audit-Log**: es gibt keine Tabelle/kein Mechanismus,
  der "wer hat wann welchen Datensatz gelesen/verändert" festhält — nur
  DB-Timestamps. Für Art. 30/32 DSGVO-Rechenschaftspflicht eine reale
  Lücke, kein Nice-to-have.
- **Keine Redis-Authentifizierung**: kein `requirepass` in
  `docker-compose.yml`/`docker-swarm.yml` — nur akzeptabel, weil Redis
  nicht extern exponiert ist, aber eine reale Lücke, falls das
  Docker-Netz selbst mal nicht vertrauenswürdig ist.
- **Bus-Faktor 1**: alle über 150 Commits (Stand 2026-10-08) stammen von einer Person (vier
  verschiedene Git-Identitäten, gleicher Mensch) — kein zweiter Maintainer,
  kein dokumentierter Governance-/Nachfolgeprozess.
- **Verschlüsselung in Transit nicht erzwungen**: ob LLM-/Sanitizer-/
  LDAP-Endpunkte tatsächlich `https://`/`ldaps://` nutzen, hängt von der
  eingetragenen URL ab — die Anwendung selbst erzwingt nichts
  (`SECURITY.md`, Art. 32).
- **Data-Subject-Rights unvollständig**: Auskunfts- und
  Portabilitätsrecht (Art. 15/20 DSGVO) sind laut `SECURITY.md`
  explizit **nicht implementiert** — nur manuelle DB-Abfrage möglich.

## 7. Kernbotschaft für den Vortrag

Auditierbarkeit ist keine Eigenschaft, die man am Ende eines Projekts
"hinzufügt" — sie ist eine Entscheidung, die man von Anfang an trifft:
Verschlüsselung als Default statt Option, Secrets nie im Repo, Lücken
dokumentieren statt verschweigen, Datenflüsse aufzeichnen bevor jemand
danach fragt. openDox zeigt beides gleichzeitig: was es heißt, das von
Anfang an ernst zu nehmen (Abschnitt 5) — und dass selbst ein so
diszipliniertes Projekt reale, unvermeidliche Lücken hat, sobald man genau
hinschaut (Abschnitt 6). Genau diese Kombination — nicht Perfektion,
sondern **nachprüfbare Ehrlichkeit** — ist das, was Open Source
auditierbar macht, wo proprietäre Software sich oft hinter
Vertraulichkeit verstecken kann.
