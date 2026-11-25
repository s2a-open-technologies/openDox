# Datenschutz-Folgenabschätzung (DSFA): Vorlage für Betreiber von openDox

> Stand: 2026-11-06 · gilt für openDox ab Version 0.11.x
>
> **Diese Vorlage ist keine fertige DSFA.** Durchführen und verantworten muss die
> DSFA nach Art. 35 DSGVO der **Verantwortliche**, also die Klinik, Praxis oder das MVZ,
> die openDox betreibt. Das lässt sich nicht an den Hersteller abgeben. Bei
> Self-Hosting ist der Hersteller weder Verantwortlicher noch Auftragsverarbeiter: Er
> sieht keine Daten der Instanz.
>
> Die Vorlage beschreibt alles, was aus dem Code folgt, jeweils mit Fundstelle.
> Felder mit **► Betreiber:** füllen Sie selbst aus, ebenso die Bewertungen, die Sie
> an Ihre Umgebung anpassen. Ziehen Sie Ihren Datenschutzbeauftragten hinzu (Art. 35
> Abs. 2 DSGVO). Die Vorlage ist keine Rechtsberatung.

Verwandte Dokumente:
- [`zweckbestimmung.md`](zweckbestimmung.md): Zweck und Abgrenzung
- [`data-mapping.md`](data-mapping.md): Datenflüsse im Detail
- [`pii.md`](pii.md): PII-Sanitizer
- [`../SECURITY.md`](../SECURITY.md): Sicherheitsarchitektur
- [`audit-checklist-opendox.md`](audit-checklist-opendox.md): Selbstauskunft mit Lücken

## 0. Angaben zur Durchführung

| Feld | Eintrag |
|---|---|
| Verantwortlicher (Art. 4 Nr. 7) | ► Betreiber: |
| Datenschutzbeauftragter | ► Betreiber: |
| Beteiligte (IT, Fachbereich, Betriebs-/Personalrat) | ► Betreiber: |
| openDox-Version, Installationsart (Compose/Swarm) | ► Betreiber: |
| Datum, Version dieser DSFA | ► Betreiber: |

## 1. Ist eine DSFA erforderlich?

Ja, in aller Regel. Begründung:

- **Art. 35 Abs. 3 lit. b DSGVO:** umfangreiche Verarbeitung besonderer Kategorien nach
  Art. 9 (Gesundheitsdaten im Diktat).
- **Kriterien der Leitlinien WP 248 rev.01 (EDSA),** von denen meist mehrere zutreffen:
  - sensible Daten (Gesundheit, Berufsgeheimnis nach § 203 StGB),
  - schutzbedürftige Betroffene (Patientinnen und Patienten),
  - innovative Technologie (Spracherkennung und Sprachmodelle),
  - Verarbeitung in großem Umfang (abhängig von der Einrichtung).
- **DSK-Liste der Verarbeitungen mit DSFA-Pflicht (Muss-Liste):** prüfen Sie die
  einschlägigen Einträge, insbesondere zu Daten unter Berufsgeheimnis und zum Einsatz
  von KI.

► Betreiber: Begründung, falls Sie zu einem anderen Ergebnis kommen (etwa sehr kleine
Einzelpraxis):

**AI Act:** openDox ist kein Hochrisiko-KI-System. Es ist kein Medizinprodukt (siehe
Zweckbestimmung) und fällt unter keinen Bereich des Anhangs III. Eine
Grundrechte-Folgenabschätzung nach Art. 27 AI Act ist deshalb nicht erforderlich.
Verwenden Sie openDox abweichend von der Zweckbestimmung, ändert sich diese Einschätzung
(Zweckbestimmung, Abschnitt 6).

## 2. Systematische Beschreibung der Verarbeitung (Art. 35 Abs. 7 lit. a)

### Zweck

Dokumentationsunterstützung: Gesprochenes von medizinischem Fachpersonal wird in Text
umgewandelt, optional maskiert, optional übersetzt und optional von einem Sprachmodell
zu einem Textentwurf aufbereitet. Abgrenzung und Ausschlüsse:
[`zweckbestimmung.md`](zweckbestimmung.md).

| Feld | Eintrag |
|---|---|
| Rechtsgrundlage | ► Betreiber: typisch Art. 6 Abs. 1 lit. c/e mit Art. 9 Abs. 2 lit. h DSGVO und § 22 Abs. 1 Nr. 1 lit. b BDSG bzw. Landeskrankenhausrecht; prüfen |
| Einsatzbereiche und Kategorien | ► Betreiber: Stationen/Abteilungen; nur Kategorie *Standard* oder eigene Kategorien? |
| Anzahl Benutzer, Diktate pro Tag | ► Betreiber: |

### Betroffene und Datenkategorien

| Betroffene | Daten | Fundstelle |
|---|---|---|
| Patientinnen und Patienten, ggf. Angehörige und Dritte, die im Diktat genannt werden | Audio, Transkript, Übersetzung, Zusammenfassung (Gesundheitsdaten, Art. 9), Namen im Freitext | `Record.content`, `translation`, `translation_segments`, `summarize`, `pii_mapping` in `record_model.py` |
| Beschäftigte (Benutzer) | Kontodaten, Rolle, persönliche Wörterbücher, Spracheinstellung, Aufbewahrungsfrist | `User` in `user_model.py`, `Dictionary` in `dictionary.py` |
| Beschäftigte (Administration und Anmeldeversuche) | Audit-Einträge: Aktion, Feldnamen, IP, Rolle, eingegebener Benutzername bei Fehlanmeldung | `AuditEvent` in `audit_model.py`, `audit_service.py` |

### Datenfluss, Empfänger, Speicherorte

Der vollständige Fluss mit Diagramm steht in [`data-mapping.md`](data-mapping.md). Kurz:

1. **Aufnahme:** Audio geht per WebSocket an den openDox-Server und liegt dort
   temporär in `chunks/`. Optional läuft die Live-Vorschau über Parakeet.
2. **Transkription:** Whisper, self-hosted im Stack.
3. **Übersetzung (optional, nur nach Freigabe):** Das Transkript geht an den
   LLM-Endpunkt. Bei aktivem Sanitizer werden Namen vorher maskiert
   (`_translate_record()` in `background_transcription_service.py`).
4. **PII-Maskierung (optional):** Sanitizer-Endpunkt (EntityGuard), Adresse frei
   konfigurierbar.
5. **Textentwurf (optional):** LLM-Endpunkt, Adresse frei konfigurierbar,
   OpenAI-kompatibel.
6. **Speicherung:** PostgreSQL, Inhalte feldweise verschlüsselt (Fernet,
   `field_encryption.py`). Optional wird Audio verschlüsselt im Objektspeicher abgelegt.
7. **Übernahme:** Anwender kopieren den Text, oder der Desktop-Client fügt ihn in ein
   Zielprogramm ein ([`client.md`](client.md)).

| Empfänger | Ort | Eintrag |
|---|---|---|
| Whisper, Parakeet, PostgreSQL, Redis, Garage | im openDox-Stack | ► Betreiber: Hosting (eigenes RZ, Dienstleister?) |
| LLM-Endpunkt | konfigurierbar | ► Betreiber: Anbieter, Standort, Drittland ja/nein, AV-Vertrag |
| PII-Sanitizer | konfigurierbar | ► Betreiber: Anbieter, Standort, AV-Vertrag |
| LDAP/AD, OIDC-Provider | konfigurierbar (nur Anmeldedaten) | ► Betreiber: |
| Externer Objektspeicher (statt Garage) | konfigurierbar (nur verschlüsselte Blobs) | ► Betreiber: |
| Zielsysteme des Desktop-Clients (KIS, PVS) | beim Anwender | ► Betreiber: |

### Fristen

| Daten | Frist im Code | Eintrag |
|---|---|---|
| Rohaudio | nach erfolgreicher Verarbeitung gelöscht; bei Fehlschlag aufbewahrt, nach `FAILED_AUDIO_RETENTION_DAYS` (Standard 3) verschlüsselt archiviert | ► Betreiber: Frist bestätigen |
| Aufnahmen (Text, optional Audio) | bis zur Löschung oder automatischen Löschung (`auto_delete_service.py`, globale Höchstfrist plus kürzere persönliche Frist; Standard: aus) | ► Betreiber: Frist laut Löschkonzept (z. B. bis zur Übernahme in die Akte) |
| Audit-Log | `AUDIT_RETENTION_DAYS` (Standard 365) | ► Betreiber: mit Betriebs- bzw. Personalrat abgestimmte Frist |

## 3. Notwendigkeit und Verhältnismäßigkeit (Art. 35 Abs. 7 lit. b)

- **Zweckbindung:** Der Zweck ist in der Zweckbestimmung festgelegt. Die mitgelieferte
  Kategorie *Standard* (nur Zeichensetzung) ist schreibgeschützt
  (`Categories.is_builtin`, `settings_routes.py`). Eigene Prompts sind
  Betreiberentscheidung. Benutzerkategorien sind standardmäßig aus
  (`personal_categories_allowed`).
- **Datenminimierung:**
  - Das Rohaudio wird nach der Verarbeitung gelöscht.
  - Ein optionaler Sanitizer maskiert Namen vor jeder LLM-Verarbeitung (Zusammenfassung
    und Übersetzung).
  - Das LLM lässt sich je Kategorie abschalten, dann wird nur transkribiert
    (`llm_gate.py`).
  - Die Übersetzung ist standardmäßig aus und wird nur für freigegebene Benutzer
    eingeschaltet (`translation_gate.py`).
- **Speicherbegrenzung:** automatisches Löschen, Audit-Frist, Bereinigung temporärer
  Dateien (`chunk_cleanup.py`).
- **Richtigkeit:** Jede Ausgabe ist ein Entwurf mit Prüfpflicht und
  Bestätigungshaken; übersetzte Sätze mit abweichenden Zahlen werden markiert
  (`translation/check.py`).
- **Betroffenenrechte:**
  - Löschung einzelner Aufnahmen ist möglich.
  - Für Auskunft und Datenübertragbarkeit gibt es **keine** Export-Funktion, nur eine
    manuelle Datenbankabfrage ([`audit-checklist-opendox.md`](audit-checklist-opendox.md)).
  - ► Betreiber: Prozess für Auskunftsersuchen. In der Regel ist die Patientenakte die
    maßgebliche Quelle, openDox nur ein Zwischenschritt.
- **Alternativen:** ► Betreiber: Warum ist die Verarbeitung nötig (z. B. Entlastung
  der Dokumentation), und warum reicht ein milderes Mittel nicht (z. B. reine
  Transkription ohne LLM)?

## 4. Risikobewertung (Art. 35 Abs. 7 lit. c)

Die Bewertung von **Eintrittswahrscheinlichkeit (W)** und **Schwere (S)** ist vorbelegt
für eine typische Self-Hosting-Installation mit lokalem LLM. Skala: gering, mittel,
hoch. ► Betreiber: Passen Sie W, S und Restrisiko an Ihre Konfiguration an,
insbesondere bei externem LLM oder Sanitizer.

| # | Risiko | Ursache | W | S | Maßnahmen (Fundstelle) | Restrisiko |
|---|---|---|---|---|---|---|
| R1 | Offenlegung von Gesundheitsdaten an Dritte oder ins Drittland | externer LLM- oder Sanitizer-Endpunkt | gering (lokal) / hoch (extern) | hoch | Self-Hosting als Standard; Sanitizer maskiert Namen vor Zusammenfassung und Übersetzung, fail-closed (`llm_gate.sanitize_if_configured`); LLM je Kategorie abschaltbar | ► Betreiber |
| R2 | Unvollständige Maskierung | Der Sanitizer erkennt nicht jeden Namen, besonders in fremdsprachigem Text | mittel | hoch | Die Maskierung ist ein Zusatzschutz, kein Ersatz für ein vertrauenswürdiges LLM; Übersetzung nur mit lokalem LLM betreiben | mittel |
| R3 | Falsche Dokumentation | Hör-, Schreib- oder Übersetzungsfehler, Halluzination, vertauschte Zahlen oder Verneinungen | mittel | hoch | Prüfpflicht mit Bestätigungshaken; Original bleibt erhalten; Zahlenabgleich pro übersetztem Satz; Anti-Platzhalter-Regel (`llm_model.py`); Hinweis „Kein Medizinprodukt“ | mittel (abhängig von der Prüfdisziplin) |
| R4 | Unbefugter Zugriff auf Aufnahmen | fremde Konten, zu weite Rollen | gering | hoch | Aufnahmen nur für ihre Eigentümer (`_require_owner` in `record.py`), auch nicht für Admins; LDAP/OIDC mit Gruppen-Gate (fail-closed); Sitzungsprüfung bei Verlängerung; Leerlauf-Abmeldung; Rate-Limit beim Login | gering |
| R5 | Offenlegung bei Diebstahl der Datenbank oder eines Backups | Zugriff auf DB-Dateien | gering | hoch | Feldverschlüsselung der Inhalte (`field_encryption.py`, `ENCRYPTION_KEY` Pflicht); Einstellungs-Backup ohne Aufnahmen und ohne Zugangsdaten | gering (Schlüssel getrennt aufbewahren) |
| R6 | Verlust der Verfügbarkeit oder Daten | Schlüsselverlust, Ausfall | mittel | mittel | Schlüsselrotation (`key_rotation.py`); Prüfung „Verschlüsselungsschlüssel“ im System-Tab; fehlgeschlagene Aufnahmen bleiben für einen Retry erhalten | ► Betreiber: Backup- und Schlüsselkonzept |
| R7 | Unverschlüsseltes Rohaudio auf dem Server | Audio fehlgeschlagener Transkriptionen in `chunks/failed/` | gering | hoch | Archivierung nach 3 Tagen verschlüsselt im Objektspeicher; Zugriff nur für Server-Administratoren | mittel ohne Objektspeicher (bekannte Lücke, [`data-mapping.md`](data-mapping.md)) |
| R8 | Zweckabweichung durch eigene Prompts | Benutzer- oder Betreiberkategorien mit diagnostischen Aufträgen | mittel | hoch | Benutzerkategorien standardmäßig aus; *Standard* schreibgeschützt; Hinweis in Oberfläche und Handbuch | ► Betreiber (Verantwortung nach Zweckbestimmung, Abschnitt 6) |
| R9 | Text landet im falschen System | Desktop-Client fügt in das fokussierte Programm ein | mittel | mittel | Einfügen nur auf Handlung des Anwenders; Allow-Liste der Zielprogramme; Zwischenablage-Verlauf ausgeschlossen und automatische Leerung (Windows) | ► Betreiber: Allow-Liste pflegen |
| R10 | Leistungs- und Verhaltenskontrolle von Beschäftigten | Audit-Log mit Benutzername, IP und Zeit | gering | mittel | Bewusst schmaler Umfang: keine Protokollierung der Arbeit mit eigenen Aufnahmen, keine Inhalte; Lesen nur durch Admins; automatische Löschung | ► Betreiber: Vereinbarung nach § 87 Abs. 1 Nr. 6 BetrVG |
| R11 | Zugangsdaten zu Drittsystemen werden bekannt | API-Keys, LDAP-Bind-Passwort | gering | mittel | Schlüssel nur für Admins lesbar; nicht im Backup; Docker-Secrets (`_FILE`) | gering |
| R12 | Unverschlüsselte Übertragung zu externen Diensten | Endpunkte ohne TLS konfiguriert | ► Betreiber | hoch | Die Anwendung erzwingt kein TLS (bekannte Lücke) | ► Betreiber: nur `https`-Endpunkte |

## 5. Abhilfemaßnahmen (Art. 35 Abs. 7 lit. d)

**Technisch (im Produkt):** siehe Spalte „Maßnahmen“ oben. Dazu gehören:
- Verschlüsselung at rest ([`../SECURITY.md`](../SECURITY.md), *Data Encryption*),
- Authentifizierung und Rollen (*Authentication & Authorization*),
- Löschfristen ([`data-mapping.md`](data-mapping.md), *Aufbewahrung & Löschung*),
- das Audit-Log.

**Organisatorisch (beim Betreiber).** ► Betreiber: Umsetzung festhalten.
- LLM und Sanitizer selbst betreiben oder mit AV-Vertrag und ohne Drittlandtransfer
  einbinden.
- Löschfrist für Aufnahmen und Audit-Log festlegen und einschalten.
- Schulung: Prüfpflicht, keine vollständigen Patientennamen im Titel, Umgang mit
  Übersetzungen.
- Freigabeprozess für eigene Kategorien und für die Übersetzung.
- Vereinbarung mit Betriebs- bzw. Personalrat zum Audit-Log.
- Backup- und Schlüsselkonzept, Zugriffsschutz auf den Server und `chunks/`.
- TLS für alle externen Endpunkte, Objektspeicher konfigurieren.
- Prozess für Betroffenenanfragen.

## 6. Ergebnis

| Feld | Eintrag |
|---|---|
| Verbleibende hohe Risiken? | ► Betreiber: |
| Konsultation der Aufsichtsbehörde nach Art. 36 nötig? | ► Betreiber: (nur wenn trotz Maßnahmen ein hohes Risiko bleibt) |
| Stellungnahme des Datenschutzbeauftragten | ► Betreiber: |
| Freigabe durch den Verantwortlichen (Name, Datum) | ► Betreiber: |
| Nächste Überprüfung | ► Betreiber: spätestens bei einer neuen openDox-Version mit neuen Datenflüssen (siehe `CHANGELOG.md`) oder einer Änderung von LLM, Sanitizer oder Hosting |
