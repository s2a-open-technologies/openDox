# Zweckbestimmung openDox

> Stand: 2026-10-05 · gilt für openDox ab Version 0.8.x
> Diese Zweckbestimmung legt fest, wofür openDox vom Hersteller bestimmt ist
> und wofür nicht. Sie ist die Grundlage der Abgrenzung zum Medizinprodukt
> (Art. 2 Nr. 1 Verordnung (EU) 2017/745, MDR) und ergänzt
> [`DISCLAIMER.md`](../DISCLAIMER.md). Sie ist keine Rechtsberatung; vor dem
> Einsatz im klinischen Umfeld sollte der Betreiber sie rechtlich prüfen
> lassen (siehe Abschnitt 6).

## 1. Bestimmungsgemäßer Zweck

openDox ist eine Software zur **Dokumentationsunterstützung**. Sie wandelt
gesprochene Sprache in Text um (Spracherkennung), kann personenbezogene
Angaben optional maskieren und erstellt aus dem Text mittels Sprachmodell
einen **strukturierten Textentwurf** (z. B. Gesprächs- oder Befunddokumentation)
nach Vorgaben, die der Betreiber je Kategorie festlegt.

Der Zweck beschränkt sich auf das **Erfassen, Umwandeln, Strukturieren und
Ablegen von Text**, den medizinisches Fachpersonal selbst gesprochen hat. Die
inhaltliche Verantwortung für jede Aufzeichnung und jeden Text bleibt
vollständig beim Anwender.

## 2. Anwender und Einsatzumfeld

- **Anwender:** qualifiziertes medizinisches Fachpersonal und von diesem
  beauftragtes Personal (Ärztinnen und Ärzte, Therapeutinnen und Therapeuten,
  medizinische Fachangestellte, Schreibkräfte).
- **Einsatzumfeld:** Praxen, MVZ, Kliniken und vergleichbare Einrichtungen, die
  openDox selbst oder durch einen Dienstleister betreiben (Self-Hosting).
- **Nicht vorgesehen:** Nutzung durch Patientinnen und Patienten oder Laien.

## 3. Funktionsumfang im Rahmen des Zwecks

| Funktion | Beschreibung |
|---|---|
| Aufnahme | Audioaufnahme per Browser oder Desktop-Client ([`client.md`](client.md)), Upload vorhandener Audiodateien |
| Einfügen (Desktop-Client) | Der Anwender bestätigt den Text („Akzeptieren und einfügen“); der Client fügt ihn in das gerade fokussierte Programm ein, in dem der Anwender ihn prüft und selbst speichert |
| Transkription | Live-Text (Parakeet) und finale Transkription (Whisper) |
| Fachbegriff-Korrektur | Phonetischer Abgleich mit Glossaren (Kategorie, persönliches Wörterbuch) |
| PII-Maskierung (optional) | Ersetzen von Namen und Orten durch Platzhalter vor der LLM-Verarbeitung |
| Textentwurf | Sprachmodell strukturiert bzw. bereinigt den Text nach Kategorie-Vorgabe |
| Ablage | Verschlüsselte Speicherung von Text und optional Audio, Archivierung, Export |

## 4. Ausdrücklich nicht bestimmungsgemäß

openDox ist **nicht** dafür bestimmt und darf **nicht** verwendet werden für:

1. die **Diagnose**, Überwachung, Vorhersage, Prognose, Behandlung oder
   Linderung von Krankheiten, Verletzungen oder Behinderungen;
2. die **Entscheidungsfindung** über Diagnostik oder Therapie, einschließlich
   Empfehlungen, Risikobewertungen, Triage oder Dosierungsvorschlägen;
3. die **automatische Übernahme** von Ausgaben in die Patientenakte oder in
   andere Systeme ohne Prüfung durch qualifiziertes Fachpersonal. Der
   Desktop-Client fügt Text nur an der Cursorposition des Zielprogramms ein
   und speichert oder sendet nichts; die Prüfung vor dem Speichern bleibt
   Pflicht des Anwenders;
4. die Ableitung neuer medizinischer Aussagen: openDox soll Gesagtes
   dokumentieren, nicht medizinisch bewerten oder ergänzen;
5. den Einsatz als **alleinige Grundlage** für Behandlungsentscheidungen;
6. Notfall- und Intensivsituationen, in denen eine fehlerhafte oder verzögerte
   Ausgabe unmittelbar die Patientensicherheit gefährden kann.

Kein Funktionsmerkmal von openDox verfolgt einen medizinischen Zweck im Sinne
der MDR. Die Kategorie-Prompts dürfen keine diagnostischen oder
therapeutischen Auswertungen verlangen (siehe Abschnitt 6).

## 5. Pflichten bei der Nutzung

- **Human-in-the-loop:** Jedes Transkript und jede Zusammenfassung ist ein
  maschinell erzeugter Entwurf. Er muss vor Verwendung, Übernahme in die
  Patientenakte oder Weitergabe von qualifiziertem Fachpersonal gelesen,
  geprüft und bei Bedarf korrigiert werden.
- **Bekannte Fehlerquellen:** Spracherkennung und Sprachmodelle können
  Wörter, Zahlen, Dosierungen, Seitenangaben und Negationen falsch wiedergeben
  oder Inhalte erfinden. Das Risiko steigt bei Dialekt, Hintergrundgeräuschen,
  seltenen Fachbegriffen und mehreren Sprechenden.
- **Betreiber:** Wer eine Instanz betreibt, ist für Datenschutz (DSGVO,
  §203 StGB), IT-Sicherheit, Auftragsverarbeitung und die Einhaltung der
  Zweckbestimmung verantwortlich.

### Technische Durchsetzung

Die Abgrenzung wird in der Software nachvollziehbar abgebildet:

- Der Desktop-Client fügt Text nur auf eine Handlung des Anwenders hin ein
  (Button, Hotkey oder Mikrofontaste), nie von selbst. Beim Tastenmikrofon im
  Standardmodus „hold“ ist diese Handlung das Loslassen der Aufnahmetaste; der
  Text landet dann ohne weiteren Klick im Zielprogramm. Der Betreiber kann auf
  „toggle“ umstellen und Zielprogramme auf eine Allow-Liste beschränken
  (Admin → Clients).
- Pflicht-Bestätigung beim ersten Login (`DisclaimerGate.tsx`, in Web-Frontend und Desktop-Client), serverseitig
  mit Zeitstempel in `User.disclaimer_accepted_at` gespeichert; alle Routen
  bleiben bis zur Bestätigung gesperrt.
- Hinweis „Kein Medizinprodukt“ im Aufnahmedialog und in der Transkriptansicht
  in allen Oberflächensprachen.
- Das Sprachmodell wird angewiesen, nichts zu ergänzen und keine Platzhalter
  für fehlende Angaben zu erfinden.

## 6. Änderung des Zwecks und Verantwortung des Betreibers

Die Einstufung als Nicht-Medizinprodukt gilt nur, solange openDox **innerhalb
dieser Zweckbestimmung** eingesetzt wird. Wer openDox abweichend verwendet,
etwa indem er Kategorie-Prompts für diagnostische Auswertungen, Therapie-
vorschläge oder Risikoberechnungen konfiguriert, oder indem er Ausgaben ohne
Prüfung automatisch weiterverarbeitet, gibt dem Produkt damit selbst einen
medizinischen Zweck. In diesem Fall wird der Betreiber nach MDR Art. 16
rechtlich wie ein Hersteller behandelt und muss die Konformitätsbewertung
selbst durchführen. Der ursprüngliche Hersteller und alle Mitwirkenden
übernehmen dafür keine Verantwortung.

Die Software wird ohne Gewährleistung bereitgestellt (AGPL-3.0-or-later,
§§ 15–16).

## 7. Hersteller und Kontakt

Christopher Abanilla · christopher.abanilla@gmx.de
Lizenz: AGPL-3.0-or-later · Quellcode: <https://github.com/daemolition/openDox>

## Verwandte Dokumente

- [`DISCLAIMER.md`](../DISCLAIMER.md): Haftungs- und Regulierungshinweis
- [`docs/hospital-audit-frameworks.md`](hospital-audit-frameworks.md) §8: Abgrenzung zur MDR
- [`docs/data-mapping.md`](data-mapping.md): Datenfluss und DSGVO
- [`docs/client.md`](client.md): Funktionsweise des Desktop-Clients
