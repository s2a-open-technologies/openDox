# openDox-Handbücher

Quelle der drei Handbücher für Anwender und Betreiber. Geschrieben wird
Markdown; DOCX, PDF und XWiki-Seiten werden daraus erzeugt.

| Handbuch | Datei | Zielgruppe |
|---|---|---|
| Benutzerhandbuch | `benutzer/handbuch.md` | Alle, die diktieren und Texte bearbeiten |
| Administrationshandbuch (geplant) | `administration/handbuch.md` | Administratoren in der Weboberfläche |
| Installations- und Betriebshandbuch (geplant) | `installation/handbuch.md` | IT / Betrieb |

Ein neues Handbuch ist ein Ordner mit einer `handbuch.md`; das Build-Script
findet es von selbst.

## Bauen

```bash
scripts/build_handbuch.sh                  # alle, DOCX + PDF
scripts/build_handbuch.sh benutzer         # nur eins
FORMATS="docx xwiki" scripts/build_handbuch.sh
```

Ergebnis in `build/handbuch/` (nicht versioniert). Benötigt nur Docker
(Pandoc `pandoc/core`, Typst `ghcr.io/typst/typst`) und ImageMagick für die
Bild-Platzhalter. Die Versionsnummer kommt aus `pyproject.toml`.

## Release

Jedes Release bringt die Handbücher mit: `.github/workflows/release.yml`
baut beim Push eines `vX.Y.Z`-Tags die PDFs (Version aus dem Tag) und hängt
sie als Assets an das GitHub Release. Schlägt der Build fehl, schlägt das
Release fehl.

## Layout

- **PDF** (Hauptausgabe): `vorlage/handbuch.typst`, ein Pandoc-Template für
  Typst. Deckblatt, Kopf-/Fußzeile, Farben (Navy `#1A2B6D`, Cyan `#00CED1`),
  Tabellen- und Bildstil stehen dort. Die PDF wird bewusst nicht über
  Word/OnlyOffice erzeugt, damit sie bei jedem Build gleich aussieht.
- **Logo**: `vorlage/s2a-open-technologies.svg` (weiß, fürs Deckblatt); die
  dunkle Variante für die Kopfzeile erzeugt das Build-Script.
- **Schriften**: `vorlage/fonts/` (Poppins für Überschriften, Lato für Text,
  beide SIL Open Font License, Lizenztexte liegen daneben).
- **DOCX** (bearbeitbare Nebenausgabe): optional `vorlage/reference.docx` mit
  Pandoc-Formatvorlagen (`Title`, `Heading 1`–`3`, `Body Text`, …).

## Schreiben

- Sie-Form, sachlich, kurze Sätze. UI-Bezeichnungen **fett** und exakt wie in
  `frontend/src/i18n/locales/de/*.json`.
- Bilder: `![Bildunterschrift](bilder/<handbuch>/NN-name.png)`, jedes neue
  Bild auch in `screenshots.md` eintragen.
- Der Hinweis „Kein Medizinprodukt“ gehört in jedes Handbuch.
- Ändert sich die Oberfläche, das Handbuch im selben Commit nachziehen.
