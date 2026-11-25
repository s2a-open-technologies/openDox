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

Deterministic consistency check between two versions of a dictation.

Compares a reference text with a candidate (e.g. the source transcript with
its machine translation, or a translation with a German reference) on the
details a translation must never change: numbers (doses, values), negations
and medical terms. No model involved — the result is meant to point a
reviewer at suspicious spots, not to judge the translation as a whole.

Numbers are compared language-independently (digits only). Negations and
terms are compared on German text, the target language of openDox.
"""

# Standard library
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

# Third party
from rapidfuzz import fuzz

# A number with optional decimal part ("2,5", "2.5", "1000") or German
# thousands separators ("1.000", "12.500").
_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")
# Dot followed by groups of exactly three digits = German thousands separator.
_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")

# German negation and prohibition markers. "vermeiden" is included because
# "X ist zu vermeiden" losing its meaning in translation is as dangerous as a
# dropped "nicht".
_NEGATION = re.compile(
    r"\b(?:kein(?:e|en|em|er|es)?|nicht|nie|niemals|ohne|noch nicht|"
    r"verneint|verneinen|negiert|leugnet|leugnen|bestreitet|bestreiten|"
    r"unbekannt|ausgeschlossen|vermeiden|vermieden|meiden|abzusehen)\b",
    re.IGNORECASE,
)
# "weder X noch Y" negates two things, like "kein X und kein Y".
_NEITHER = re.compile(r"\bweder\b", re.IGNORECASE)

# Fuzzy threshold for a term to count as present (allows inflection and
# small spelling variants like "Spironolakton"/"Spironolacton").
TERM_MATCH_MIN = 85


# Arabic decimal separator "٫" and thousands separator "٬" → German style.
_ARABIC_SEPARATORS = str.maketrans({"\u066b": ",", "\u066c": "."})


def _ascii_digits(raw: str) -> str:
    """Map any Unicode digit (e.g. Arabic-Indic "٣") to its ASCII form."""
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in raw)


def _normalize_number(raw: str) -> str:
    raw = _ascii_digits(raw)
    if _THOUSANDS.match(raw):
        return raw.replace(".", "")
    return raw.replace(",", ".")


def extract_numbers(text: str) -> Counter:
    """Return the numbers in ``text`` as a multiset.

    Decimal comma and point are treated alike ("2,5" == "2.5"); a dot followed
    by groups of three digits is a German thousands separator
    ("1.000" == "1000").
    """
    text = text.translate(_ARABIC_SEPARATORS)
    return Counter(_normalize_number(m) for m in _NUMBER.findall(text))


def count_negations(text: str) -> int:
    """Return the number of German negation/prohibition markers in ``text``."""
    return len(_NEGATION.findall(text)) + 2 * len(_NEITHER.findall(text))


def term_present(term: str, text: str) -> bool:
    """Return whether ``term`` (or a close variant) occurs in ``text``.

    ``term`` may list accepted synonyms separated by "|", e.g.
    "Pneumonie|Lungenentzündung"; any of them counts.
    """
    lowered = text.lower()
    for variant in term.lower().split("|"):
        if variant in lowered or fuzz.partial_ratio(variant, lowered) >= TERM_MATCH_MIN:
            return True
    return False


@dataclass
class CheckResult:
    """Differences between a reference and a candidate text."""

    missing_numbers: list[str] = field(default_factory=list)
    extra_numbers: list[str] = field(default_factory=list)
    reference_negations: int = 0
    candidate_negations: int = 0
    missing_terms: list[str] = field(default_factory=list)

    @property
    def negations_lost(self) -> int:
        """Negations the candidate has fewer than the reference (never negative)."""
        return max(0, self.reference_negations - self.candidate_negations)

    @property
    def ok(self) -> bool:
        """True if nothing suspicious was found."""
        return not (
            self.missing_numbers
            or self.extra_numbers
            or self.negations_lost
            or self.missing_terms
        )


def compare(
    reference: str,
    candidate: str,
    terms: list[str] | None = None,
    check_negations: bool = True,
) -> CheckResult:
    """Compare ``candidate`` against ``reference``.

    Args:
        reference: Text whose details must be preserved.
        candidate: Text to check (e.g. the translation).
        terms: Medical terms that must appear in the candidate.
        check_negations: Count German negations; turn off when the two
            texts are in different languages.

    Returns:
        The differences found.
    """
    ref_numbers = extract_numbers(reference)
    cand_numbers = extract_numbers(candidate)
    result = CheckResult(
        missing_numbers=sorted((ref_numbers - cand_numbers).elements()),
        extra_numbers=sorted((cand_numbers - ref_numbers).elements()),
        missing_terms=[t for t in terms or [] if not term_present(t, candidate)],
    )
    if check_negations:
        result.reference_negations = count_negations(reference)
        result.candidate_negations = count_negations(candidate)
    return result
