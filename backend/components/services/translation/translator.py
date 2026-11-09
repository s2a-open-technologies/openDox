"""openDox - Medical transcription platform
Copyright (C) 2026  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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

Translate a dictation sentence by sentence with the configured LLM.

The sentences go to the model in numbered blocks and come back as a JSON
array, so every translated sentence stays paired with its source (the web UI
shows them side by side). If the model returns something else or the wrong
number of sentences, that block is translated again one sentence at a time.
Each pair is then checked for numbers that went missing or appeared
(``check.compare``); negations are not compared, the two texts are in
different languages.

The prompt is the one that won ``bench/translation_bench.py`` (literal, no
omissions, no corrections, numbers exact), generalised to any source and
target language.
"""

# Standard library
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Callable

# Custom
from backend.components.services.translation.check import compare
from backend.components.services.translation.segmenter import (
    join_sentences,
    split_sentences,
)

# (system prompt, user message) -> model answer
Complete = Callable[[str, str], str]

BLOCK_SIZE = 20

LANGUAGE_NAMES = {
    "ar": "Arabic",
    "bg": "Bulgarian",
    "bs": "Bosnian",
    "cs": "Czech",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fa": "Persian",
    "fr": "French",
    "hr": "Croatian",
    "hu": "Hungarian",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sq": "Albanian",
    "sr": "Serbian",
    "tr": "Turkish",
    "uk": "Ukrainian",
}

_RULES = (
    "You are a medical translator. Translate from {source} into {target} "
    "literally and completely: leave nothing out, add nothing, do not "
    "summarize and do not correct the content. Keep numbers, doses and units "
    "exactly as dictated. Use the medical terms and drug spellings that are "
    "common in {target}."
)
BLOCK_PROMPT = _RULES + (
    " You receive numbered sentences of one dictation. Answer only with a "
    "JSON array of strings: the translated sentences in the same order, "
    "exactly {count} entries, without the numbers."
)
SENTENCE_PROMPT = _RULES + " Output only the translation of the sentence."
# Added when names were masked by the PII sanitizer before translating.
PRESERVE_TOKENS = (
    " Placeholders in square brackets such as [PERSON_1] or [LOCATION_2] stand "
    "for masked names: copy them exactly as they are, do not translate, change "
    "or remove them."
)

_JSON_ARRAY = re.compile(r"\[.*\]", re.S)


def language_name(code: str) -> str:
    """English name of an ISO 639-1 code for the prompt (the code if unknown)."""
    return LANGUAGE_NAMES.get(code.lower(), code)


@dataclass
class Segment:
    """One sentence pair with the numbers that differ between the two."""

    source: str
    target: str
    paragraph: int
    missing_numbers: list[str] = field(default_factory=list)
    extra_numbers: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        """True if the numbers of source and translation differ."""
        return bool(self.missing_numbers or self.extra_numbers)

    def to_dict(self) -> dict:
        """Plain dict for JSON storage (``Record.translation_segments``)."""
        return asdict(self)


@dataclass
class TranslationResult:
    """The joined translation, its sentence pairs and the target language."""

    text: str
    segments: list[Segment]
    language: str


def check_segment(source: str, target: str, paragraph: int) -> Segment:
    """Pair ``source`` and ``target`` and flag differing numbers."""
    result = compare(source, target, check_negations=False)
    return Segment(
        source=source,
        target=target,
        paragraph=paragraph,
        missing_numbers=result.missing_numbers,
        extra_numbers=result.extra_numbers,
    )


def _parse_block(answer: str, count: int) -> list[str] | None:
    """Return the translated sentences, or None if the answer is unusable."""
    match = _JSON_ARRAY.search(answer)
    if not match:
        return None
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(items, list)
        or len(items) != count
        or not all(isinstance(item, str) for item in items)
    ):
        return None
    return [item.strip() for item in items]


def _translate_block(
    sentences: list[str],
    source: str,
    target: str,
    complete: Complete,
    suffix: str = "",
) -> list[str]:
    names = {"source": language_name(source), "target": language_name(target)}
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, start=1))
    answer = complete(
        BLOCK_PROMPT.format(count=len(sentences), **names) + suffix, numbered
    )
    parsed = _parse_block(answer, len(sentences))
    if parsed is not None:
        return parsed
    # Fallback: one call per sentence keeps the pairing intact.
    prompt = SENTENCE_PROMPT.format(**names) + suffix
    return [complete(prompt, sentence).strip() for sentence in sentences]


def translate(
    text: str,
    source: str,
    target: str,
    complete: Complete,
    preserve_tokens: bool = False,
) -> TranslationResult:
    """Translate ``text`` from ``source`` into ``target``.

    Args:
        text: The transcript in the dictation language.
        source: ISO 639-1 code of the dictation language.
        target: ISO 639-1 code of the instance language.
        complete: Calls the LLM with a system prompt and a user message.
        preserve_tokens: The text carries sanitizer placeholders that the
            model must copy unchanged.

    Returns:
        The translation, joined per paragraph, and the checked sentence pairs.

    Raises:
        Exception: Whatever ``complete`` raises; a partial translation is
            never returned.
    """
    sentences = split_sentences(text)
    targets: list[str] = []
    for start in range(0, len(sentences), BLOCK_SIZE):
        block = [s.text for s in sentences[start : start + BLOCK_SIZE]]
        suffix = PRESERVE_TOKENS if preserve_tokens else ""
        targets.extend(_translate_block(block, source, target, complete, suffix))
    segments = [
        check_segment(s.text, t, s.paragraph) for s, t in zip(sentences, targets)
    ]
    joined = join_sentences(targets, [s.paragraph for s in sentences])
    return TranslationResult(text=joined, segments=segments, language=target)
