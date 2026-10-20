# Spracherkennung im Vergleich: Whisper, Parakeet, Fachbegriff-Korrektur

Stand: 21.10.2026, openDox 0.10.4. Gemessen auf einer RTX 3060 (12 GB) mit
synthetischen Diktaten. Die Zahlen helfen bei der Wahl des Modells, ersetzen
aber keinen Test mit echten Diktaten der eigenen Einrichtung (siehe
*Einschränkungen*).

## Kurzfassung

| Frage | Ergebnis |
| --- | --- |
| Bestes Ergebnis | Whisper mit Transkriptions-Hint und Wörterbuch: Fehlerrate 6,2–6,9 %, alle Fachbegriffe richtig, kein Dosisfehler |
| Whisper large-v3 oder large-v3-turbo? | Praktisch gleich genau, turbo ist knapp dreimal schneller. Standard bleibt **turbo** |
| Kann Parakeet Whisper ersetzen? | Technisch ja, ohne Codeänderung. Etwas mehr Fehler (7,3–9,7 %) und **ein beobachteter Dosisfehler**, dafür etwa dreimal schneller und ein Container weniger |
| Hat int8 bei Whisper Nachteile? | Nein: gleiche Genauigkeit wie float16, am schnellsten, halber GPU-Speicher. Standard bleibt `WHISPER_COMPUTE_TYPE=int8` |
| Lohnt int8 für Parakeet? | Auf der GPU nein (zehnmal langsamer), auf der CPU ja für Demos (~25 % schneller, aber schlechter bei Medikamentennamen) |
| Bringt das Wörterbuch etwas? | Ja: 2–3 Prozentpunkte weniger Fehler bei jedem Modell, keine falsch eingesetzten Begriffe |

## Aufbau der Messung

- **Diktate:** drei synthetische medizinische Diktate (3, 5 und 10 Minuten,
  422 bis 1.318 Wörter), gesprochen mit Piper TTS (Stimme
  `de_DE-thorsten-medium`), mit Referenztext. Inhalt: Anamnese, Medikation mit
  Dosierungen, Laborwerte, Befunde.
- **Weg durch openDox:** Jede Aufnahme lief durch den echten
  `OpenAICompatibleBackend`, also wie in der App: Silero-VAD schneidet Stille
  heraus, Sprache geht in Stücken bis 28 s parallel an den Server.
- **Hardware:** RTX 3060 12 GB. Whisper (faster-whisper) in `int8`, Parakeet
  TDT 0.6B v3 (onnx-asr) in FP32 auf CUDA.
- **Transkriptions-Hint** (Whisper `initial_prompt`, Kategorie-Feld
  *Transkriptions-Hint*): `Ramipril, Metoprolol, Pantoprazol, Spironolacton,
  Levothyroxin, Bisoprolol`. Das sind Medikamente aus den Diktaten, Whisper
  ist damit im Vorteil. Parakeet kennt keinen solchen Hinweis.
- **Wörterbuch:** die 31 Fachbegriffe der Diktate, Fachbegriff-Korrektur mit
  Schwelle 85 (Standard).

### Kennzahlen

- **Fehlerrate (WER):** Anteil falscher Wörter. Zahlen und Satzzeichen werden
  vorher entfernt, damit „fünf“ und „5“ nicht als Fehler zählen.
- **Fachbegriffe:** Anteil der 27 Fachbegriffe aus der Referenz, die richtig
  geschrieben im Ergebnis stehen.
- **Dosis/Werte:** Medikament mit Dosis (z. B. „Bisoprolol 2,5 mg“), Laborwerte,
  Blutdruck, Ejektionsfraktion, geprüft per Muster. Ein Treffer zählt nur,
  wenn Name **und** Wert stimmen. Ein falsch geschriebener Name zählt
  deshalb auch als verfehlt.

## Ergebnisse

### Genauigkeit

Werte jeweils für die Diktate 3 / 5 / 10 min. „Dosis/Werte“ ist die Summe aller
drei.

| Modell | WER ohne Korrektur | WER mit Wörterbuch | Fachbegriffe mit Wörterbuch | Dosis/Werte mit Wörterbuch |
| --- | --- | --- | --- | --- |
| Whisper large-v3-turbo | 8,8 / 9,5 / 9,2 % | 6,8 / 7,2 / 6,6 % | 96 / 100 / 100 % | 47/51 |
| Whisper large-v3-turbo + Hint | 8,8 / 8,5 / 8,9 % | 6,8 / 6,9 / 6,6 % | 100 / 100 / 100 % | 50/51 |
| Whisper large-v3 | 8,8 / 9,0 / 9,3 % | 6,8 / 6,3 / 6,7 % | 100 / 100 / 96 % | 47/51 |
| Whisper large-v3 + Hint | 8,2 / 8,5 / 8,7 % | 6,8 / 6,2 / 6,6 % | 100 / 100 / 100 % | 51/51 |
| Parakeet TDT 0.6B v3 | 9,9 / 10,6 / 12,4 % | 7,3 / 7,4 / 9,7 % | 96 / 93 / 96 % | 48/51 |

Was die Zahlen nicht direkt zeigen:

- **Parakeet hört Dosierungen meist richtig, schreibt aber Namen falsch**
  („Levotyroxen“, „Pantobrazol“, „Bisopronol“, „Hämogloben“). Genau das
  repariert das Wörterbuch. Ohne Wörterbuch fand Parakeet nur 52–67 % der
  Fachbegriffe, Whisper 74–85 %.
- **Ein echter Dosisfehler bei Parakeet:** „Bisoprolol 2,5 mg“ wurde einmal
  „Bisoprolol 2 mg“. Das kann kein Wörterbuch korrigieren. Bei Whisper waren
  die verbleibenden Fehlstellen im Dosis-Check Schreibweisen der Einheit
  („Mikrogram“), keine falschen Werte.
- **Der Hint hilft Whisper vor allem bei den Medikamentennamen**, die im Hint
  stehen. Mit Wörterbuch schrumpft der Vorteil, weil die Korrektur dieselben
  Namen repariert.

### Geschwindigkeit und Speicher

Gesamtzeit für ein Diktat über den ganzen Weg (VAD, Stückelung, parallele
Anfragen), nach einem Aufwärmlauf. GPU-Speicher je Server-Prozess.

| Modell | 3 min | 5 min | 10 min | GPU-Speicher |
| --- | --- | --- | --- | --- |
| Whisper large-v3-turbo (int8) | 5,3–5,5 s | 9,2 s | 16–17 s | ~1,1 GB im Leerlauf, ~1,9 GB unter Last |
| Whisper large-v3 (int8) | 14,5–15 s | 24,5–26 s | 45–46 s | ~2,1 GB |
| Parakeet TDT 0.6B v3 (FP32) | 1,8–2,1 s | 3,0–3,6 s | 5,6–5,9 s | ~3,5 GB |

Parakeet belegte bis 0.10.3 rund **6,8 GB**, weil Live-Vorschau und
Datei-Transkription das Modell je einmal geladen haben. Seit 0.10.4 teilen
sie sich eine Instanz. Auf der 3060 passte erst danach ein lokales LLM
(Ollama `qwen3:4b`, 3 GB) vollständig auf die GPU; vorher lief es auf der CPU
und Zusammenfassungen liefen in den Timeout.

### Warum large-v3-turbo fast so gut ist wie large-v3

turbo übernimmt den **Encoder** von large-v3 unverändert. Dieser Teil „hört“ das
Audio. Gekürzt wurde der **Decoder**, der daraus Wort für Wort Text erzeugt,
von 32 auf 4 Schichten (809 Mio. statt 1,55 Mrd. Parameter). Weil der Decoder
für jedes Wort einmal läuft, bringt das die Geschwindigkeit. Bei klarer
deutscher Sprache kostet es kaum Genauigkeit. Bei undeutlicher Sprache,
Akzent oder Störgeräuschen kann der größere Decoder von large-v3 mehr aus dem
Zusammenhang erschließen. Das deckt diese Messung nicht ab.

### Whisper: Rechengenauigkeit (`WHISPER_COMPUTE_TYPE`)

Gemessen am 21.10.2026, gleicher Aufbau wie oben, large-v3-turbo mit
Transkriptions-Hint, jede Variante in einem eigenen Server-Prozess.
Fehlerrate für die Diktate 3 / 5 / 10 min.

| Variante | WER ohne Korrektur | WER mit Wörterbuch | Dosis/Werte | 10 min | GPU-Speicher |
| --- | --- | --- | --- | --- | --- |
| turbo `int8` | 8,8 / 8,5 / 8,9 % | 6,8 / 6,9 / 6,6 % | 50/51 | 16,2 s | ~1,2 GB |
| turbo `int8_float16` | 8,8 / 8,5 / 8,9 % | 6,8 / 6,9 / 6,6 % | 50/51 | 17,2 s | ~1,2 GB |
| turbo `float16` | 9,0 / 8,6 / 9,1 % | 7,1 / 7,0 / 6,8 % | 50/51 | 17,5 s | ~2,2 GB |
| large-v3 `int8` (Vergleich) | 8,2 / 8,5 / 8,7 % | 6,8 / 6,2 / 6,6 % | 51/51 | 45,9 s | ~2,1 GB |

- **int8 kostet hier keine Genauigkeit.** float16 war minimal schlechter; die
  Unterschiede von wenigen Zehnteln liegen im Rauschen dieser kleinen Messung.
- `int8` und `int8_float16` lieferten auf der GPU identische Texte.
- Der Vorteil von int8 ist vor allem der **Speicher** (halb so viel wie
  float16), auf dieser Karte war es zusätzlich am schnellsten. Auf der CPU ist
  int8 ohnehin die schnellste Wahl.
- Die eine Lücke bei Dosis/Werte ist bei allen turbo-Varianten dieselbe:
  „75 Mikrogram“ statt „Mikrogramm“, ein Schreibfehler der Einheit, kein
  falscher Wert.

Anders als bei Parakeet (siehe unten) rechnet CTranslate2 int8 auf der GPU
nativ, es landen keine Rechenschritte auf der CPU.

### Parakeet int8 (`PARAKEET_QUANTIZATION`)

| | FP32 | int8 |
| --- | --- | --- |
| GPU, 9-s-Segment (Live-Takt 0,4 s) | 0,07 s | 0,73 s |
| GPU, 30 s Audio | 0,20 s | 2,4 s |
| GPU-Speicher | 3,7 GB | 1,4 GB |
| CPU, 30 s Audio | 3,5 s | 2,6 s |
| RAM (CPU) | 3,1 GB | 1,9 GB |

- **Auf der GPU** fügt onnxruntime beim int8-Modell 742 Kopierknoten zwischen
  GPU und CPU ein (FP32: 2). Die meisten Rechenschritte laufen auf der CPU, die
  Live-Vorschau käme nicht mehr hinterher.
- **Auf der CPU** ist int8 schneller und kleiner, erkennt aber Medikamente
  schlechter („Ramibril“, „mit Formin“, „Metroprolol“). Das CPU-Image ist nur
  für Demos gedacht und nutzt int8 als Standard; das GPU-Image bleibt bei
  FP32.

### Fachbegriff-Korrektur (Wörterbücher)

Bis 0.10.3 verglich die Korrektur nur den Kölner-Phonetik-Code. Der streicht
Vokale und fasst Laute zusammen, deshalb bekommen unterschiedliche Wörter
ähnliche Codes. Auf einem **fehlerfreien** Diktat:

| Wörterbuch | Falsche Ersetzungen bis 0.10.3 | seit 0.10.4 |
| --- | --- | --- |
| 27 Fachbegriffe | 16 (z. B. „Notaufnahme“ → „Metformin“, „Indikation“ → „Appendektomie“) | 0 |
| + 1.000 Zusatzwörter | 299 | 0 |

Seit 0.10.4 muss eine Ersetzung ähnlich **klingen und geschrieben** sein
(beides ≥ 75, Mittelwert ≥ Schwelle), die Länge darf höchstens ±25 % abweichen,
die Wortzahl muss passen. Richtig geschriebene Begriffe bleiben unangetastet,
auch gebeugt („Myokardinfarkts“). Die 15 echten Schreibfehler aus den
Messungen oben werden weiter repariert. Bis 0.10.3 hat die Korrektur die
Fehlerrate kaum verändert, weil sich falsche und richtige Ersetzungen
aufgehoben haben; jetzt senkt sie sie um 2–3 Prozentpunkte.

**Wie groß darf ein Wörterbuch sein?** Technisch bis 50.000 Begriffe (je bis
200 Zeichen, Upload bis 5 MB). Die Korrektur braucht für ein 10-min-Diktat
etwa 0,1 s bei 1.000 Begriffen und 7 s bei 50.000. Fachlich sind kleine,
fokussierte Listen besser: Mit 20.000 Zufallswörtern wurde einmal „besteht“
durch einen Eintrag ersetzt, der fast gleich geschrieben war. Bei Schwelle
90 passiert das nicht mehr, dafür werden 3 von 15 echten Fehlern nicht mehr
repariert. ICD/OPS-Kataloge besser als Wortliste einspielen statt mit den
langen Beschreibungstexten; die Korrektur vergleicht Fenster von 1–3 Wörtern.

## Empfehlung

- **Standard:** Whisper large-v3-turbo in `int8` für die finale Transkription, mit
  kurzem Transkriptions-Hint pro Kategorie und Wörterbüchern für die
  Fachbegriffe. Fachbegriff-Korrektur einschalten (Administration → Dienste →
  Whisper → Final), Schwelle 85.
- **Parakeet als finale Transkription** ist eine Option, wenn GPU-Speicher
  knapp ist oder der Whisper-Container entfallen soll. Umstellen in
  Administration → Dienste → Whisper → Final: Endpunkt
  `http://parakeet:5001/v1` **und** Modellname `nemo-parakeet-tdt-0.6b-v3`
  (mit dem Standardnamen `large-v3-turbo` schlägt jeder Aufruf fehl). Dabei
  entfällt die Wirkung des Transkriptions-Hints, und die Sprache lässt sich
  nicht festlegen (Parakeet erkennt sie selbst). Vorher mit echten Diktaten
  prüfen, ob Dosierungen stimmen.
- **large-v3** lohnt sich nach diesen Daten nicht: gleiche Genauigkeit,
  dreifache Rechenzeit. Ob es bei echten, undeutlichen Diktaten Vorteile
  bringt, muss eine Messung mit echten Aufnahmen zeigen.

## Einschränkungen

- **Synthetische Stimme:** eine TTS-Stimme, gleichmäßig, ohne Störgeräusche,
  ohne Akzent. Echte Diktate sind schwieriger. Unterschiede zwischen den
  Modellen können dort größer sein, besonders bei undeutlicher Sprache.
- **Kleine Stichprobe:** drei Diktate mit wiederkehrenden Absätzen. Ein
  einzelner Dosisfehler ist ein Warnsignal, keine Statistik.
- **Wörterbuch passt genau:** Es enthielt genau die Begriffe der Diktate. In
  der Praxis fehlen Begriffe oder es sind viel mehr, was die Wirkung ändert.
- **Eine GPU:** Die Zeiten gelten für eine RTX 3060 und ein Diktat zur Zeit.
  Unter Last mit vielen Diktaten verschiebt sich das Verhältnis.

Wer echte Diktate prüfen will: 10–20 Aufnahmen aus dem Alltag (mit
Einwilligung oder nachgesprochen, ohne Patientendaten) und je eine von Hand
korrigierte Fassung als Referenz. Ausschlaggebend sind falsche Medikamente und
Dosierungen, nicht die allgemeine Fehlerrate.
