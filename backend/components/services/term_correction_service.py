"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import re

from rapidfuzz import fuzz

from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+")

# Kölner Phonetik code table. Context-dependent letters (C, P, D/T, X) are
# handled separately in ``koelner_phonetik``.
_VOWELS = set("AEIOUJYÄÖÜ")
_SIMPLE = {
    "B": "1",
    "F": "3",
    "V": "3",
    "W": "3",
    "G": "4",
    "K": "4",
    "Q": "4",
    "L": "5",
    "M": "6",
    "N": "6",
    "R": "7",
    "S": "8",
    "Z": "8",
    "ß": "8",
}


def koelner_phonetik(word: str) -> str:
    """Encode a German word as a Kölner Phonetik digit code.

    Similar-sounding words (typical ASR mishearings) map to the same or a
    very similar code, e.g. "Meier" and "Maier" both encode to "67". Only
    letters carry a code; digits, punctuation and whitespace are skipped
    (so multi-word glossary terms can be passed in directly).
    """
    letters = word.upper()
    codes: list[str] = []

    for i, c in enumerate(letters):
        prev_c = letters[i - 1] if i > 0 else ""
        next_c = letters[i + 1] if i + 1 < len(letters) else ""

        if c in _VOWELS:
            codes.append("0")
        elif c == "H":
            continue
        elif c == "P":
            codes.append("3" if next_c == "H" else "1")
        elif c in ("D", "T"):
            codes.append("8" if next_c in ("C", "S", "Z") else "2")
        elif c == "X":
            codes.append("8" if prev_c in ("C", "K", "Q") else "48")
        elif c == "C":
            if i == 0:
                codes.append("4" if next_c in "AHKLOQRUX" else "8")
            elif prev_c in ("S", "Z"):
                codes.append("8")
            else:
                codes.append("4" if next_c in "AHKOQUX" else "8")
        elif c in _SIMPLE:
            codes.append(_SIMPLE[c])
        # Anything else (digits, punctuation, unknown chars) is skipped.

    # Collapse immediately-repeated digits (H is already transparent since
    # it never entered `codes`).
    collapsed: list[str] = []
    for code in codes:
        if not collapsed or collapsed[-1] != code:
            collapsed.append(code)

    # Drop all "0"s except a leading one.
    result = collapsed[:1] + [c for c in collapsed[1:] if c != "0"]

    return "".join(result)


def parse_glossary(whisper_prompt: str) -> list[str]:
    """Parse a category's free-text ``whisper_prompt`` into a glossary list.

    Splits on comma/semicolon/newline, trims whitespace, drops very short
    tokens (<3 chars, too ambiguous phonetically) and duplicates.
    """
    if not whisper_prompt:
        return []

    seen: set[str] = set()
    glossary: list[str] = []
    for raw in re.split(r"[,;\n]+", whisper_prompt):
        term = raw.strip()
        if len(term) < 3:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        glossary.append(term)

    return glossary


def correct_terms(
    text: str, glossary: list[str], threshold: float
) -> tuple[str, list[dict]]:
    """Fuzzy-correct mistranscribed glossary terms in ``text``.

    Slides every 1-3 word window over ``text``, compares each window's
    Kölner Phonetik code against the glossary's precomputed codes via
    ``rapidfuzz.fuzz.ratio``, and collects every window scoring at least
    ``threshold`` (0-100 scale) as a replacement candidate. Candidates are
    then applied highest-score-first, skipping any candidate that overlaps
    a span already claimed by a better-scoring one — this matters because
    a mediocre 2-3 word window can otherwise outscore-by-being-tried-first
    a near-exact 1-word match starting one token later.

    Returns:
        Tuple of (corrected_text, replacements), where replacements is a
        list of ``{"original", "replacement", "score"}`` dicts for logging,
        ordered by position in the text.
    """
    if not text or not glossary:
        return text, []

    glossary_codes = [
        (term, code) for term in glossary if (code := koelner_phonetik(term))
    ]
    if not glossary_codes:
        return text, []

    tokens = list(_WORD_RE.finditer(text))
    if not tokens:
        return text, []

    # Words the text already spells exactly like a glossary term are
    # "protected" — no window overlapping them becomes a candidate. Without
    # this, an already-correct term glued to a neighboring word (e.g.
    # "Sertralin wurde") can still score above threshold against that same
    # term, since the fuzzy compare has no notion of "this part is already
    # right, don't touch it".
    protected_spans = [
        (m.start(), m.end())
        for term in glossary
        for m in re.finditer(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
    ]

    def _overlaps_protected(span_start: int, span_end: int) -> bool:
        return any(span_start < e and span_end > s for s, e in protected_spans)

    n_tokens = len(tokens)
    candidates: list[dict] = []

    for i in range(n_tokens):
        for window in (1, 2, 3):
            if i + window > n_tokens:
                continue
            span_start = tokens[i].start()
            span_end = tokens[i + window - 1].end()
            if _overlaps_protected(span_start, span_end):
                continue
            window_text = text[span_start:span_end]
            code = koelner_phonetik(window_text)
            if not code:
                continue

            best_term, best_score = None, 0.0
            for term, term_code in glossary_codes:
                score = fuzz.ratio(code, term_code)
                if score > best_score:
                    best_term, best_score = term, score

            if (
                best_term is not None
                and best_score >= threshold
                and best_term.lower() != window_text.lower()
            ):
                candidates.append(
                    {
                        "span_start": span_start,
                        "span_end": span_end,
                        "term": best_term,
                        "score": best_score,
                        "window_text": window_text,
                    }
                )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    selected: list[dict] = []
    for cand in candidates:
        if any(
            cand["span_start"] < s["span_end"] and cand["span_end"] > s["span_start"]
            for s in selected
        ):
            continue
        selected.append(cand)

    if not selected:
        return text, []

    selected.sort(key=lambda c: c["span_start"])
    result_parts: list[str] = []
    replacements: list[dict] = []
    last_end = 0
    for sel in selected:
        result_parts.append(text[last_end : sel["span_start"]])
        result_parts.append(sel["term"])
        replacements.append(
            {
                "original": sel["window_text"],
                "replacement": sel["term"],
                "score": sel["score"],
            }
        )
        last_end = sel["span_end"]
    result_parts.append(text[last_end:])

    return "".join(result_parts), replacements
