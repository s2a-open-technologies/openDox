# Screenshot-Liste

Alle Bilder, die die Handbücher referenzieren. Fehlende Dateien ersetzt
`scripts/build_handbuch.sh` beim Bauen durch einen grauen Platzhalter.

**Konventionen**

- PNG, Browserfenster ca. 1440 × 900, Zoom 100 %, helles Design.
- Nur Demo-Daten: keine echten Patienten-, Personen- oder Servernamen,
  keine echten IP-Adressen, API-Keys oder Passwörter.
- Dateiname exakt wie unten, Ablage unter `docs/handbuch/<Pfad>`.
- Ausschnitt statt Vollbild, wenn nur ein Dialog gemeint ist.

## Benutzerhandbuch

| Datei | Was zu sehen ist | Rolle |
|---|---|---|
| `bilder/benutzer/01-anmeldung.png` | Anmeldeseite, idealerweise mit SSO-Schaltfläche | Benutzer |
| `bilder/benutzer/02-hinweis-erstanmeldung.png` | Dialog „Kein Medizinprodukt“ bei Erstanmeldung | Benutzer (neues Konto) |
| `bilder/benutzer/03-uebersicht.png` | Hauptansicht: Seitenleiste mit einigen Aufnahmen, eine fertige Aufnahme geöffnet | Benutzer |
| `bilder/benutzer/04-neue-aufnahme.png` | Dialog „Neue Aufnahme“ mit Titel und Kategorie | Benutzer |
| `bilder/benutzer/05-aufnahme-laeuft.png` | Laufende Aufnahme mit Live-Vorschau, Pause/Stopp sichtbar | Benutzer |
| `bilder/benutzer/05a-aufnahme-laeuft.png` | Laufende Aufnahme ohne Live-Vorschau, Pause/Stopp sichtbar | Benutzer |
| `bilder/benutzer/06-audio-hochladen.png` | Dialog „Audio hochladen“ | Benutzer |
| `bilder/benutzer/07-transkript.png` | Fertige Aufnahme: Transkript, Zusammenfassung, Hinweis, Bestätigungshaken | Benutzer |
| `bilder/benutzer/08-zeilenmenue.png` | Geöffnetes Zeilenmenü einer Aufnahme (Archivieren/Löschen) | Benutzer |
| `bilder/benutzer/09-meine-kategorien.png` | Profil → Meine Kategorien mit ausgefülltem Formular, ein globales Wörterbuch angehakt | Benutzer |
| `bilder/benutzer/10-profil.png` | Profil-Dialog, Tab „Meine Wörterbücher“ mit einem geöffneten Wörterbuch und Beispielbegriffen | Benutzer |

## Administrationshandbuch

| Datei | Was zu sehen ist | Rolle |
|---|---|---|
| `bilder/administration/01-administration.png` | Administration geöffnet, Navigation links vollständig sichtbar (Bereich „Dienste“) | Administrator |
| `bilder/administration/02-whisper-allgemein.png` | Dienste → Whisper / ASR → Allgemein, Sprache „Deutsch“ | Administrator |
| `bilder/administration/03-whisper-live.png` | Dienste → Whisper / ASR → Live mit Parakeet, Endpoint, Testergebnis „Erreichbar“ | Administrator |
| `bilder/administration/04-whisper-final.png` | Dienste → Whisper / ASR → Final mit Fachbegriff-Korrektur an, Schwellenwert 85 | Administrator |
| `bilder/administration/05-llm.png` | Dienste → LLM mit Testergebnis „Verbunden“, darunter PII-Sanitizer | Administrator |
| `bilder/administration/06-kategorien.png` | Kategorien: Liste und Formular einer globalen Kategorie mit angehaktem Wörterbuch | Administrator |
| `bilder/administration/07-woerterbuecher.png` | Wörterbücher: Liste mit Begriffs-/Kategorienzahl, ein Wörterbuch geöffnet, Upload-Bereich | Administrator |
| `bilder/administration/08-archivierung.png` | Archivierung: Audio-Download, Auto-Archivierung, Liste fehlgeschlagener Transkriptionen mit einem Eintrag | Administrator |
| `bilder/administration/09-benutzer.png` | Benutzerliste mit mehreren Rollen, Dialog „Benutzer bearbeiten“ | Administrator |
| `bilder/administration/10-ldap.png` | Authentifizierung → LDAP mit Beispielwerten (Demo-Domain), ohne echtes Passwort | Administrator |
| `bilder/administration/11-oidc.png` | Authentifizierung → OIDC / SSO mit Beispielwerten, Client Secret leer/maskiert | Administrator |
| `bilder/administration/12-clients.png` | Clients: Installer-Links, settings.json, Intune/SCCM-Befehle, Client-Einstellungen | Administrator |
| `bilder/administration/13-backup.png` | Backup: Export und Wiederherstellung | Administrator |
| `bilder/administration/14-system.png` | System: alle Dienste mit Status | Administrator |

## Installations- und Betriebshandbuch

| Datei | Was zu sehen ist | Rolle |
|---|---|---|
| `bilder/installation/01-architektur.png` | Diagramm: Browser/Client → Reverse Proxy → app → postgres/redis/whisper/parakeet/garage, extern LLM und PII-Sanitizer | – (Grafik) |
| `bilder/installation/02-systemstatus.png` | Administration → System direkt nach der Installation, alle Dienste online | Administrator |
