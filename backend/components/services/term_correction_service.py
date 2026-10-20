"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
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

from rapidfuzz import fuzz, process

from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+")

# Acceptance rules for a replacement, calibrated on synthetic dictations: on
# the error-free reference texts no word may change, while the real ASR
# misspellings ("Levotyroxen", "Pantobrazol", "mit Formin") are still fixed.
# See correct_terms() for why the phonetic code alone is not enough.
PHONETIC_MIN = 75.0
SPELLING_MIN = 75.0
LENGTH_TOLERANCE = 1.25
MIN_WINDOW_LETTERS = 4
# German inflection endings a correctly spelled term may carry in the text.
_INFLECTIONS = ("ern", "es", "en", "er", "s", "n", "e")


def _letters(text: str) -> str:
    """Lowercase letters only (no spaces/punctuation), for spelling compares."""
    return "".join(_WORD_RE.findall(text)).lower()


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


def correct_terms(
    text: str, glossary: list[str], threshold: float
) -> tuple[str, list[dict]]:
    """Fuzzy-correct mistranscribed glossary terms in ``text``.

    Slides every 1-3 word window over ``text`` and accepts a glossary term as
    replacement only if the window both *sounds* and *is spelled* like it:

    - Kölner Phonetik codes compared via ``rapidfuzz.fuzz.ratio`` score at
      least ``PHONETIC_MIN``, the lowercase letters at least ``SPELLING_MIN``,
      and their mean reaches ``threshold`` (the admin setting, 0-100);
    - the letter count differs by at most ``LENGTH_TOLERANCE``;
    - the window has the term's word count or one word more (ASR splits like
      "mit Formin" for "Metformin"), and at least ``MIN_WINDOW_LETTERS``.

    The phonetic code alone is far too lenient: it drops vowels and merges
    sounds, so unrelated words share codes — matching on it alone turned an
    error-free "Notaufnahme" into "Metformin" and "Indikation" into
    "Appendektomie". Terms already spelled correctly in the text, including
    inflected forms ("Myokardinfarkts"), are protected and never touched.

    Candidates are applied highest-score-first, skipping any that overlaps a
    span already claimed by a better-scoring one.

    Returns:
        Tuple of (corrected_text, replacements), where replacements is a
        list of ``{"original", "replacement", "score"}`` dicts for logging,
        ordered by position in the text.
    """
    # Terms under 3 characters are too ambiguous phonetically to correct to.
    glossary = [term for term in glossary if len(term.strip()) >= 3]
    if not text or not glossary:
        return text, []

    # Spelling first: a term needs SPELLING_MIN anyway, and that cut keeps
    # far fewer candidates than the phonetic one (codes are short, so many
    # terms sound alike) — this keeps catalog-sized dictionaries fast. The
    # phonetic code is computed once per term, in glossary order (first term
    # wins a tie).
    entries = []
    for term in glossary:
        code = koelner_phonetik(term)
        if code:
            entries.append((term, _letters(term), code, len(_WORD_RE.findall(term))))
    if not entries:
        return text, []
    entry_letters = [entry[1] for entry in entries]

    tokens = list(_WORD_RE.finditer(text))
    if not tokens:
        return text, []

    # Words the text already spells like a glossary term — also inflected —
    # are "protected": no window overlapping them becomes a candidate.
    # Otherwise "Sertralin wurde" can still score against "Sertralin", and a
    # correct genitive "Myokardinfarkts" would be "fixed" to the base form.
    # Only terms whose first word (or its stem) occurs in the text are
    # searched for, so this stays cheap for thousands of terms.
    text_stems = set()
    for m in tokens:
        word = m.group(0).lower()
        text_stems.add(word)
        text_stems.update(
            word[: -len(suffix)] for suffix in _INFLECTIONS if word.endswith(suffix)
        )
    protected_spans = []
    for term in glossary:
        first_word = _WORD_RE.search(term)
        if not first_word or first_word.group(0).lower() not in text_stems:
            continue
        pattern = rf"\b{re.escape(term)}(?:{'|'.join(_INFLECTIONS)})?\b"
        protected_spans.extend(
            (m.start(), m.end())
            for m in re.finditer(pattern, text, flags=re.IGNORECASE)
        )

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
            window_letters = _letters(window_text)
            if len(window_letters) < MIN_WINDOW_LETTERS:
                continue
            code = koelner_phonetik(window_text)
            if not code:
                continue

            best_term, best_score, best_idx = None, 0.0, -1
            for _, spelling, idx in process.extract(
                window_letters,
                entry_letters,
                scorer=fuzz.ratio,
                score_cutoff=SPELLING_MIN,
                limit=None,
            ):
                term, term_letters, term_code, term_words = entries[idx]
                if window not in (term_words, term_words + 1):
                    continue
                if window_letters == term_letters:
                    continue
                ratio = len(window_letters) / len(term_letters)
                if not 1 / LENGTH_TOLERANCE <= ratio <= LENGTH_TOLERANCE:
                    continue
                phonetic = fuzz.ratio(code, term_code)
                if phonetic < PHONETIC_MIN:
                    continue
                score = (phonetic + spelling) / 2
                # Ties go to the earlier glossary entry.
                if score >= threshold and (
                    score > best_score or (score == best_score and idx < best_idx)
                ):
                    best_term, best_score, best_idx = term, score, idx

            if best_term is not None:
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
