# Screenshot-Liste

Alle Bilder, die die Handbücher referenzieren. Fehlende Dateien ersetzt
`scripts/build_handbuch.sh` beim Bauen durch einen grauen Platzhalter.

**Konventionen**

- PNG, Browserfenster ca. 1440 × 900, Zoom 100 %, helles Design.
- Nur Demo-Daten: keine echten Patienten-, Personen- oder Servernamen,
  keine echten IP-Adressen, API-Keys oder Passwörter.
- Kategorien: nur die mitgelieferte Kategorie „Standard“. Eigene Prompts
  liegen außerhalb dessen, was die Zweckbestimmung abdeckt, und gehören nicht
  in die Handbuch-Bilder.
- Dateiname exakt wie unten, Ablage unter `docs/handbuch/<Pfad>`.
- Ausschnitt statt Vollbild, wenn nur ein Dialog gemeint ist. Lange Einstellungsseiten
  nicht als Ganzes, sondern als Ausschnitt der jeweiligen Karte(n), damit die Schrift im
  PDF lesbar bleibt (Abbildungen werden auf höchstens 20 cm Höhe verkleinert).

## Benutzerhandbuch

| Datei | Was zu sehen ist | Rolle |
|---|---|---|
| `bilder/benutzer/01-anmeldung.png` | Anmeldeseite, idealerweise mit SSO-Schaltfläche | Benutzer |
| `bilder/benutzer/02-hinweis-erstanmeldung.png` | Dialog „Kein Medizinprodukt“ bei Erstanmeldung | Benutzer (neues Konto) |
| `bilder/benutzer/03-uebersicht.png` | Hauptansicht: Seitenleiste mit einigen Aufnahmen, eine fertige Aufnahme geöffnet | Benutzer |
| `bilder/benutzer/04-neue-aufnahme.png` | Dialog „Neue Aufnahme“ mit Titel, Kategorie „Standard“ und Diktiersprache „Arabisch“ (Hinweise Übersetzung und keine Live-Vorschau sichtbar) | Benutzer mit Übersetzungsfreigabe |
| `bilder/benutzer/05-aufnahme-laeuft.png` | Laufende Aufnahme mit Live-Vorschau, Pause/Stopp sichtbar | Benutzer |
| `bilder/benutzer/05a-aufnahme-laeuft.png` | Laufende Aufnahme ohne Live-Vorschau, Pause/Stopp sichtbar | Benutzer |
| `bilder/benutzer/06-audio-hochladen.png` | Dialog „Audio hochladen“ mit Diktiersprache „Russisch“ | Benutzer mit Übersetzungsfreigabe |
| `bilder/benutzer/07-transkript.png` | Fertige Aufnahme: Transkript, Zusammenfassung, Hinweis, Bestätigungshaken | Benutzer |
| `bilder/benutzer/08-zeilenmenue.png` | Geöffnetes Zeilenmenü einer Aufnahme (Archivieren/Löschen) | Benutzer |
| `bilder/benutzer/09-meine-kategorien.png` | Ausschnitt: Formular „Neue Kategorie erstellen“ (Profil → Meine Kategorien), ein globales Wörterbuch angehakt, ein eigenes als „Eigen · automatisch“ (vorher unter Kategorien *Benutzerkategorien erlauben* einschalten) | Benutzer |
| `bilder/benutzer/11-uebersetzung.png` | Übersetzte Aufnahme: „Transkript (Original: Russisch)“ links, Reiter „Übersetzung“ mit Satzpaaren rechts, ein Satz mit abweichender Zahl gelb markiert | Benutzer mit Übersetzungsfreigabe |
| `bilder/benutzer/10-profil.png` | Profil-Dialog, Tab „Meine Wörterbücher“ mit einem geöffneten Wörterbuch und Beispielbegriffen | Benutzer |

## Administrationshandbuch

| Datei | Was zu sehen ist | Rolle |
|---|---|---|
| `bilder/administration/01-administration.png` | Administration geöffnet, Navigation links vollständig sichtbar (Bereich „Dienste“) | Administrator |
| `bilder/administration/02-whisper-allgemein.png` | Dienste → Whisper / ASR → Allgemein, Sprache „Deutsch“ | Administrator |
| `bilder/administration/03-whisper-live.png` | Dienste → Whisper / ASR → Live mit Parakeet, Endpoint, Testergebnis „Erreichbar“ | Administrator |
| `bilder/administration/04-whisper-final.png` | Dienste → Whisper / ASR → Final mit Fachbegriff-Korrektur an, Schwellenwert 85 | Administrator |
| `bilder/administration/05-llm.png` | Ausschnitt: Dienste → LLM, Karten „LLM-Verarbeitung“ und „LLM / Ollama Konfiguration“ | Administrator |
| `bilder/administration/05b-pii-sanitizer.png` | Ausschnitt: Karte „PII-Sanitizer“ mit Buttons und Testergebnis „Verbunden“ | Administrator |
| `bilder/administration/06-kategorien.png` | Ausschnitt: Kategorien, Schalter *Benutzerkategorien erlauben* und Kategorienliste mit nur der mitgelieferten Kategorie „Standard“ (Schloss und Stern) | Administrator |
| `bilder/administration/06b-kategorie-formular.png` | Ausschnitt: Formular „Kategorie bearbeiten“ der Kategorie „Standard“ mit Schreibschutz-Hinweis und angehaktem Wörterbuch | Administrator |
| `bilder/administration/07-woerterbuecher.png` | Ausschnitt: Wörterbücher, Liste mit Begriffs-/Kategorienzahl, ein Wörterbuch geöffnet bis „Speichern“ (ohne Upload-Bereich) | Administrator |
| `bilder/administration/08-archivierung.png` | Ausschnitt: Archivierung, Karte „Audio-Download“ | Administrator |
| `bilder/administration/08b-auto-archivierung.png` | Ausschnitt: Karte „Auto-Archivierung“ | Administrator |
| `bilder/administration/08c-automatisches-loeschen.png` | Ausschnitt: Karte „Automatisches Löschen“ mit Warnhinweis | Administrator |
| `bilder/administration/09-benutzer.png` | Dialog „Benutzer bearbeiten“ mit Schalter „Übersetzung freigeben“ | Administrator |
| `bilder/administration/10-ldap.png` | Ausschnitt: LDAP-Karte von „LDAP Konfiguration“ bis Suchfilter, Beispielwerte (Demo-Domain), SSL an | Administrator |
| `bilder/administration/10b-ldap-gruppen.png` | Ausschnitt: LDAP-Karte von „Verschachtelte Gruppen“ bis zu den Buttons, ohne echtes Passwort | Administrator |
| `bilder/administration/11-oidc.png` | Authentifizierung → OIDC / SSO mit Beispielwerten, Client Secret leer/maskiert | Administrator |
| `bilder/administration/12-clients.png` | Ausschnitt: Karte „Client verteilen“ (Installer-Links, settings.json, Intune/SCCM-Befehle), Demo-Serveradresse | Administrator |
| `bilder/administration/12b-client-einstellungen.png` | Ausschnitt: Karte „Client-Einstellungen“ | Administrator |
| `bilder/administration/13-backup.png` | Backup: Export und Wiederherstellung | Administrator |
| `bilder/administration/14-system.png` | System: alle Dienste mit Status und Karte „Sicherheit“ (Verschlüsselungsschlüssel) | Administrator |
| `bilder/administration/15-uebersetzung.png` | Ausschnitt: Karte „Übersetzung“ eingeschaltet, Zugriff „Ausgewählte Benutzer“, Diktiersprachen | Administrator |

## Installations- und Betriebshandbuch

| Datei | Was zu sehen ist | Rolle |
|---|---|---|
| `bilder/installation/01-architektur.png` | Diagramm: Browser/Client → Reverse Proxy → app → postgres/redis/whisper/parakeet/garage, extern LLM und PII-Sanitizer. Quelle: `01-architektur.dot` daneben (Graphviz, Befehl im Dateikopf) | – (Grafik) |
| `bilder/installation/02-systemstatus.png` | Ausschnitt: Karte „Systemstatus“ direkt nach der Installation, Pflichtdienste online (optionale dürfen „Deaktiviert“ sein) | Administrator |
