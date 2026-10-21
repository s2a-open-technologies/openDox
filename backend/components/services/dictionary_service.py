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

Dictionaries (term lists for the phonetic term correction).

File format accepted by ``parse_upload`` (also shown in the UI and the user
manual — keep them in sync):

- ``.txt`` or ``.csv``, UTF-8 (a BOM is fine), at most ``MAX_UPLOAD_BYTES``.
- One term per line; empty lines and lines starting with ``#`` are ignored.
  Commas inside a term are kept (ICD texts contain them).
- ``.csv``: the first column is the term; ``;`` or ``,`` as delimiter,
  quoting is honored.
- Surrounding whitespace is stripped, duplicates (case-insensitive) dropped.
"""

import csv
import io

from sqlmodel import Session, select

from backend.components.models.categories import Categories
from backend.components.models.dictionary import CategoryDictionaryLink, Dictionary

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TERMS = 50_000
MAX_TERM_LENGTH = 200
UPLOAD_EXTENSIONS = (".txt", ".csv")


class _SemicolonCsv(csv.excel):
    delimiter = ";"


class DictionaryInputError(ValueError):
    """Invalid dictionary input; ``code`` maps to an ``errors:<code>`` entry."""

    def __init__(self, code: str, message: str, **params):
        """Store the error code, message and message parameters."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.params = params


def normalize_terms(terms: list[str]) -> list[str]:
    """Strip, drop empty/comment entries and case-insensitive duplicates.

    Raises:
        DictionaryInputError: Too many terms or a term that is too long.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in terms:
        term = raw.strip()
        if not term or term.startswith("#"):
            continue
        if len(term) > MAX_TERM_LENGTH:
            raise DictionaryInputError(
                "dictionary_term_too_long",
                f"Term longer than {MAX_TERM_LENGTH} characters: {term[:40]}…",
                max=MAX_TERM_LENGTH,
            )
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    if len(result) > MAX_TERMS:
        raise DictionaryInputError(
            "dictionary_too_large",
            f"A dictionary may hold at most {MAX_TERMS} terms",
            max=MAX_TERMS,
        )
    return result


def parse_terms(text: str | None) -> list[str]:
    """Split stored/typed dictionary text into terms, one per line."""
    if not text:
        return []
    return normalize_terms(text.splitlines())


def parse_upload(filename: str, data: bytes) -> list[str]:
    """Parse an uploaded ``.txt``/``.csv`` term file (format: module docstring).

    Raises:
        DictionaryInputError: Wrong file type, too large, not UTF-8, or the
            limits of ``normalize_terms`` are exceeded.
    """
    name = (filename or "").lower()
    if not name.endswith(UPLOAD_EXTENSIONS):
        raise DictionaryInputError(
            "dictionary_upload_invalid", "Only .txt and .csv files are supported"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise DictionaryInputError(
            "dictionary_upload_too_big",
            "File is larger than 5 MB",
            max_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise DictionaryInputError(
            "dictionary_upload_invalid", "File is not UTF-8 encoded"
        ) from e

    if not name.endswith(".csv"):
        return parse_terms(text)

    # Comment lines are dropped before the CSV reader sees them, so a
    # commented-out header never confuses delimiter detection.
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:50]), delimiters=";,")
    except csv.Error:
        # Single-column files give the sniffer nothing to detect.
        dialect = _SemicolonCsv
    rows = csv.reader(io.StringIO("\n".join(lines)), dialect)
    return normalize_terms([row[0] for row in rows if row])


def serialize_terms(terms: list[str]) -> str:
    """Store terms as one per line (the ``Dictionary.terms`` format)."""
    return "\n".join(terms)


def set_terms(dictionary: Dictionary, terms: list[str]) -> None:
    """Replace a dictionary's terms (already normalized) and its count."""
    dictionary.terms = serialize_terms(terms)
    dictionary.term_count = len(terms)


def category_ids_by_dictionary(
    db: Session, dictionary_ids: list[int]
) -> dict[int, list[int]]:
    """Map each dictionary id to the ids of the categories it is attached to."""
    result: dict[int, list[int]] = {d: [] for d in dictionary_ids}
    if not dictionary_ids:
        return result
    links = db.exec(
        select(CategoryDictionaryLink).where(
            CategoryDictionaryLink.dictionary_id.in_(dictionary_ids)
        )
    ).all()
    for link in links:
        result[link.dictionary_id].append(link.category_id)
    return result


def dictionary_ids_by_category(
    db: Session, category_ids: list[int]
) -> dict[int, list[int]]:
    """Map each category id to the ids of its attached dictionaries."""
    result: dict[int, list[int]] = {c: [] for c in category_ids}
    if not category_ids:
        return result
    links = db.exec(
        select(CategoryDictionaryLink).where(
            CategoryDictionaryLink.category_id.in_(category_ids)
        )
    ).all()
    for link in links:
        result[link.category_id].append(link.dictionary_id)
    return result


def set_category_dictionaries(
    db: Session, category_id: int, dictionary_ids: list[int]
) -> None:
    """Replace the dictionaries attached to a category (caller commits)."""
    existing = db.exec(
        select(CategoryDictionaryLink).where(
            CategoryDictionaryLink.category_id == category_id
        )
    ).all()
    for link in existing:
        db.delete(link)
    for dictionary_id in dict.fromkeys(dictionary_ids):
        db.add(
            CategoryDictionaryLink(category_id=category_id, dictionary_id=dictionary_id)
        )


def glossary_for_category(
    db: Session, category: Categories | None, user_id: int | None = None
) -> list[str]:
    """Return the merged, de-duplicated term-correction glossary of a recording.

    Sources: the dictionaries attached to the recording's category, plus every
    personal dictionary of the recording's owner (``user_id``) — personal
    dictionaries always apply, whatever the category; global ones only through
    the categories they are attached to. Category dictionaries come first, so
    ties in the correction go to them.
    """
    dictionaries: list[Dictionary] = []
    if category is not None and category.id is not None:
        dictionaries.extend(
            db.exec(
                select(Dictionary)
                .join(
                    CategoryDictionaryLink,
                    CategoryDictionaryLink.dictionary_id == Dictionary.id,
                )
                .where(CategoryDictionaryLink.category_id == category.id)
                .order_by(Dictionary.id)
            ).all()
        )
    if user_id is not None:
        attached = {d.id for d in dictionaries}
        dictionaries.extend(
            d
            for d in db.exec(
                select(Dictionary)
                .where(Dictionary.user_id == user_id)
                .order_by(Dictionary.id)
            ).all()
            if d.id not in attached
        )
    terms: list[str] = []
    seen: set[str] = set()
    for dictionary in dictionaries:
        for term in (dictionary.terms or "").splitlines():
            key = term.lower()
            if term and key not in seen:
                seen.add(key)
                terms.append(term)
    return terms
