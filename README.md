# Projekt Red: Medizinische Transkriptionsplattform

## Über das Projekt
**Projekt Red** ist eine moderne medizinische Transkriptionsplattform, die auf **Python (FastAPI)** und **React mit Tailwind CSS** basiert. Sie ermöglicht die automatisierte und manuelle Transkription von Audioaufnahmen für medizinische Zwecke, wie z. B. Arzt-Patienten-Gespräche oder Aufzeichnungen in Kliniken.

### Technologiestack
- **Backend**: Python + FastAPI (für API-Endpunkte und Dienstleistungen)
- **Frontend**: React mit TypeScript, Tailwind CSS und Radix UI für UI-Komponenten
- **Dienstleistungen**: Integration von Sprachmodellen wie Whisper für automatische Transkription
- **Einstellungen & Benutzerfreundlichkeit**: Dark Mode, Konfiguration der Whisper-Einstellungen und moderne UI/UX-Erlebnisse

### Kernfunktionen
1. **Automatisierte Transkription** mit Whisper-Modellen (z. B. Small, Base, Large)
2. **Manuelle Bearbeitung** für präzisere Ergebnisse
3. **Medizinische Sicherheit**: Datenschutz und Konformität mit medizinischen Standards
4. **Einstellungen & Anpassungen**: Geräteauswahl, Sprachmodelle, Temperatur-Einstellungen
5. **Modernisierte UI/UX**: Intuitives Bedienfeld, Dark Mode und verbesserte Komponenten wie Dropdowns und Dialoge
6. **Backend-Integration**: API für flexible Integration in bestehende Systeme

### Entwicklung & Deployment
- **Entwicklung**: Start mit `uvicorn app.main:app --reload` (Backend) oder `npm run dev` (Frontend)
- **Deployment**: Über Lovable oder lokale Umgebungen mit Node.js und npm
- **Technische Dokumentation**: Alle Änderungen sind in `HISTORY.md` und `TASK.md` dokumentiert

### Aktuelle Entwicklungen
Das Projekt umfasst eine Reihe von Verbesserungen, darunter:
- **UI/UX Modernisierung** (z. B. Dark Mode, verbesserte Komponenten wie Buttons, Inputs und Dropdowns)
- **Whisper-Konfiguration** mit Auswahlmöglichkeiten für Geräte, Modelle und Sprachen
- **Medizinische Sicherheit**: Datenschutz und Konformität in den Einstellungen
- **Bugfixes** für Interaktionsprobleme (z. B. korrekte Dialogfunktionalität)

### Wie du das Projekt nutzt
1. Klone das Repository oder arbeite direkt mit Lovable.
2. Installiere die Abhängigkeiten mit `npm install` und starte den Entwicklungsserver mit `npm run dev`.
3. Nutze die Plattform für medizinische Transkriptionen und passe Einstellungen nach Bedarf an.

Wir freuen uns auf deine Feedback und Zusammenarbeit!