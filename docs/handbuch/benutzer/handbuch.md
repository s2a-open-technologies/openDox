---
title: "openDox"
subtitle: "Benutzerhandbuch"
---

# Über dieses Handbuch

Dieses Handbuch richtet sich an alle, die mit openDox Diktate aufnehmen und
Transkripte bearbeiten: Ärztinnen und Ärzte, Pflege- und Assistenzpersonal,
Schreibkräfte. Es beschreibt die Weboberfläche aus Sicht der Rolle
**Benutzer**. Einstellungen, die nur Administratoren vornehmen können, stehen
im *Administrationshandbuch*; Installation und Betrieb im *Installations- und
Betriebshandbuch*.

Bezeichnungen von Schaltflächen, Menüs und Feldern sind im Text **fett**
gesetzt und entsprechen der deutschen Oberfläche.

## Wichtiger Hinweis: Kein Medizinprodukt

openDox ist **kein zugelassenes Medizinprodukt** gemäß Medizinproduktegesetz
(MPG) oder vergleichbaren Regularien (z. B. EU-MDR, FDA). Es dient
ausschließlich der Unterstützung bei der Dokumentation.

Alle maschinell erstellten Transkriptionen und Zusammenfassungen müssen von
qualifiziertem Fachpersonal überprüft werden, bevor sie verwendet oder in
eine Patientenakte übernommen werden. openDox ersetzt keine ärztliche
Diagnose, Beratung oder Therapieempfehlung.

Spracherkennung und KI-Zusammenfassung arbeiten nicht fehlerfrei. Typische
Fehler sind falsch erkannte Fachbegriffe, Medikamentennamen, Dosierungen und
Zahlen, vertauschte Seitenangaben (links/rechts) sowie ausgelassene oder
hinzugefügte Inhalte in der Zusammenfassung. Prüfen Sie diese Stellen
besonders sorgfältig.

## Was openDox macht

openDox wandelt gesprochene Diktate in Text um und erstellt daraus eine
strukturierte Zusammenfassung:

1. **Aufnahme:** Sie diktieren im Browser oder im Desktop-Client. Während
   Sie sprechen, erscheint eine Live-Vorschau des Textes.
2. **Transkription:** Nach dem Beenden wird die vollständige Aufnahme ein
   zweites Mal und genauer verschriftlicht. Dieser Text ist das *Transkript*.
3. **Zusammenfassung:** Eine KI formt das Transkript nach den Vorgaben der
   gewählten **Kategorie** um, z. B. in einen Arztbrief-Abschnitt oder einen
   strukturierten Befund.

Die Live-Vorschau ist nicht das endgültige Ergebnis. Maßgeblich sind das
Transkript und die Zusammenfassung, die nach der Verarbeitung angezeigt
werden.

# Erste Schritte

## Voraussetzungen

- Ein aktueller Browser (Chrome, Edge, Firefox oder Safari).
- Ein Mikrofon. Ein Headset oder Diktiermikrofon liefert deutlich bessere
  Ergebnisse als ein eingebautes Laptop-Mikrofon.
- Die Adresse Ihrer openDox-Installation (erhalten Sie von Ihrer IT) und
  Ihre Zugangsdaten.

Der Browser erlaubt den Zugriff auf das Mikrofon nur über eine sichere
Verbindung (Adresse beginnt mit `https://`). Erscheint keine Abfrage zur
Mikrofonfreigabe, wenden Sie sich an Ihre IT.

## Anmelden

Öffnen Sie die Adresse von openDox im Browser.

![Anmeldeseite](bilder/benutzer/01-anmeldung.png)

Je nach Einrichtung melden Sie sich auf eine von zwei Arten an:

- **Mit Benutzername und Passwort:** Geben Sie **Username** und **Passwort**
  ein und klicken Sie auf **Anmelden**. Das kann ein eigenes openDox-Konto oder
  Ihr gewohntes Windows-/Netzwerk-Konto sein (LDAP/Active Directory).
- **Mit Single Sign-On:** Ist die Schaltfläche **Mit Single Sign-On
  anmelden** sichtbar, werden Sie zur Anmeldeseite Ihrer Organisation
  weitergeleitet und danach automatisch zurück zu openDox.

Schlägt die Anmeldung fehl, prüfen Sie Benutzername und Passwort. Bei
Netzwerk-Konten entscheidet die Gruppenzugehörigkeit, ob Sie openDox nutzen
dürfen; ist Ihr Konto nicht freigeschaltet, hilft Ihre IT.

## Hinweis bei der ersten Anmeldung bestätigen

Bei der ersten Anmeldung zeigt openDox den Hinweis **Kein Medizinprodukt**.
Lesen Sie ihn, setzen Sie den Haken bei *„Ich habe den Hinweis gelesen und
verstanden …“* und klicken Sie auf **Bestätigen**. Ohne diese Bestätigung
lässt sich openDox nicht verwenden. Die Bestätigung wird zu Ihrem Konto
gespeichert und nur einmal abgefragt.

![Hinweis bei der ersten Anmeldung](bilder/benutzer/02-hinweis-erstanmeldung.png)

## Die Oberfläche im Überblick

![Hauptansicht mit Seitenleiste und Transkript](bilder/benutzer/03-uebersicht.png)

- **Seitenleiste (links):** Ihre Aufnahmen, aufgeteilt in **Aktuell** und
  **Archiv**, sowie **Audio hochladen**.
- **Arbeitsbereich (Mitte):** die gerade geöffnete Aufnahme mit Transkript und
  Zusammenfassung, oder die Schaltfläche **Neue Aufnahme starten**.
- **Benutzermenü (Ihr Name):** **Profil**, bei entsprechender Berechtigung
  **Administration**, und **Abmelden**.

Auf dem Smartphone ist die Seitenleiste eingeklappt und über das Menüsymbol
(**Menü öffnen**) erreichbar.

## Automatische Abmeldung

Arbeiten Sie eine Zeit lang nicht mit openDox, meldet es Sie ab (Ihre
Administration legt fest, nach wie vielen Minuten; üblich sind 30). Sie sehen
dann die Anmeldeseite mit einem Hinweis. Während einer Aufnahme und solange
die Transkription läuft, werden Sie nie abgemeldet. Melden Sie sich trotzdem
selbst über **Abmelden** ab, wenn Sie einen gemeinsam genutzten Rechner
verlassen.

# Eine Aufnahme erstellen

## Neue Aufnahme anlegen

1. Klicken Sie auf **Neue Aufnahme starten**.
2. Geben Sie einen **Titel** ein, z. B. *Anamnese Zimmer 12*. Verwenden Sie
   im Titel möglichst keine vollständigen Patientennamen, wenn Ihre
   Einrichtung das nicht ausdrücklich vorsieht.
3. Wählen Sie eine **Kategorie**. Vorausgewählt ist **Allgemein**. Die
   Kategorie bestimmt, wie die Zusammenfassung aufgebaut wird und welche
   globalen Wörterbücher gelten (siehe Kapitel *Kategorien*). Ihre eigenen
   Wörterbücher gelten immer.
4. Klicken Sie auf **Aufnahme starten**.

![Dialog „Neue Aufnahme“](bilder/benutzer/04-neue-aufnahme.png)

Erscheint der Hinweis *„Legen Sie zuerst eine Kategorie unter Einstellungen
an.“*, ist noch keine Kategorie verfügbar. Legen Sie unter **Profil → Meine
Kategorien** eine eigene an oder bitten Sie Ihre Administration darum.

## Diktieren

Beim ersten Start fragt der Browser, ob openDox das Mikrofon verwenden darf.
Erlauben Sie den Zugriff.

![Laufende Aufnahme mit Live-Vorschau](bilder/benutzer/05-aufnahme-laeuft.png)

- **Starten:** Klicken Sie auf das Mikrofon. Der Status wechselt zu
  **Aufnahme läuft...**.
- **Pausieren und fortsetzen:** Mit der Pause-Taste unterbrechen Sie die
  Aufnahme, mit der Play-Taste setzen Sie sie fort. In der Pause wird nichts
  aufgezeichnet.
- **Beenden:** Klicken Sie auf die Stopp-Taste und bestätigen Sie
  **Aufnahme beenden**. Die Aufnahme wird gespeichert und verarbeitet.
- **Abbrechen:** Mit **Abbrechen** wird die Aufnahme verworfen. Das lässt
  sich nicht rückgängig machen.

Während Sie sprechen, erscheint der erkannte Text als **Live-Vorschau**. Sie
dient nur der Orientierung. Ist die Live-Vorschau in Ihrer Installation
abgeschaltet oder vorübergehend nicht verfügbar, läuft die Aufnahme trotzdem
weiter, und das Ergebnis nach dem Beenden ist davon nicht betroffen.

Ohne Livevorschau wird die Aufnahme in Form eines Orbs dargestellt.
![Laufende Aufnahme ohne Live-Vorschau](bilder/benutzer/05b-aufnahme-laeuft.png)

## Tipps für gute Ergebnisse

- Sprechen Sie in normalem Tempo und gleichmäßiger Lautstärke, mit einer
  Handbreit Abstand zum Mikrofon.
- Diktieren Sie Satzzeichen nicht; Punkt und Komma setzt openDox selbst.
- Buchstabieren Sie seltene Namen und Begriffe nicht, sondern tragen Sie sie
  einmal in eines Ihrer Wörterbücher ein (siehe *Meine Wörterbücher*).
- Kurze Denkpausen sind kein Problem. Längere Pausen nutzen Sie besser mit der
  Pause-Taste.
- Vermeiden Sie Hintergrundgespräche; openDox verschriftlicht alles, was das
  Mikrofon hört.

## Unterbrochene Aufnahme fortsetzen

Wird der Browser während einer Aufnahme geschlossen oder bricht die
Verbindung ab, zeigt openDox beim nächsten Öffnen **Unfertige Aufnahme**:

- **Fortsetzen** nimmt die Aufnahme an der unterbrochenen Stelle wieder auf;
  der bisher aufgezeichnete Ton bleibt erhalten.
- **Verwerfen** löscht die unterbrochene Aufnahme.

Eine unfertige Aufnahme kann etwa 30 Minuten lang fortgesetzt werden.
Danach wird sie automatisch entfernt.

## Audiodatei hochladen

Statt live zu diktieren, können Sie eine fertige Audiodatei verarbeiten
lassen, z. B. von einem Diktiergerät:

1. Klicken Sie in der Seitenleiste auf **Audio hochladen**.
2. Optional: Geben Sie einen **Titel** ein.
3. Wählen Sie Kategorie und **Audiodatei** und klicken Sie auf
   **Hochladen**.

![Dialog „Audio hochladen“](bilder/benutzer/06-audio-hochladen.png)

Die Datei durchläuft danach dieselbe Verarbeitung wie eine Live-Aufnahme.

# Ergebnis prüfen und übernehmen

## Verarbeitung abwarten

Nach dem Beenden zeigt openDox zuerst **Transkription läuft...** und danach
**KI erstellt Zusammenfassung...**. Je nach Länge der Aufnahme und Auslastung
des Servers dauert das wenige Sekunden bis einige Minuten. Sie können in
dieser Zeit weitere Aufnahmen beginnen oder andere Aufnahmen öffnen.

Ist die Verarbeitung abgeschlossen, trägt die Aufnahme das Kennzeichen
**Fertig**. Bei **Fehler** konnte die Aufnahme nicht verarbeitet werden;
melden Sie das bitte Ihrer Administration, die fehlgeschlagene
Transkriptionen erneut anstoßen kann. Die Aufnahme geht dabei in der Regel
nicht verloren.

## Transkript und Zusammenfassung

![Aufnahme mit Transkript, Zusammenfassung und Hinweis](bilder/benutzer/07-transkript.png)

Eine fertige Aufnahme zeigt zwei Bereiche:

- **Transkript:** der wörtlich verschriftlichte Text Ihres Diktats.
- **Zusammenfassung:** der von der KI nach den Vorgaben der Kategorie
  aufbereitete Text.

Darunter steht der Hinweis **Kein Medizinprodukt**.

## Prüfen und bestätigen

Bevor Sie Text kopieren oder bearbeiten können, setzen Sie den Haken bei
*„Ich habe den Text sorgfältig überprüft und ggf. korrigiert. Ich übernehme
die Verantwortung für den kopierten Inhalt.“* und bestätigen im Dialog
**Verantwortung übernehmen**. Solange der Haken fehlt, sind **Kopieren** und
**Bearbeiten** gesperrt (*„Bitte zuerst Bestätigungshaken setzen“*).

Lesen Sie Transkript und Zusammenfassung vollständig, bevor Sie bestätigen.
Vergleichen Sie insbesondere Medikamente, Dosierungen, Zahlen, Seitenangaben
und Diagnosen mit dem, was Sie diktiert haben.

## Text bearbeiten

- **Transkript:** direkt im Textfeld ändern.
- **Zusammenfassung:** mit **Bearbeiten** in den Bearbeitungsmodus wechseln,
  mit **Vorschau** zurück zur formatierten Ansicht. Die Zusammenfassung ist
  im Markdown-Format geschrieben (z. B. `**fett**`, Aufzählungen mit `-`).

Klicken Sie auf **Speichern**, um Ihre Änderungen zu sichern. Solange Sie
nicht gespeichert haben, zeigt openDox *„Ungespeicherte Änderungen
vorhanden“*.

## Text übernehmen

Mit **Kopieren** übernehmen Sie das Transkript, mit dem Kopiersymbol in der
Zusammenfassung die Zusammenfassung in die Zwischenablage. Fügen Sie den Text
anschließend in Ihr Praxis- oder Kliniksystem ein.

## Zusammenfassung neu erstellen oder Kategorie wechseln

- Mit **Zusammenfassung neu generieren** lässt die KI die Zusammenfassung aus
  dem aktuellen Transkript neu erstellen, z. B. nachdem Sie das Transkript
  korrigiert haben. Eine von Ihnen bearbeitete Zusammenfassung wird dabei
  ersetzt.
- Über das Auswahlfeld **Kategorie** im Kopf der Aufnahme können Sie die
  Kategorie nachträglich ändern und anschließend die Zusammenfassung neu
  generieren.

## Audio herunterladen

Ist die Aufbewahrung von Aufnahmen in Ihrer Installation eingeschaltet,
erscheint die Schaltfläche **Audio**. Damit laden Sie die Aufnahme als
Audiodatei herunter, etwa um eine Stelle nachzuhören. Behandeln Sie die
Datei wie jede andere Patientenunterlage.

# Aufnahmen verwalten

## Aktuell und Archiv

In der Seitenleiste stehen unter **Aktuell** Ihre laufenden und neuen
Aufnahmen. Über das Menü einer Zeile können Sie eine Aufnahme:

- **Archivieren:** Sie verschwindet aus **Aktuell** und liegt im **Archiv**.
- **Löschen:** Die Aufnahme wird nach Rückfrage unwiderruflich gelöscht.

![Zeilenmenü einer Aufnahme](bilder/benutzer/08-zeilenmenue.png)

Unter **Archiv** sind die archivierten Aufnahmen nach Tagen gruppiert
(**Heute**, **Gestern**, Datum). Wählen Sie einen Tag, um die Aufnahmen
dieses Tages zu sehen. Mit **Wiederherstellen** holen Sie eine Aufnahme
zurück nach **Aktuell**.

Ihre Administration kann einstellen, dass Aufnahmen nach einer bestimmten
Anzahl von Tagen automatisch archiviert werden. Archivierte Aufnahmen bleiben
jederzeit wiederherstellbar.

Außerdem kann Ihre Administration eine Frist festlegen, nach der Aufnahmen
**automatisch gelöscht** werden, auch archivierte. Gelöschte Aufnahmen lassen
sich nicht wiederherstellen. Übernehmen Sie Ihre Texte daher rechtzeitig in
die Patientendokumentation. Wie lange Ihre Aufnahmen höchstens aufbewahrt
werden, sehen Sie im Profil unter **Aufbewahrung**.

## Wer sieht meine Aufnahmen?

Ihre Aufnahmen, Transkripte und Zusammenfassungen sind Ihrem Konto
zugeordnet und nur für Sie zugänglich. Weder andere Benutzer noch
Administratoren können sie öffnen, herunterladen oder löschen. Die Inhalte
werden verschlüsselt gespeichert. Die Rohaufnahme des Diktats wird nach erfolgreicher
Verarbeitung automatisch gelöscht, sofern Ihre Installation keine
Aufbewahrung für den Audio-Download vorsieht.

# Kategorien

Eine Kategorie legt fest, wie openDox Ihr Diktat verarbeitet:

- welche Fachbegriffe bei der Spracherkennung bevorzugt werden,
- welche globalen Wörterbücher für die automatische Korrektur von
  Fachbegriffen gelten (Ihre eigenen gelten ohnehin immer),
- wie die Zusammenfassung aufgebaut wird (z. B. Gliederung, Stil, Länge).

Es gibt zwei Arten:

- **Global:** von der Administration für alle bereitgestellt.
- **Eigene Kategorie:** von Ihnen angelegt und nur für Sie sichtbar.

## Eigene Kategorie anlegen

Öffnen Sie **Profil → Meine Kategorien**.

![Eigene Kategorie anlegen](bilder/benutzer/09-meine-kategorien.png)

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **Kategorie Name** | Name in der Auswahlliste, z. B. *Entlassbrief Innere*. |
| **Beschreibung** | Kurze Erklärung für Sie selbst. |
| **System Prompt (LLM)** | Anweisung an die KI, wie die Zusammenfassung aussehen soll. |
| **Transkriptions-Hint (Whisper)** | Wenige typische Fachbegriffe und Namen als Hilfe für die Spracherkennung. Nur die letzten rund 224 Tokens werden berücksichtigt, also kurz halten. Optional. |
| **Wörterbücher** | Haken Sie die globalen Wörterbücher an, deren Begriffe nach der Transkription automatisch korrigiert werden. Ihre eigenen Wörterbücher erscheinen hier nicht, weil sie ohnehin für alle Ihre Aufnahmen gelten (siehe *Meine Wörterbücher*). |

Klicken Sie auf **Erstellen**. Bestehende Kategorien ändern Sie mit
**Bearbeiten** und **Aktualisieren**.

Ob die Wörterbücher tatsächlich angewendet werden, hängt davon ab, ob Ihre
Administration die Fachbegriff-Korrektur eingeschaltet hat.

## Beispiel für einen System Prompt

> Erstelle aus dem Diktat einen Befundbericht mit den Abschnitten
> Anamnese, Befund, Beurteilung und Procedere. Schreibe in sachlichem,
> ärztlichem Stil, in vollständigen Sätzen, ohne Inhalte hinzuzufügen, die
> nicht diktiert wurden. Fehlt eine Angabe, lass den Abschnitt weg.

Formulieren Sie konkret: Abschnitte, Reihenfolge, Stil und was die KI *nicht*
tun soll. Testen Sie eine neue Kategorie mit einigen Probediktaten und passen
Sie den Text an, bis das Ergebnis stimmt.

# Profil und persönliche Einstellungen

Öffnen Sie über Ihren Namen das Menü **Profil**.

![Profil-Dialog](bilder/benutzer/10-profil.png)

## Sprache

Unter **Sprache** wählen Sie die Sprache der Oberfläche. Die Einstellung gilt
auf allen Ihren Geräten. Sie betrifft nur die Bedienoberfläche, nicht die
Sprache, in der diktiert wird.

## Meine Wörterbücher

Ein Wörterbuch ist eine Liste von Begriffen, die bei der Erkennung häufig
falsch geschrieben werden: Medikamente, Eigennamen, Abkürzungen, Namen von
Kolleginnen und Kollegen. Nach der Transkription ersetzt openDox ähnlich
klingende Wörter automatisch durch die Schreibweise aus dem Wörterbuch.

Ihre eigenen Wörterbücher gelten automatisch für alle Ihre Aufnahmen, egal in
welcher Kategorie Sie diktieren; Sie müssen sie nirgends anhängen. Globale
Wörterbücher wirken dagegen nur in den Kategorien, an die sie angehängt sind.
Ihre eigenen Wörterbücher sind nur für Sie sichtbar, auch nicht für
Administratoren. Globale Wörterbücher stellt Ihre Administration bereit.

1. Öffnen Sie **Profil → Meine Wörterbücher**.
2. Geben Sie einen Namen ein und klicken Sie auf **Anlegen**.
3. Tragen Sie Begriffe einzeln ein (**Hinzufügen**) und klicken Sie auf
   **Speichern**, oder laden Sie eine Datei hoch (siehe unten). Ab der nächsten
   Aufnahme wird das Wörterbuch angewendet.

Lange Listen zeigt openDox nur auszugsweise an; über das Suchfeld finden Sie
jeden Begriff.

**Dateiformat für den Upload**

- Datei `.txt` oder `.csv`, Zeichenkodierung UTF-8, höchstens 5 MB.
- Ein Begriff pro Zeile. Leere Zeilen und Zeilen, die mit `#` beginnen,
  werden ignoriert. Kommas innerhalb eines Begriffs bleiben erhalten.
- Bei `.csv` zählt die erste Spalte (Trennzeichen `;` oder `,`). Eine
  Kopfzeile kommentieren Sie mit `#` aus.
- Doppelte Begriffe werden entfernt. Höchstens 50.000 Begriffe mit je bis zu
  200 Zeichen.
- **Anhängen** ergänzt die vorhandene Liste, **Ersetzen** tauscht sie aus.

Beispiel `meine-begriffe.txt`:

```
# Medikamente
Sertralin
Metformin
Dr. Okonkwo
Ductus Botalli
Hypertonie, essentiell
```

## Meine Kategorien

Hier verwalten Sie Ihre eigenen Kategorien, unabhängig von Ihrer Rolle (auch
Administratoren legen hier persönliche Kategorien an; globale Kategorien
verwalten sie unter **Administration**). Siehe Kapitel *Kategorien*.

## Aufbewahrung

Unter **Aufbewahrung** sehen Sie, nach wie vielen Tagen Ihre Einrichtung
Aufnahmen spätestens löscht. Bei **Eigene Aufnahmen löschen nach (Tagen)**
können Sie für Ihre eigenen Aufnahmen eine **kürzere** Frist eintragen,
zum Beispiel 14 Tage, wenn Sie Ihre Texte immer sofort übernehmen. Lassen Sie
das Feld leer, gilt nur die Frist der Einrichtung. Eine längere Frist als die
der Einrichtung ist nicht möglich.

## Design

Unter **Design** wählen Sie **Hell**, **Dunkel** oder **System** (passend zur
Einstellung Ihres Betriebssystems).

# Desktop-Client

Für das Diktieren direkt in andere Programme (Praxissoftware, Mail,
Textverarbeitung) gibt es einen optionalen Desktop-Client für Windows, macOS
und Linux. Er bleibt als kleines Fenster im Vordergrund, nimmt auf und fügt
den fertigen Text an der Cursorposition im zuletzt aktiven Programm ein.
Ob der Client in Ihrer Einrichtung verfügbar ist und wie Sie ihn erhalten,
erfahren Sie von Ihrer IT.

<!-- TODO: Bedienung des Clients beschreiben, sobald Screenshots vorliegen -->

# Häufige Fragen und Probleme

**Der Browser fragt nicht nach dem Mikrofon / das Mikrofon ist blockiert.**
Prüfen Sie, ob die Adresse mit `https://` beginnt. Klicken Sie auf das
Schloss-Symbol links in der Adresszeile und erlauben Sie den
Mikrofonzugriff. Prüfen Sie in den Systemeinstellungen, ob das richtige
Mikrofon als Standard ausgewählt ist.

**Während der Aufnahme erscheint kein Live-Text.**
Die Live-Vorschau ist eventuell abgeschaltet oder gerade nicht erreichbar.
Die Aufnahme läuft trotzdem; Transkript und Zusammenfassung entstehen nach
dem Beenden wie gewohnt.

**„Verbindung unterbrochen – bitte Aufnahme neu starten“.**
Die Verbindung zum Server ist abgebrochen, etwa durch WLAN-Wechsel oder
Standby. Öffnen Sie openDox neu; die Aufnahme kann meist über **Unfertige
Aufnahme → Fortsetzen** weitergeführt werden.

**Ein Fachbegriff wird immer wieder falsch erkannt.**
Tragen Sie ihn in eines Ihrer Wörterbücher ein. Betrifft er viele Kolleginnen und Kollegen, bitten Sie die
Administration, ihn in ein globales Wörterbuch aufzunehmen.

**Die Zusammenfassung enthält Angaben, die ich nicht diktiert habe.**
Korrigieren Sie die Zusammenfassung vor dem Kopieren. Tritt das häufig auf,
schärfen Sie den System Prompt Ihrer Kategorie nach („keine Inhalte
hinzufügen“) oder melden Sie es der Administration.

**Die Aufnahme steht auf „Fehler“.**
Melden Sie Titel und Uhrzeit der Aufnahme Ihrer Administration. Die
Aufnahme wird bei einem Fehler aufbewahrt und kann erneut verarbeitet
werden.

# Glossar

| Begriff | Erklärung |
|:-----------|:-------------------------------|
| Transkript | Wörtliche Verschriftlichung des Diktats. |
| Zusammenfassung | Von der KI nach den Vorgaben der Kategorie aufbereiteter Text. |
| Live-Vorschau | Vorläufiger Text während der Aufnahme; nicht das Endergebnis. |
| Kategorie | Vorlage, die Erkennung und Zusammenfassung für einen Einsatzzweck steuert. |
| Wörterbuch | Begriffsliste für die automatische Korrektur. Global (von der Administration, wirkt in den Kategorien, an die es angehängt ist) oder eigenes (nur für Sie, wirkt in allen Ihren Aufnahmen). |
| System Prompt | Anweisung an die KI, wie die Zusammenfassung aussehen soll. |
| KI / LLM | Sprachmodell, das die Zusammenfassung erstellt. |

# Impressum und Lizenz

openDox wird von der S2A Open Technologies gGmbH entwickelt und als freie
Software unter der GNU Affero General Public License, Version 3 oder später
(AGPL-3.0-or-later), veröffentlicht. Die Software wird ohne Gewährleistung
bereitgestellt; Einzelheiten regelt die Lizenz.

Für den Betrieb der jeweiligen Installation, einschließlich Datenschutz und
der Einhaltung medizinrechtlicher Vorschriften, ist die betreibende
Einrichtung verantwortlich. Bei Fragen zur Nutzung wenden Sie sich zuerst an
Ihre interne IT oder Administration.
