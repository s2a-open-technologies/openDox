# Audit-Rahmenwerke im Krankenhausumfeld — und warum lokale/on-prem KI ein Pluspunkt ist

> Diese Übersicht beschreibt regulatorische Rahmenwerke auf allgemeiner
> Ebene und ordnet openDox' Architektur dagegen ein. **Keine
> Rechtsberatung, keine Einzelfallprüfung** — ob und in welcher
> Ausprägung ein Rahmenwerk für eine konkrete Klinik gilt, hängt von
> Größe, Trägerschaft, Bundesland und tatsächlicher Betriebsweise ab.
> Vor einer Zertifizierung/einem echten Audit immer mit
> Datenschutzbeauftragtem, IT-Sicherheitsbeauftragtem bzw. externen
> Prüfern abstimmen. Ergänzt [`docs/oss-audit-talk-outline.md`](oss-audit-talk-outline.md)
> und [`docs/audit-checklist-opendox.md`](audit-checklist-opendox.md).

## Warum Krankenhäuser mehrere, überlappende Audit-Pflichten haben

Anders als ein typisches SaaS-Unternehmen unterliegt ein Krankenhaus
gleichzeitig: allgemeiner IT-Sicherheitsregulatorik (unabhängig von der
Branche), sektorspezifischer Regulatorik (weil Gesundheitsversorgung als
besonders schützenswert gilt), Produktregulatorik (für die eingesetzte
Software/Hardware selbst) und Datenschutzrecht (wegen
Gesundheitsdaten nach Art. 9 DSGVO). Diese Ebenen überschneiden sich,
werden aber von unterschiedlichen Prüfern mit unterschiedlichem Fokus
abgeklopft — ein Grund, warum "Auditierbarkeit" für ein Tool wie openDox
nicht an einem einzigen Zertifikat hängt, sondern an durchgängiger
Dokumentation über alle Ebenen hinweg.

## 1. ISO/IEC 27001 (Informationssicherheits-Managementsystem)

**Was es prüft**: nicht primär den Code, sondern den *Prozess* — hat die
Organisation ein systematisches Risikomanagement für Informationssicherheit
(Asset-Inventar, Risikobewertung, Kontrollen nach Anhang A, kontinuierliche
Verbesserung)? Weltweit anerkannter Standard, oft Grundvoraussetzung, um
überhaupt als Lieferant in Ausschreibungen zugelassen zu werden. Für den
Gesundheitssektor existiert mit **ISO 27799** eine branchenspezifische
Ergänzung (Leitfaden für Gesundheitsorganisationen, baut auf ISO 27002 auf).

**openDox-Bezug**: ISO 27001 zertifiziert die *Organisation* des
Krankenhauses, nicht das einzelne Tool — aber ein Auditor prüft im Rahmen
von Anhang-A-Kontrollen (z. B. A.8 Asset Management, A.13
Kommunikationssicherheit) typischerweise auch eingesetzte Software auf
Datenabfluss-Risiken. Hier zählt konkret: **keine Telemetrie/Phone-Home**
(verifiziert per Grep über `backend/` und `frontend/src/` — keine
Sentry/PostHog/Google-Analytics/Mixpanel/Datadog-o.-ä.-Aufrufe gefunden) und
die durchgängige Feldverschlüsselung (`docs/SECURITY.md`) als direkt
zitierbare technische Kontrolle für A.8.24 (Kryptographie).

## 2. BSI IT-Grundschutz

**Was es prüft**: deutsche Alternative/Ergänzung zu ISO 27001 mit
konkreteren, bausteinbasierten Vorgaben (IT-Grundschutz-Kompendium). Oft
Grundlage, auf der ein B3S-Nachweis (siehe unten) aufbaut, oder eigenständig
als "IT-Grundschutz-Zertifikat" erreichbar.

**openDox-Bezug**: wie bei ISO 27001 zählt hier vor allem, dass sich die
Architektur *ohne Widerspruch* in ein Grundschutz-Konzept einfügen lässt —
insbesondere der Baustein zu Netzsegmentierung profitiert davon, dass
`docker-compose.yml`/`docker-swarm.yml` Datenbank und Redis grundsätzlich
ohne Host-Port-Mapping betreiben (nur im internen Docker-Netz erreichbar,
siehe `docs/audit-checklist-opendox.md`).

## 3. B3S Gesundheitsversorgung im Krankenhaus

**Was es prüft**: der "Branchenspezifische Sicherheitsstandard" nach
§ 8a BSIG — verpflichtend für **KRITIS-Krankenhäuser** (aktuell: Häuser ab
einem gesetzlich definierten Schwellenwert stationärer Fälle pro Jahr).
Konkretisiert IT-Sicherheitsanforderungen speziell für den
Krankenhausbetrieb (z. B. medizintechnische Geräte, Patientendatenflüsse).

**openDox-Bezug**: auch unterhalb der KRITIS-Schwelle ein guter
Orientierungsrahmen. Der B3S verlangt u. a. Nachweise zur
Datenflusstransparenz — genau das liefert
[`docs/data-mapping.md`](data-mapping.md) bereits als ROPA-Ausgangspunkt
mit Mermaid-Diagramm, inklusive expliziter Unterscheidung "per Default
self-hosted" vs. "vom Betreiber konfigurierbar (potenziell extern)".

## 4. § 75c SGB V — IT-Sicherheit für alle Krankenhäuser

**Was es prüft**: seit 2022 gilt für **jedes** Krankenhaus in Deutschland
(nicht nur KRITIS-Häuser) die Pflicht, IT-Sicherheit nach dem "Stand der
Technik" zu gewährleisten. Das ist die gesetzliche Basis, auf der KHZG-
Fördervoraussetzungen aufbauen — eine niedrigere Einstiegshürde als B3S,
aber verbindlich für die überwiegende Mehrheit der Häuser.

**openDox-Bezug**: "Stand der Technik" wird typischerweise über
anerkannte Referenzen wie den BSI-Grundschutz oder OWASP ausgelegt. Hier
zählt die durchgehende Verschlüsselungsarchitektur
(`field_encryption.py`, Fernet), das Secrets-Handling nach
Docker-Best-Practice (`env_or_file()`) und — spezifisch für lokale KI —
dass ASR-Modelle **beim Docker-Build gebacken** werden
(`parakeet_server/Dockerfile`, Kommentar "Download models at build time
for faster container starts") bzw. beim ersten Start einmalig lokal
gecacht werden (`whisper_server/Dockerfile`, `HF_HOME`-Volume) statt bei
jeder Anfrage Daten an einen externen Modell-Anbieter zu schicken.

## 5. KHZG (Krankenhauszukunftsgesetz)

**Was es prüft**: kein eigenständiger Sicherheitsstandard, sondern ein
Förderprogramm — Fördermittel für Digitalisierungsprojekte sind an den
Nachweis von IT-Sicherheitsmaßnahmen (u. a. § 75c SGB V-Konformität)
gekoppelt. Relevanz für den Vortrag: Digitalisierung und IT-Sicherheit
sind hier gesetzlich *verkoppelt*, nicht getrennt zu betrachten.

**openDox-Bezug**: als selbst-hostbares Tool passt openDox in klassische
KHZG-Förderanträge (z. B. Fördertatbestand "IT-Sicherheit" oder
"Digitale Dokumentation") — die Selbstbetriebs-Fähigkeit (kompletter
Stack via `docker-compose.yml`, keine verpflichtende Cloud-Abhängigkeit)
vermeidet den sonst üblichen Zusatzaufwand, einen externen
SaaS-Anbieter vertraglich/technisch in den Sicherheitsnachweis
einzubeziehen.

## 6. NIS2 (EU-Richtlinie, national über NIS2UmsuCG)

**Was es prüft**: NIS2 erweitert den Kreis der von EU-Cybersicherheits-
Pflichten betroffenen Einrichtungen im Gesundheitssektor deutlich über
die bisherigen KRITIS-Schwellen hinaus ("wichtige Einrichtungen"), mit
Pflichten zu Risikomanagement, Meldepflichten bei Vorfällen und
**Lieferketten-Absicherung** (Art. 21).

**openDox-Bezug**: der Lieferketten-Aspekt ist der interessanteste
Vortragspunkt — jede extern angebundene Cloud-Komponente (Cloud-LLM,
externer PII-Sanitizer, Cloud-Objektspeicher) ist im NIS2-Sinn ein
zusätzliches Lieferketten-Risiko, das gemeldet/bewertet werden muss. Weil
openDox laut `docs/data-mapping.md` **per Default vollständig
self-hosted** ist (Whisper, Parakeet, PostgreSQL, Redis, Garage) und der
LLM-Endpunkt wahlweise komplett lokal (Ollama/vLLM) betrieben werden
kann, reduziert sich die Anzahl der NIS2-relevanten Lieferketten-Glieder
strukturell — nicht weil openDox das "verspricht", sondern weil die
externen Anbindungen bewusste, vom Betreiber gesteuerte Ausnahmen sind,
keine eingebauten Pflichtabhängigkeiten.

## 7. EU Cyber Resilience Act (CRA)

**Was es prüft**: Produktsicherheitspflichten für "Produkte mit
digitalen Elementen", die in der EU in Verkehr gebracht werden — u. a.
SBOM-Pflicht, koordinierte Schwachstellenbehandlung, Pflicht zu
Sicherheitsupdates über den Produktlebenszyklus. **Open-Source-Sonderfall**:
rein community-getriebene, nicht-kommerzielle OSS-Entwicklung ist
grundsätzlich ausgenommen — sobald aber ein Hersteller/Anbieter das
Produkt kommerziell vertreibt oder als Dienstleistung betreibt, greift
der CRA regulär.

**openDox-Bezug — hier ehrlich bleiben**: die Lockfiles
(`pyproject.toml`/`uv.lock`, `frontend/package.json`/`package-lock.json`)
sind eine gute SBOM-*Vorstufe*, aber wie in
[`docs/audit-checklist-opendox.md`](audit-checklist-opendox.md) dokumentiert,
gibt es **kein `.github/`-Verzeichnis, keine CI/CD, kein automatisiertes
Dependency-/Vulnerability-Scanning**. Für den Vortrag ist das der
richtige Moment, die Gegenthese zu zeigen: lokale KI-Architektur löst das
*Datenabfluss*-Problem, ersetzt aber nicht die CRA-Pflicht zu
automatisierter Schwachstellenbehandlung — das bleibt eine echte,
unerledigte Lücke, kein Pluspunkt.

## 8. EU MDR (Medical Device Regulation) — bewusste Abgrenzung

**Was es prüft**: Software, die für diagnostische oder therapeutische
Zwecke bestimmt ist, kann als Medizinprodukt (ggf. "Software as a Medical
Device", je nach Risikoklasse) eingestuft werden — mit entsprechend
hohen Zulassungs- und Überwachungspflichten.

**openDox-Bezug**: openDox ist **explizit kein Medizinprodukt** — und das
ist technisch durchgesetzt, nicht nur behauptet: `DisclaimerGate.tsx`
zeigt eine Pflicht-Checkbox mit MPG/EU-MDR/FDA-Zitat und der Anforderung,
dass jede KI-Ausgabe von qualifiziertem Personal geprüft werden muss,
bevor sie verwendet wird; `App.tsx`'s `ProtectedRoute` blockiert **alle**
Routen bis zur Akzeptanz; serverseitig wird die Zustimmung mit Zeitstempel
in `User.disclaimer_accepted_at` festgehalten (`auth_routes.py`) — kein
reiner Client-Side-Zustand, der sich umgehen ließe. Für den Vortrag lohnt
sich, den Grenzfall zu benennen: würde die KI-Zusammenfassung künftig
*autonome* diagnostische oder therapieentscheidende Aussagen treffen
(statt wie heute ausschließlich strukturierte Dokumentation zur
menschlichen Prüfung), wäre eine MDR-Klassifizierung nicht mehr
auszuschließen — der Human-Review-Zwang ist also nicht nur
Haftungsschutz, sondern die eigentliche Grenze, die das Produkt außerhalb
der MDR hält.

## 9. DSGVO/BDSG

Bereits ausführlich in [`docs/data-mapping.md`](data-mapping.md) und
[`docs/SECURITY.md`](SECURITY.md) (Art.-32-Maßnahmentabelle,
Data-Subject-Rights-Tabelle) sowie in
[`docs/oss-audit-talk-outline.md`](oss-audit-talk-outline.md) behandelt —
hier nur der Querverweis, um Dopplung zu vermeiden.

## Kernbotschaft für diesen Teil des Vortrags

Lokale/self-hosted KI ist im Krankenhausumfeld kein Nice-to-have, sondern
reduziert strukturell die Anzahl der Angriffsflächen, die ein Auditor über
*mehrere* dieser Rahmenwerke hinweg gleichzeitig bewerten muss: weniger
Datenabfluss an Dritte (ISO 27001/BSI-Grundschutz), weniger
Lieferketten-Glieder (NIS2 Art. 21), keine Drittland-Transfer-Fragen für
den ASR-Kernprozess (DSGVO). Das ersetzt aber **nicht** die
Rahmenwerke, die auf *Prozessreife* statt *Architektur* zielen (CRA:
automatisiertes Vulnerability-Handling; ISO 27001: Managementsystem der
Organisation) — dort hat openDox, wie in
[`docs/audit-checklist-opendox.md`](audit-checklist-opendox.md) offen
dokumentiert, reale Lücken. Genau diese Kombination — Architektur als
struktureller Vorteil, Prozessreife als offen benannte Baustelle — ist
die differenzierte Aussage, die im Vortrag überzeugt, statt "lokal =
automatisch audit-sicher" zu behaupten.
