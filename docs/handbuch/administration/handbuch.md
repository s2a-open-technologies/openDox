---
title: "openDox"
subtitle: "Administrationshandbuch"
---

# Über dieses Handbuch

Dieses Handbuch richtet sich an alle, die openDox über die Weboberfläche
einrichten und betreuen: Administratoren, Moderatoren und die Fachabteilung,
die Kategorien und Wörterbücher pflegt. Es beschreibt den Bereich
**Administration**. Die Bedienung für Anwender steht im *Benutzerhandbuch*,
Installation, Server-Konfiguration, Update und Datensicherung im
*Installations- und Betriebshandbuch*.

Bezeichnungen von Schaltflächen, Menüs und Feldern sind im Text **fett**
gesetzt und entsprechen der deutschen Oberfläche.

## Wichtiger Hinweis: Kein Medizinprodukt

openDox ist **kein zugelassenes Medizinprodukt** gemäß Medizinproduktegesetz
(MPG) oder vergleichbaren Regularien (z. B. EU-MDR, FDA). Es dient
ausschließlich der Unterstützung bei der Dokumentation. Alle maschinell
erstellten Transkriptionen und Zusammenfassungen müssen von qualifiziertem
Fachpersonal überprüft werden.

Als Administrator beeinflussen Sie die Qualität der Ergebnisse unmittelbar:
Sprachmodell, System Prompts, Wörterbücher und Schwellenwerte entscheiden,
wie oft Fehler entstehen. Testen Sie jede Änderung mit Probediktaten, bevor
Sie sie für alle freigeben. Der Hinweis „Kein Medizinprodukt“ in der
Oberfläche und die Bestätigung bei der ersten Anmeldung lassen sich nicht
abschalten.

## Wie openDox ein Diktat verarbeitet

Wer die Verarbeitungskette kennt, findet Fehlerursachen schneller:

1. **Aufnahme:** Browser oder Desktop-Client schicken das Audio an den
   openDox-Server.
2. **Live-Vorschau (optional):** Der Server leitet das Audio an den
   Parakeet-Dienst weiter, der während des Sprechens vorläufigen Text
   zurückliefert.
3. **Finale Transkription:** Nach dem Beenden schneidet openDox Pausen aus der
   Aufnahme und schickt nur die gesprochenen Abschnitte an den
   Whisper-Dienst. Das Ergebnis ist das *Transkript*.
4. **Fachbegriff-Korrektur (optional):** Ähnlich klingende Wörter werden
   durch Begriffe aus den Wörterbüchern ersetzt.
5. **PII-Sanitizer (optional):** Namen und andere personenbezogene Angaben
   werden vor der Übergabe an das Sprachmodell durch Platzhalter ersetzt und
   danach wieder eingesetzt.
6. **Zusammenfassung:** Ein Sprachmodell (LLM) formt das Transkript nach dem
   System Prompt der gewählten Kategorie um.
7. **Audio-Aufbewahrung (optional):** Eine komprimierte, verschlüsselte
   Kopie der Aufnahme wird für den Download gespeichert. Die Rohaufnahme wird
   nach erfolgreicher Verarbeitung gelöscht.

Transkripte, Zusammenfassungen und gespeicherte Audiodateien liegen
verschlüsselt in Datenbank und Objektspeicher.

# Rollen und Zugang zur Administration

## Rollen

| Rolle | Rechte |
|:-----------|:-------------------------------|
| **Benutzer** | Diktieren, eigene Aufnahmen, eigene Kategorien und Wörterbücher. Kein Zugang zur Administration. |
| **Moderator** | Wie Benutzer, zusätzlich globale **Kategorien**, globale **Wörterbücher** und **System**-Status. |
| **Administrator** | Alle Bereiche der Administration. |
| **Demo-Viewer (nur lesen)** | Sieht alle Bereiche wie ein Administrator, kann aber nichts speichern. Nur Kategorien und Wörterbücher bleiben bearbeitbar. Gedacht für Vorführungen. |

Die Rolle wird bei lokalen Konten in der **Benutzerverwaltung** gesetzt, bei
LDAP- und SSO-Konten bei jeder Anmeldung aus der Gruppenzugehörigkeit
abgeleitet (siehe Kapitel *Authentifizierung*).

## Datenschutz zwischen den Rollen

Auch Administratoren können **keine** Aufnahmen, Transkripte,
Zusammenfassungen oder Audiodateien anderer Benutzer öffnen. Ebenso bleiben
die persönlichen Wörterbücher der Benutzer für Administratoren unsichtbar.
Persönliche Kategorien der Benutzer sehen Administratoren dagegen in der
Kategorienliste und können sie zu Supportzwecken bearbeiten.

## Administration öffnen

Klicken Sie oben auf Ihren Namen und wählen Sie **Administration**. Der
Eintrag erscheint nur für Moderatoren, Administratoren und Demo-Viewer.

![Administrationsbereich mit Navigation](bilder/administration/01-administration.png)

Die Navigation links (auf dem Smartphone oben) enthält:

| Bereich | Inhalt | Sichtbar für |
|:-----------|:-------------------------------|:-----------|
| **Dienste** | Spracherkennung (Whisper / ASR) und Sprachmodell (LLM), PII-Sanitizer | Administrator |
| **Archivierung** | Audio-Download, Auto-Archivierung, fehlgeschlagene Transkriptionen | Administrator |
| **Benutzer** | Lokale Benutzerkonten | Administrator |
| **Authentifizierung** | LDAP und OIDC / SSO | Administrator |
| **Backup** | Einstellungen sichern und wiederherstellen | Administrator |
| **Clients** | Desktop-Client verteilen und konfigurieren | Administrator |
| **Kategorien** | Globale Kategorien | Moderator, Administrator |
| **Wörterbücher** | Globale Wörterbücher | Moderator, Administrator |
| **System** | Status aller Dienste | Moderator, Administrator |

Ihre persönlichen Einstellungen (Sprache, eigene Wörterbücher, eigene
Kategorien, Design) finden Sie wie alle Benutzer unter **Profil**.

## Erste Anmeldung nach der Installation

Eine neue Installation enthält ein Administratorkonto mit Benutzername
`admin` und Passwort `admin`.

> Ändern Sie das Passwort sofort nach der ersten Anmeldung unter
> **Benutzer → admin → Bearbeiten**, oder legen Sie ein eigenes
> Administratorkonto an und deaktivieren Sie `admin` danach.

Prüfen Sie anschließend unter **System**, ob alle Dienste erreichbar sind,
und arbeiten Sie die Kapitel *Dienste* und *Authentifizierung* durch.

# Dienste

Unter **Dienste** verbinden Sie openDox mit der Spracherkennung und dem
Sprachmodell. Die Werte gelten für alle Benutzer. Bei mehreren
Server-Instanzen übernehmen die anderen Instanzen Änderungen nach spätestens
etwa 30 Sekunden.

## Whisper / ASR: Allgemein

Unter **Sprache** wählen Sie die Sprache, in der diktiert wird
(**Deutsch**, **Englisch**, **Französisch**, **Spanisch**, **Italienisch**
oder **Automatisch (Spracherkennung)**). Eine feste Sprache liefert
zuverlässigere Ergebnisse als die automatische Erkennung. Die Einstellung ist
unabhängig von der Sprache der Bedienoberfläche.

![Dienste → Whisper / ASR → Allgemein](bilder/administration/02-whisper-allgemein.png)

## Whisper / ASR: Live

Die Live-Vorschau zeigt während der Aufnahme vorläufigen Text.

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **Live-Transkription aktiv** | **Parakeet (empfohlen)** oder **Deaktiviert**. |
| **API Endpoint** | Adresse des Parakeet-Dienstes, in der mitgelieferten Docker-Installation `http://parakeet:5001/v1`. |
| **API Key (optional)** | Muss dem beim Parakeet-Dienst hinterlegten Schlüssel entsprechen (`PARAKEET_API_KEY`). |

Mit **Verbindung testen** prüfen Sie die Erreichbarkeit.

![Dienste → Whisper / ASR → Live](bilder/administration/03-whisper-live.png)

> Die Live-Vorschau ist nur auf einem Server mit Grafikkarte (GPU) in
> Echtzeit möglich. Läuft Parakeet ohne GPU, hinkt der Text stark hinterher.
> Stellen Sie in diesem Fall **Deaktiviert** ein. Aufnahme und finales
> Ergebnis funktionieren ohne Live-Vorschau unverändert.

## Whisper / ASR: Final

Die finale Transkription erzeugt das maßgebliche Transkript.

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **API Endpoint** | Adresse des Whisper-Dienstes (OpenAI-kompatibel), in der Docker-Installation `http://whisper:5002/v1`. |
| **API Key (optional)** | Muss dem beim Whisper-Dienst hinterlegten Schlüssel entsprechen (`WHISPER_API_KEY`). |
| **Modell** | Modellname, den der Whisper-Dienst erwartet, z. B. `large-v3-turbo`. |
| **Fachbegriff-Korrektur (Phonetik/Fuzzy)** | Schaltet die automatische Korrektur mit Wörterbüchern ein. Standard: aus. |
| **Schwellenwert (0-100)** | Wie ähnlich ein Wort einem Wörterbuchbegriff sein muss, damit es ersetzt wird. |

![Dienste → Whisper / ASR → Final](bilder/administration/04-whisper-final.png)

### Fachbegriff-Korrektur

Ist die Korrektur eingeschaltet, vergleicht openDox das finale Transkript mit
den Wörterbüchern, die für die Aufnahme gelten: den globalen Wörterbüchern
der gewählten Kategorie und den persönlichen Wörterbüchern des Benutzers. Ein
Wort wird nur ersetzt, wenn es einem Begriff sowohl im Klang als auch in der
Schreibweise ähnelt. Richtig geschriebene Wörter bleiben unangetastet.

- **85** ist ein guter Standardwert.
- **90** korrigiert etwas weniger, ist aber bei sehr großen oder
  uneinheitlichen Wörterbüchern vorsichtiger.
- Niedrigere Werte erhöhen das Risiko, dass ein richtiges Wort durch einen
  falschen Fachbegriff ersetzt wird.

Jede Ersetzung wird im Server-Protokoll mit Original, Ersatz und Wert
festgehalten. Ihr IT-Betrieb kann Ihnen diese Einträge zur Feineinstellung
geben.

## Whisper / ASR: Qualität

Die Werte unter **Qualität & Anti-Halluzination** verhindern vor allem, dass
die Spracherkennung bei Stille Text erfindet. Für die mitgelieferte
Installation passen die Voreinstellungen; ändern Sie sie nur gezielt.

| Feld | Standard | Bedeutung |
|:-----------|:-----|:-------------------------------|
| **VAD min. Stille (ms)** | 500 | Ab dieser Pausenlänge schneidet openDox Stille aus der Aufnahme, bevor sie an Whisper geht. |
| **VAD-Filter des Servers (zusätzlich)** | an | Zusätzliche Stille-Erkennung im Whisper-Dienst. |
| **Auf vorherigen Text bedingen** | aus | Whisper berücksichtigt den vorherigen Abschnitt. Kann Wiederholungsschleifen auslösen. |
| **Temperatur (0 = deterministisch)** | 0 | Höhere Werte machen das Ergebnis zufälliger. |
| **No-Speech-Schwelle** | 0,6 | Ab wann ein Abschnitt als „keine Sprache“ gilt. |
| **Compression-Ratio-Schwelle** | 2,4 | Erkennt sich wiederholenden Text. |
| **Log-Prob-Schwelle** | -1,0 | Verwirft sehr unsichere Abschnitte. |
| **Halluzinations-Stille-Schwelle** | 2,0 s | Überspringt Stille, in der Text erfunden würde; leer = aus. |
| **Beam-Size** | 5 | Suchbreite; höher ist genauer, aber langsamer. |

Klicken Sie nach Änderungen in jedem Reiter auf **Einstellungen speichern**.

## LLM

Hier verbinden Sie das Sprachmodell, das die Zusammenfassungen schreibt.
openDox spricht jeden OpenAI-kompatiblen Dienst an, z. B. Ollama, vLLM oder
einen internen LLM-Proxy.

![Dienste → LLM](bilder/administration/05-llm.png)

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **API Endpoint** | Adresse des Dienstes, z. B. `http://ollama:11434/v1`. |
| **API Key (optional)** | Schlüssel, falls der Dienst einen verlangt. |
| **Modell** | Modellname beim Dienst. |
| **Temperatur (0.0 - 1.0)** | Standard 0,2. Für Zusammenfassungen niedrig halten. |
| **Max Tokens** | Höchstlänge der Antwort, Standard 2048. Bei langen Diktaten ggf. erhöhen. |
| **Top P (0.0 - 1.0)** | Standard 0,9. |
| **Frequency Penalty (-2.0 - 2.0)** | Standard 0,3; dämpft Wiederholungen. |
| **Thinking aktivieren** | Standard aus. Reasoning-Modelle (z. B. Qwen3, DeepSeek-R1) brauchen sonst sehr lange oder bleiben hängen. |

Mit **Verbindung testen** schickt openDox eine kurze Testanfrage und zeigt
die Antwort an. **Einstellungen speichern** übernimmt die Werte.

Unabhängig vom System Prompt hängt openDox an jede Anfrage zwei feste
Anweisungen an: keine Denkschritte ausgeben und keine Platzhalter wie
`[DATUM]` erfinden. Sie müssen das nicht in Ihre Prompts schreiben.

Einzelne Kategorien können ein anderes Modell verwenden (siehe *Kategorien*).

## PII-Sanitizer

Der PII-Sanitizer ersetzt Namen, Orte und andere personenbezogene Angaben im
Transkript durch Platzhalter wie `[PERSON_1]`, bevor der Text an das
Sprachmodell geht. Nach der Antwort setzt openDox die echten Angaben wieder
ein. Das ist vor allem sinnvoll, wenn das Sprachmodell außerhalb Ihres
eigenen Rechenzentrums läuft.

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **Sanitizer aktivieren** | Schaltet die Anonymisierung ein. |
| **Sanitizer Endpoint (vollständige URL)** | Komplette Adresse einschließlich Pfad, z. B. `http://entityguard:9500/api/v1/sanitize`. openDox hängt keinen Pfad an. |
| **API Key** | Bearer Token für den Dienst, falls nötig. |

Der Sanitizer ist ein separater Dienst (z. B. EntityGuard) und nicht Teil
der openDox-Installation. Die Wiedereinsetzung arbeitet nach bestem Bemühen:
Prüfen Sie bei eingeschaltetem Sanitizer stichprobenartig, ob Namen in der
Zusammenfassung korrekt zurückgesetzt wurden.

# Kategorien

Eine Kategorie ist eine Vorlage für einen Einsatzzweck, z. B. *Arztbrief
Kardiologie* oder *OP-Bericht*. Benutzer wählen sie beim Start einer
Aufnahme und können sie danach ändern.

Unter **Kategorien** verwalten Moderatoren und Administratoren die
**globalen** Kategorien, die allen Benutzern zur Verfügung stehen.
Benutzer können sich zusätzlich eigene Kategorien anlegen.

![Kategorien mit Liste und Formular](bilder/administration/06-kategorien.png)

## Kategorie anlegen oder bearbeiten

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **Kategorie Name** | Name in der Auswahlliste. |
| **Beschreibung** | Kurze Erläuterung für die Benutzer. |
| **System Prompt (LLM)** | Anweisung an das Sprachmodell, wie die Zusammenfassung aussehen soll. |
| **Transkriptions-Hint (Whisper)** | Kurzer Hinweis auf Stil und Schreibweisen für die Spracherkennung. Whisper berücksichtigt nur die letzten rund 224 Tokens; lange Begriffslisten gehören in ein Wörterbuch. |
| **Wörterbücher** | Globale Wörterbücher, deren Begriffe in dieser Kategorie korrigiert werden. Eine globale Kategorie kann nur globale Wörterbücher verwenden. |
| **Eigenes LLM verwenden** | Überschreibt die globalen LLM-Einstellungen für diese Kategorie (siehe unten). |

Klicken Sie auf **Erstellen** bzw. **Aktualisieren**. Mit dem Papierkorb
löschen Sie eine Kategorie nach Rückfrage.

## Guten System Prompt schreiben

- Beschreiben Sie Abschnitte, Reihenfolge, Stil und Länge.
- Schreiben Sie ausdrücklich, was das Modell *nicht* tun soll, z. B.
  „füge keine Inhalte hinzu, die nicht diktiert wurden“.
- Legen Sie fest, was bei fehlenden Angaben geschieht („Abschnitt
  weglassen“).
- Testen Sie mit mehreren realistischen Probediktaten, auch mit kurzen,
  unvollständigen und schlecht verständlichen.

Ein Beispiel finden Sie im *Benutzerhandbuch*, Kapitel *Kategorien*.

## Eigenes LLM je Kategorie

Mit **Eigenes LLM verwenden** kann eine Kategorie ein anderes Modell oder
einen anderen Dienst nutzen, etwa ein größeres Modell für Arztbriefe. Die
Felder (**Modell**, **API Endpunkt**, **API Key**, **Temperature**, **Max
Tokens**, **Top P**, **Frequency Penalty**, **Thinking aktivieren**)
entsprechen denen unter *Dienste → LLM*; leere Felder übernehmen den globalen
Wert. Persönliche Kategorien der Benutzer können kein eigenes LLM erhalten.

# Wörterbücher

Wörterbücher sind Begriffslisten für die Fachbegriff-Korrektur:
Medikamente, Diagnosen, Abkürzungen, Namen von Ärztinnen und Ärzten, ganze
Kataloge wie ICD-Bezeichnungen. Anders als der Transkriptions-Hint haben sie
keine Längenbegrenzung.

## Globale und persönliche Wörterbücher

| | Global | Persönlich |
|:-----------|:-------------------------------|:-------------------------------|
| Verwaltet von | Moderatoren und Administratoren unter **Wörterbücher** | dem Benutzer selbst unter **Profil → Meine Wörterbücher** |
| Sichtbar für | alle (zum Anhängen an eigene Kategorien) | nur den Besitzer, nicht für Administratoren |
| Wirkt | nur in den Kategorien, an die es angehängt ist | in allen Aufnahmen des Besitzers |

> Ein globales Wörterbuch wirkt erst, wenn es an eine Kategorie angehängt
> ist und unter **Dienste → Whisper / ASR → Final** die
> **Fachbegriff-Korrektur** eingeschaltet ist.

So lassen sich neue Wörterbücher zunächst an einer Testkategorie erproben.

## Wörterbuch anlegen und pflegen

![Globale Wörterbücher](bilder/administration/07-woerterbuecher.png)

1. Geben Sie unter **Wörterbücher** einen Namen ein und klicken Sie auf
   **Anlegen**.
2. Öffnen Sie das Wörterbuch zum Bearbeiten. Tragen Sie Begriffe einzeln ein
   (**Hinzufügen**) oder laden Sie eine Datei hoch.
3. Klicken Sie auf **Speichern**.
4. Hängen Sie das Wörterbuch unter **Kategorien** an die gewünschten
   Kategorien an.

Die Liste zeigt je Wörterbuch die Anzahl der Begriffe und in wie vielen
Kategorien es verwendet wird. Große Wörterbücher werden nur auszugsweise
angezeigt; über **Begriffe durchsuchen** finden Sie jeden Eintrag. Beim
Löschen eines angehängten Wörterbuchs wird es aus allen Kategorien entfernt.

## Dateiformat für den Upload

- `.txt` oder `.csv`, UTF-8, höchstens 5 MB.
- Ein Begriff pro Zeile; leere Zeilen und Zeilen mit `#` am Anfang werden
  ignoriert. Kommas innerhalb eines Begriffs bleiben erhalten.
- Bei `.csv` zählt die erste Spalte (Trennzeichen `;` oder `,`); eine
  Kopfzeile mit `#` auskommentieren.
- Doppelte Begriffe werden entfernt; höchstens 50.000 Begriffe mit je bis
  zu 200 Zeichen.
- **Anhängen** ergänzt die Liste, **Ersetzen** tauscht sie aus.

## Tipps

- Begriffe mit weniger als drei Zeichen werden nicht korrigiert.
- Nehmen Sie Begriffe auf, die tatsächlich falsch erkannt werden. Ein
  Wörterbuch mit vielen ähnlich klingenden Einträgen erhöht das Risiko von
  Fehlkorrekturen; erhöhen Sie dann den Schwellenwert auf 90.
- Sehr große Kataloge verlängern die Verarbeitung etwas (bei 50.000
  Begriffen einige Sekunden je Diktat).

# Archivierung und Audio

Der Bereich **Archivierung** fasst alles zusammen, was mit der Aufbewahrung
von Aufnahmen zu tun hat.

![Archivierung](bilder/administration/08-archivierung.png)

## Audio-Download

Ist **Audio speichern** eingeschaltet, bewahrt openDox nach erfolgreicher
Transkription eine Kopie der Aufnahme auf, die der Benutzer über
**Audio** herunterladen kann. Die Datei wird verschlüsselt im Objektspeicher
abgelegt. Ist kein Objektspeicher eingerichtet, bleibt die Funktion
wirkungslos.

| Feld | Bedeutung |
|:-----------|:-------------------------------|
| **Dateiformat** | **MP3** (kleinste Datei), **OGG/Opus**, **FLAC** (verlustfrei) oder **WAV** (unkomprimiert, größte Datei). |
| **Bitrate (Qualität/Größe)** | Bei MP3 und OGG; die Auswahl zeigt die ungefähre Größe je Minute. |
| **Sample-Rate (Hz)** | 16000 Hz entspricht der Aufnahme und ergibt die kleinste Datei. |

Die Einstellungen gelten nur für neue Aufnahmen. Aufnahmen werden immer in
Mono gespeichert.

> Gespeicherte Aufnahmen sind Patientendaten. Schalten Sie die Funktion nur
> ein, wenn Ihre Einrichtung die Aufbewahrung vorsieht, und legen Sie
> Löschfristen fest. Ohne Audio-Download wird die Rohaufnahme nach der
> Verarbeitung gelöscht.

## Auto-Archivierung

Mit **Automatisch archivieren** verschiebt openDox Aufnahmen nach Ablauf der
**Frist in Tagen** (1 bis 3650, gerechnet ab der Aufnahme) ins Archiv. Das
wirkt wie **Archivieren** im Zeilenmenü: Die Aufnahme verschwindet aus
**Aktuell**, bleibt aber wiederherstellbar. Gelöscht wird nichts.

Die Prüfung läuft alle sechs Stunden; Änderungen gelten ohne Neustart.

## Fehlgeschlagene Transkriptionen

Schlägt die Verarbeitung einer Aufnahme fehl (z. B. weil Whisper oder das
Sprachmodell nicht erreichbar war), löscht openDox die Aufnahme nicht,
sondern bewahrt sie auf. Die Liste **Fehlgeschlagene Transkriptionen**
zeigt diese Aufnahmen mit Titel, Zeitpunkt und Fehlermeldung.

1. Beheben Sie die Ursache, z. B. einen ausgefallenen Dienst (siehe
   **System**).
2. Klicken Sie bei der Aufnahme auf **Erneut versuchen**.

Die Verarbeitung läuft danach im Hintergrund erneut. Der Benutzer sieht das
Ergebnis in seiner Aufnahme. Aufnahmen, die nicht innerhalb von drei Tagen (Standard)
erneut versucht wurden, werden verschlüsselt in den Objektspeicher ausgelagert und
bleiben dort wiederholbar.

Erstellt ein Benutzer die Zusammenfassung selbst erfolgreich neu (z. B. weil
nur das Sprachmodell kurz ausgefallen war), verschwindet die Aufnahme von
selbst aus der Liste.

# Benutzer

Unter **Benutzer** verwalten Sie **lokale** Konten, also Konten, die nur in
openDox existieren. Konten aus LDAP oder SSO werden bei der ersten Anmeldung
automatisch angelegt.

![Benutzerverwaltung](bilder/administration/09-benutzer.png)

## Benutzer anlegen

1. Klicken Sie auf **Benutzer anlegen**.
2. Geben Sie **Benutzername** und **Passwort** ein.
3. Wählen Sie die **Rolle** und lassen Sie **Aktiv** eingeschaltet.
4. Klicken Sie auf **Anlegen**.

Teilen Sie das Passwort auf sicherem Weg mit.

## Benutzer bearbeiten, sperren, löschen

- **Bearbeiten:** Name, Rolle und Status ändern. Bleibt **Passwort** leer,
  ändert es sich nicht. So setzen Sie auch ein vergessenes Passwort zurück.
- **Sperren:** Schalten Sie **Aktiv** aus. Das Konto bleibt mit allen
  Aufnahmen erhalten, eine Anmeldung ist nicht mehr möglich. Eine laufende
  Sitzung endet spätestens nach einer halben Stunde. Die Sperre gilt auch für
  LDAP- und SSO-Konten und bleibt bestehen, bis Sie **Aktiv** wieder
  einschalten, auch wenn das Konto im Verzeichnisdienst noch freigegeben ist.
- **Löschen:** über den Papierkorb, nach Rückfrage. Ihr eigenes Konto
  können Sie nicht löschen.

> Den Zugang von LDAP- und SSO-Konten entziehen Sie regulär im
> Verzeichnisdienst, indem Sie die Person aus der erlaubten Gruppe nehmen
> (siehe *Sitzungen und Entzug von Rechten*). Die Sperre hier ist für den
> Fall, dass das nicht sofort möglich ist oder nur openDox betroffen sein
> soll.
>
> Bei LDAP- und SSO-Konten wird die Rolle bei jeder Anmeldung aus den
> Gruppen neu gesetzt. Eine hier geänderte Rolle gilt dort also nur bis zur
> nächsten Anmeldung. Ändern Sie stattdessen die Gruppenzugehörigkeit im
> Verzeichnisdienst.

# Authentifizierung

Neben lokalen Konten unterstützt openDox die Anmeldung über LDAP / Active
Directory und über Single Sign-On (OpenID Connect). Beide Verfahren lassen
sich gleichzeitig nutzen. In beiden Fällen gilt:

- Anmelden darf sich nur, wer Mitglied einer **User-**, **Admin-** oder
  **Moderator-Gruppe** ist. Die Gruppe bestimmt zugleich die Rolle.
  Admin- und Moderator-Gruppen müssen nicht zusätzlich als User-Gruppe
  eingetragen werden.
- Sind alle drei Gruppenfelder leer, kann sich niemand über dieses
  Verfahren anmelden. Das ist Absicht: Ein vergessenes Feld soll nicht das
  ganze Verzeichnis freischalten.
- Konten werden bei der ersten Anmeldung angelegt; die Rolle wird bei jeder
  Anmeldung aus den Gruppen abgeleitet. Ist jemand in einer Admin- und einer
  Moderator-Gruppe, gilt Administrator.

## LDAP / Active Directory

![Authentifizierung → LDAP](bilder/administration/10-ldap.png)

| Feld | Bedeutung | Beispiel |
|:-----------|:-------------------------------|:-----------|
| **Server Host** | Name oder IP des Verzeichnisservers | `dc01.klinik.local` |
| **Port** | 389 (LDAP) oder 636 (LDAPS) | `636` |
| **SSL (LDAPS) verwenden** | Verschlüsselte Verbindung; empfohlen | an |
| **Zertifikat hochladen** | CA-Zertifikat (PEM) des Verzeichnisservers, falls es von einer internen CA stammt | `klinik-ca.pem` |
| **Base DN** | Basis für Benutzer- und Gruppensuche | `dc=klinik,dc=local` |
| **User DN Pattern** | Attribut des Anmeldenamens: `uid` (OpenLDAP) oder `sAMAccountName` (AD) | `sAMAccountName` |
| **Suchfilter (optional)** | Schränkt ein, welche Einträge bei der Anmeldung überhaupt gefunden werden, z. B. nur Personen oder nur eine OU. Wird per UND mit der Suche nach dem Anmeldenamen verknüpft. Wer nicht passt, gilt als „nicht gefunden“. Für Gruppen „User-Gruppen“ verwenden. | `(objectClass=person)` |
| **Verschachtelte Gruppen auflösen** | Auch Mitglieder von Untergruppen zählen. Nur Active Directory. | |
| **User-Gruppen** | Mitglieder melden sich mit der Rolle User an. Gruppennamen ohne DN, durch Kommas getrennt. | `openDox-Benutzer` |
| **Admin-Gruppen** | Mitglieder werden Administratoren | `openDox-Admins` |
| **Moderator-Gruppen** | Mitglieder werden Moderatoren | `openDox-Moderatoren` |
| **Bind User DN** / **Bind User Password** | Dienstkonto für die Suche | |

Tragen Sie bei den Gruppen nur den **Namen** ein, keinen vollständigen DN.
openDox bildet den DN selbst als `cn=<Name>,<Base DN>`. Liegen Ihre Gruppen in
einer anderen Organisationseinheit, muss die Base DN so gewählt sein, dass
diese Form passt.

Die Gruppenzugehörigkeit liest openDox aus dem Attribut `memberOf` des
Benutzers. Das liefert Active Directory immer, OpenLDAP nur mit dem
memberof-Overlay.

Mit **Verbindung testen** prüfen Sie Erreichbarkeit und Dienstkonto,
**Speichern** übernimmt die Werte. Testen Sie danach die Anmeldung mit einem
Konto aus jeder Gruppe.

## OIDC / SSO

Für die Anmeldung über einen Identity Provider wie Keycloak, Authentik,
Microsoft Entra ID oder Google.

![Authentifizierung → OIDC / SSO](bilder/administration/11-oidc.png)

**Beim Identity Provider einrichten:**

1. Legen Sie einen Client (Anwendung) vom Typ *vertraulich*
   („confidential“) mit Authorization Code Flow an.
2. Tragen Sie als Redirect-URI ein:
   `https://<Ihre openDox-Adresse>/api/v1/auth/oidc/callback`
   (bei Betrieb unter einem Unterpfad entsprechend mit diesem, z. B.
   `https://klinik.example/opendox/api/v1/auth/oidc/callback`).
3. Sorgen Sie dafür, dass das ID-Token die Gruppen des Benutzers enthält
   (bei Keycloak z. B. per „Group Membership“-Mapper mit Claim `groups`).

**In openDox:**

| Feld | Bedeutung | Standard |
|:-----------|:-------------------------------|:-----------|
| **OIDC aktivieren** | Zeigt **Mit Single Sign-On anmelden** auf der Anmeldeseite. | aus |
| **Provider URL (Issuer)** | Issuer-Adresse; die übrigen Adressen ermittelt openDox über `/.well-known/openid-configuration`. | |
| **Client ID** / **Client Secret** | Zugangsdaten des Clients beim Provider. | |
| **Scopes** | Angefragte Scopes. | `openid email profile` |
| **Username-Claim** | Claim mit dem Benutzernamen. | `preferred_username` |
| **Gruppen-Claim** | Claim mit der Gruppenliste. | `groups` |
| **User-Gruppen**, **Admin-Gruppen**, **Moderator-Gruppen** | Gruppennamen, wie sie im Gruppen-Claim stehen, durch Kommas getrennt. | |

Verweigert openDox nach erfolgreicher Anmeldung beim Provider den Zugang,
fehlt meist die Gruppe im Token oder der Gruppenname weicht ab (manche
Provider liefern Pfade wie `/openDox-Benutzer`). Ihr IT-Betrieb findet die
Ursache im Server-Protokoll.

## Sitzungen und Entzug von Rechten

Nach der Anmeldung erneuert openDox die Sitzung etwa alle 30 Minuten im
Hintergrund. Dabei prüft es LDAP- und SSO-Konten erneut beim
Verzeichnisdienst:

- **LDAP:** openDox sucht das Konto mit dem Dienstkonto (**Bind User DN**).
  Gibt es das Konto nicht mehr, ist es im Active Directory deaktiviert oder
  in keiner erlaubten Gruppe mehr, endet die Sitzung. Ohne Dienstkonto prüft
  openDox nur bei der Anmeldung.
- **OIDC / SSO:** openDox erneuert die Sitzung beim Identity Provider.
  Lehnt er ab (Konto gesperrt, Sitzung beendet) oder fehlt die Gruppe im
  neuen Token, endet die Sitzung. Manche Provider, etwa Microsoft Entra ID,
  liefern die dafür nötige Erneuerung nur mit dem Scope `offline_access`;
  tragen Sie ihn dann unter **Scopes** zusätzlich ein. Ohne ihn prüft
  openDox nur bei der Anmeldung und schreibt einen Hinweis ins
  Server-Protokoll.
- Die Rolle folgt dabei den aktuellen Gruppen, wie bei der Anmeldung.

Ein entzogener Zugang wirkt so spätestens nach einer halben Stunde, in der
Weboberfläche wie im Desktop-Client.

> Ist der Verzeichnisdienst oder Identity Provider gerade nicht erreichbar,
> bleibt die Sitzung bestehen. Ein Ausfall soll niemanden mitten im Diktat
> abmelden. Abgemeldet wird nur, wenn der Dienst eindeutig ablehnt.

# Desktop-Client

Unter **Clients** verteilen und steuern Sie den optionalen Desktop-Client
für Windows und macOS. Er diktiert direkt in andere Programme und fügt den
fertigen Text dort ein.

![Clients](bilder/administration/12-clients.png)

## Client verteilen

1. **Installer herunterladen:** **Windows (MSI, für Softwareverteilung)**,
   **Windows (Setup.exe, Einzelplatz)** oder **macOS**.
2. **settings.json herunterladen:** Die Datei enthält die Adresse dieses
   Servers. Prüfen Sie die angezeigte **Server-Adresse für die Clients**;
   stimmt sie nicht, muss der IT-Betrieb `CLIENT_SERVER_URL` setzen.
3. **Installer und settings.json gemeinsam verteilen:** Für **Intune** und
   **SCCM / PowerShell** zeigt die Seite fertige Installationsbefehle zum
   Kopieren. Für Einzelplätze den Installer ausführen und die `settings.json`
   in das angegebene Programmverzeichnis kopieren.

## Client-Einstellungen

Diese Werte gelten für alle Clients dieses Servers und haben Vorrang vor
lokalen Einstellungen. Die Clients übernehmen sie beim Start und danach
spätestens nach zehn Minuten.

| Feld | Bedeutung | Standard |
|:-----------|:-------------------------------|:-----------|
| **Live-Ansicht standardmäßig an** | Live-Vorschau beim Start eingeschaltet; Benutzer können sie umschalten. | an |
| **Record-Taste am Diktiermikrofon** | **Halten zum Aufnehmen** oder **Drücken startet, erneutes Drücken stoppt**. | Halten |
| **Eingefügten Text aus Zwischenablage-Verlauf heraushalten** | Unter Windows erscheint diktierter Text nicht im Zwischenablage-Verlauf und nicht in der Cloud-Zwischenablage. | an |
| **Zwischenablage leeren nach (Sekunden)** | Löscht den Text aus der Zwischenablage, sofern sie sich nicht geändert hat; 0 = nie. | 30 |
| **Erlaubte Zielprogramme** | Ein Programm pro Zeile, z. B. `medistar.exe`. Leer = jedes Programm; sonst fragt der Client vor dem Einfügen in andere Programme nach. | leer |

# Backup der Einstellungen

Unter **Backup** sichern Sie alle globalen **Einstellungen** von openDox als
JSON-Datei: Whisper und Parakeet, LLM und EntityGuard, LDAP, OIDC, Audio,
automatische Abmeldung, Desktop-Client, Kategorien, Sprachen und globale
Wörterbücher.

![Backup](bilder/administration/13-backup.png)

- **Backup herunterladen** speichert die Datei.
- **Backup einspielen** lädt eine solche Datei und **überschreibt alle
  aktuellen Einstellungen**. Globale Kategorien und Wörterbücher werden
  vollständig ersetzt.

Nicht enthalten sind Benutzerkonten, persönliche Wörterbücher, Aufnahmen, Transkripte und
Audiodateien. Das Einstellungs-Backup ersetzt deshalb keine
Datensicherung der Datenbank; diese ist Aufgabe des IT-Betriebs (siehe
*Installations- und Betriebshandbuch*).

> Die Backup-Datei enthält **keine Zugangsdaten**: keine API-Schlüssel
> (Whisper, Parakeet, LLM, EntityGuard, LLM je Kategorie), kein Passwort und
> kein Zertifikat des LDAP-Dienstkontos, kein OIDC-Client-Secret. Beim
> Einspielen bleiben die auf dem Server gespeicherten Zugangsdaten erhalten.
> Auf einer neuen Installation tragen Sie sie nach dem Einspielen einmal von
> Hand ein.

Typische Anwendung: Einstellungen von einer Testinstallation in die
Produktivinstallation übertragen.

# System

Der Bereich **System** zeigt den Zustand aller Dienste und aktualisiert sich
alle zehn Sekunden.

![Systemstatus](bilder/administration/14-system.png)

| Dienst | Bedeutung |
|:-----------|:-------------------------------|
| **Backend** | openDox-Server selbst. |
| **Datenbank** | PostgreSQL. Ohne Datenbank funktioniert nichts. |
| **Cache** | Redis (Sitzungen laufender Aufnahmen). |
| **Transkription** | Whisper-Dienst für die finale Transkription. |
| **Live** | Parakeet-Dienst für die Live-Vorschau. |
| **PII** | PII-Sanitizer. |
| **Objekt-Speicher (S3)** | Speicher für Audio-Download und ausgelagerte Fehlaufnahmen. |
| **Verschlüsselung** | Zustand des Verschlüsselungsschlüssels. |

Jeder Dienst steht auf **Online**, **Nicht erreichbar** oder **Deaktiviert**.
*Deaktiviert* bedeutet, dass die Funktion bewusst nicht eingerichtet ist, und
ist kein Fehler.

## Automatische Abmeldung

Unter dem Systemstatus legen Sie fest, nach wie vielen Minuten ohne Eingabe
die Weboberfläche abmeldet (**Abmelden nach Inaktivität**, Standard 30,
0 = nie). Das gilt für alle Benutzer und schützt Arbeitsplätze, an denen
mehrere Personen arbeiten.

- Als Eingabe zählen Klicks, Tastatur, Scrollen und Touch, in jedem
  geöffneten Tab von openDox.
- Während einer Aufnahme und solange ihre Transkription läuft, wird nie
  abgemeldet.
- Wer zurückkommt, sieht die Anmeldeseite mit dem Hinweis, dass wegen
  Inaktivität abgemeldet wurde.

Der Desktop-Client ist davon ausgenommen. Er bleibt angemeldet, solange er
läuft, und erneuert seine Sitzung selbst. Nach sieben Tagen ohne laufenden
Client ist eine neue Anmeldung nötig.

# Fehlersuche

**„Transkription“ ist nicht erreichbar.**
Prüfen Sie unter **Dienste → Whisper / ASR → Final** Adresse und API-Key mit
**Verbindung testen**. Läuft der Dienst nicht, informieren Sie den
IT-Betrieb. Aufnahmen, die in dieser Zeit fehlschlagen, können Sie danach
unter **Archivierung → Fehlgeschlagene Transkriptionen** erneut verarbeiten.

**Keine Live-Vorschau.**
**Live** unter **System** prüfen. Ohne GPU auf **Deaktiviert** stellen.
Aufnahmen funktionieren auch ohne Live-Vorschau.

**Zusammenfassungen dauern sehr lange oder bleiben hängen.**
Prüfen Sie, ob **Thinking aktivieren** ausgeschaltet ist. Prüfen Sie das
Modell mit **Verbindung testen** und erhöhen Sie ggf. **Max Tokens**, wenn
Zusammenfassungen mittendrin abbrechen.

**Die Zusammenfassung enthält erfundene Angaben.**
Schärfen Sie den System Prompt der Kategorie nach. Verwenden Sie eine
niedrige Temperatur. Bei kleinen Modellen hilft oft ein größeres Modell
(ggf. nur für diese Kategorie über **Eigenes LLM verwenden**).

**Ein Begriff wird nicht korrigiert.**
Ist die **Fachbegriff-Korrektur** eingeschaltet? Ist das Wörterbuch an die
verwendete Kategorie angehängt? Weicht die Erkennung stark vom Begriff ab,
greift die Korrektur bewusst nicht; senken Sie den Schwellenwert nur
vorsichtig.

**Ein richtiges Wort wird durch einen Fachbegriff ersetzt.**
Schwellenwert auf 90 erhöhen oder den auslösenden Begriff aus dem Wörterbuch
entfernen bzw. präzisieren.

**LDAP-Benutzer können sich nicht anmelden.**
Ist der Benutzer Mitglied einer erlaubten Gruppe? Stimmt der Gruppenname
(ohne DN)? Liegt die Gruppe direkt unter der Base DN? Bei verschachtelten
Gruppen in Active Directory **Verschachtelte Gruppen auflösen** einschalten.

**SSO-Anmeldung endet mit einer Fehlermeldung.**
Redirect-URI beim Provider prüfen (genaue Adresse inklusive Unterpfad und
`https`). Prüfen, ob der Gruppen-Claim im Token enthalten ist und die Namen
übereinstimmen.

# Impressum und Lizenz

openDox wird von der S2A Open Technologies gGmbH entwickelt und als freie
Software unter der GNU Affero General Public License, Version 3 oder später
(AGPL-3.0-or-later), veröffentlicht. Die Software wird ohne Gewährleistung
bereitgestellt; Einzelheiten regelt die Lizenz.

Für den Betrieb der jeweiligen Installation, einschließlich Datenschutz und
der Einhaltung medizinrechtlicher Vorschriften, ist die betreibende
Einrichtung verantwortlich.
