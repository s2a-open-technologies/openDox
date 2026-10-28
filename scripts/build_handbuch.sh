#!/usr/bin/env bash
# Baut die Handbücher aus docs/handbuch/*/handbuch.md nach build/handbuch/.
#
#   scripts/build_handbuch.sh              # alle Handbücher, PDF + DOCX
#   scripts/build_handbuch.sh benutzer     # nur eins
#   FORMATS="pdf xwiki" scripts/build_handbuch.sh
#
# Pandoc und Typst laufen als Docker-Images, lokal ist nur Docker und
# ImageMagick nötig. Die PDF wird über Typst gesetzt (Layout:
# docs/handbuch/vorlage/handbuch.typst), nicht über Word/OnlyOffice, damit sie
# bei jedem Build gleich aussieht. Die DOCX ist eine bearbeitbare Nebenausgabe
# (Layout aus vorlage/reference.docx, falls vorhanden).
# Fehlende Screenshots werden als grauer Platzhalter erzeugt; die Platzhalter
# landen nur im Build-Ordner, nicht in docs/.
set -euo pipefail

PANDOC_IMAGE="${PANDOC_IMAGE:-pandoc/core:3.6}"
TYPST_IMAGE="${TYPST_IMAGE:-ghcr.io/typst/typst:v0.13.1}"
FORMATS="${FORMATS:-pdf docx}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/docs/handbuch"
OUT="$ROOT/build/handbuch"

VERSION="${OPENDOX_VERSION:-$(grep -m1 '^version' "$ROOT/pyproject.toml" | cut -d'"' -f2)}"
DATE="$(date +%d.%m.%Y)"

if [ $# -gt 0 ]; then
  BOOKS=("$@")
else
  # Alle Handbücher, die es gibt: jeder Unterordner mit einer handbuch.md
  BOOKS=()
  for md in "$SRC"/*/handbuch.md; do
    [ -f "$md" ] && BOOKS+=("$(basename "$(dirname "$md")")")
  done
fi

# Kein Aufräumen: Ausgaben werden überschrieben, ein echter Screenshot ersetzt
# beim Kopieren einen früheren Platzhalter gleichen Namens.
mkdir -p "$OUT/assets" "$OUT/bilder"
# "/." statt nur des Ordners: sonst kopiert cp ab dem zweiten Build nach
# bilder/bilder/, und die alten Platzhalter bleiben in der PDF.
cp -r "$SRC/bilder/." "$OUT/bilder/"

# Das S2A-Logo ist weiß (für dunkle Flächen, Deckblatt); für die Kopfzeile
# auf weißem Grund wird die Schrift in Navy umgefärbt.
cp "$SRC/vorlage/s2a-open-technologies.svg" "$OUT/assets/s2a-logo-white.svg"
sed 's/fill="#ffffff"/fill="#1A2B6D"/g' "$SRC/vorlage/s2a-open-technologies.svg" \
  > "$OUT/assets/s2a-logo-dark.svg"

# Platzhalter für jedes referenzierte, aber noch fehlende Bild
for book in "${BOOKS[@]}"; do
  grep -oE '\]\(bilder/[^)]+\)' "$SRC/$book/handbuch.md" | sed -E 's/^\]\(//; s/\)$//' |
    while read -r img; do
      if [ ! -f "$SRC/$img" ]; then
        mkdir -p "$(dirname "$OUT/$img")"
        convert -size 1600x900 xc:'#e5e7eb' -gravity center -fill '#6b7280' \
          -pointsize 48 -annotate 0 "Screenshot fehlt\n$(basename "$img")" "$OUT/$img"
        echo "  Platzhalter: $img"
      fi
    done
done

REFDOC=()
if [ -f "$SRC/vorlage/reference.docx" ]; then
  REFDOC=(--reference-doc=vorlage/reference.docx)
fi

pandoc() {
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$SRC:/src:ro" -v "$OUT:/out" -w /src \
    --entrypoint pandoc "$PANDOC_IMAGE" \
    --resource-path=/out:/src "$@"
}

typst() {
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$OUT:/out" -v "$SRC/vorlage/fonts:/fonts:ro" -w /out \
    --entrypoint typst "$TYPST_IMAGE" "$@"
}

for book in "${BOOKS[@]}"; do
  # Dateiname aus dem Ordnernamen, mit Fugen-s wo das Deutsche eins verlangt
  case "$book" in
    administration) label="Administrationshandbuch" ;;
    installation)   label="Installationshandbuch" ;;
    *)              label="${book^}handbuch" ;;
  esac
  name="openDox-$label-$VERSION"
  args=("$book/handbuch.md" --metadata-file=metadata.yaml
        -M version="$VERSION" -M stand="$DATE")
  for fmt in $FORMATS; do
    case "$fmt" in
      pdf)
        pandoc "${args[@]}" --template=vorlage/handbuch.typst -t typst \
          -o "/out/$name.typ"
        typst compile --root /out --font-path /fonts --ignore-system-fonts \
          "$name.typ" "$name.pdf"
        echo "→ build/handbuch/$name.pdf" ;;
      docx)
        pandoc "${args[@]}" -M date="Version $VERSION · Stand $DATE" "${REFDOC[@]}" \
          --toc --toc-depth=2 --number-sections -o "/out/$name.docx"
        echo "→ build/handbuch/$name.docx" ;;
      xwiki)
        pandoc "${args[@]}" -t xwiki -o "/out/$name.xwiki"
        echo "→ build/handbuch/$name.xwiki" ;;
      *) echo "Unbekanntes Format: $fmt" >&2; exit 1 ;;
    esac
  done
done
