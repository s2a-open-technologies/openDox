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

Sentence splitting for dictations in any language.

Whisper output is mostly one block of text. It is split at sentence ends
(".", "!", "?", the Arabic "؟", "…") followed by whitespace, and at line
breaks, which are kept as paragraph boundaries. Numbers like "2.5" or "1.000"
are never split because there is no whitespace after the dot.
"""

# Standard library
import re
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"(?<=[.!?؟…])\s+")


@dataclass
class Sentence:
    """One sentence and the paragraph it belongs to."""

    text: str
    paragraph: int


def split_sentences(text: str) -> list[Sentence]:
    """Split ``text`` into sentences, remembering paragraph boundaries."""
    sentences: list[Sentence] = []
    paragraph = 0
    for line in text.splitlines():
        parts = [p.strip() for p in _SENTENCE_END.split(line) if p.strip()]
        if not parts:
            continue
        sentences.extend(Sentence(part, paragraph) for part in parts)
        paragraph += 1
    return sentences


def join_sentences(texts: list[str], paragraphs: list[int]) -> str:
    """Join translated sentences, one line per original paragraph."""
    lines: list[list[str]] = []
    last = None
    for text, paragraph in zip(texts, paragraphs):
        if paragraph != last:
            lines.append([])
            last = paragraph
        if text.strip():
            lines[-1].append(text.strip())
    return "\n".join(" ".join(line) for line in lines if line)
