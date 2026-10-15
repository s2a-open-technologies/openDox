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

# Standard library
import difflib
import re

# Third party
import requests

# Custom imports
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)


def _extract_mapping(original: str, sanitized: str) -> dict[str, str]:
    """Best-effort reconstruction of token -> real value via word-level diff.

    Only used as a fallback when the sanitizer backend doesn't return a
    `mapping` dict directly. Skips (and logs) any replace block containing
    zero or multiple tokens rather than risk a wrong attribution between
    adjacent redactions.

    Args:
        original: Text before sanitization (real values).
        sanitized: Text after sanitization (placeholder tokens).

    Returns:
        Mapping of placeholder token to the real value it replaced.
    """
    orig_words = original.split()
    san_words = sanitized.split()
    matcher = difflib.SequenceMatcher(None, orig_words, san_words)
    mapping: dict[str, str] = {}

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        orig_chunk = " ".join(orig_words[i1:i2])
        san_chunk = " ".join(san_words[j1:j2])
        matches = list(re.finditer(r"\[[^\[\]]+\]", san_chunk))
        if len(matches) == 1:
            # Strip any punctuation glued to the token (e.g. a trailing "."
            # at sentence end) from the mapped value, since it belongs to
            # the surrounding sentence, not the redacted entity.
            match = matches[0]
            prefix, suffix = san_chunk[: match.start()], san_chunk[match.end() :]
            value = orig_chunk
            if prefix and value.startswith(prefix):
                value = value[len(prefix) :]
            if suffix and value.endswith(suffix):
                value = value[: len(value) - len(suffix)]
            mapping[match.group(0)] = value
        elif len(matches) > 1:
            tokens = [m.group(0) for m in matches]
            logger.warning(
                f"Skipping ambiguous PII block with {len(tokens)} adjacent "
                f"tokens (no separating text to anchor on): {tokens}"
            )

    return mapping


def sanitize(
    text: str, endpoint: str, api_key: str | None, timeout: int = 10
) -> tuple[str, dict[str, str]]:
    """Call the sanitizer endpoint and build the entity mapping.

    Prefers a `mapping` dict ({token: original}) returned directly by the
    sanitizer backend; falls back to diffing original vs. sanitized text
    when the backend only returns `sanitized_text`.

    Args:
        text: Original text to sanitize.
        endpoint: Full URL of the sanitizer's sanitize endpoint.
        api_key: Optional bearer token.
        timeout: Request timeout in seconds. Defaults to 10.

    Returns:
        Tuple of (sanitized_text, entity_mapping).

    Raises:
        requests.HTTPError: If the sanitizer endpoint call fails
            (fail-closed — no unsanitized LLM call).
    """
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.post(
        endpoint.rstrip("/"),
        json={"text": text},
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    sanitized = body["sanitized_text"]

    mapping = body.get("mapping")
    if not mapping:
        mapping = _extract_mapping(text, sanitized)

    return sanitized, mapping


def reinject(text: str, entity_mapping: dict[str, str]) -> str:
    """Deterministic string replace: [PERSON] -> 'Dr. Müller' etc.

    Args:
        text: Text still containing placeholder tokens.
        entity_mapping: Mapping of placeholder token to real value.

    Returns:
        Text with all placeholder tokens replaced by their real values.
    """
    for placeholder, original in entity_mapping.items():
        text = text.replace(placeholder, original)
    return text


_PRESERVE_TOKENS_INSTRUCTION = (
    "\n\nWICHTIG: Alle Platzhalter in eckigen Klammern wie [PERSON], [LOCATION] etc. "
    "müssen exakt so im Text erhalten bleiben. Nicht umformulieren, nicht entfernen."
)
