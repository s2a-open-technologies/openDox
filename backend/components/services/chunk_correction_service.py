"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

import requests

from backend.components.llm.llm_model import _strip_thinking
from backend.components.modules.logger import get_logger
from backend.components.services.sanitizing_service import (
    _PRESERVE_TOKENS_INSTRUCTION,
    reinject,
    sanitize,
)
from backend.components.services.settings_service import get_llm_settings

logger = get_logger(__name__)

_LIVE_SANITIZER_TIMEOUT = 3


def _sanitize_live(text: str) -> tuple[str, dict[str, str]]:
    """Sanitize text for live paths; returns (original, {}) on any failure.

    Live correction must never block — if EntityGuard is slow or down we
    fall back to sending the raw text through (same as having PII disabled).
    """
    settings = get_llm_settings()
    if (
        not settings
        or not settings.sanitizer_enabled
        or not settings.sanitizer_endpoint
    ):
        return text, {}
    try:
        sanitized, mapping = sanitize(
            text,
            endpoint=settings.sanitizer_endpoint,
            api_key=settings.sanitizer_api_key,
            timeout=_LIVE_SANITIZER_TIMEOUT,
        )
        return sanitized, mapping
    except Exception as e:
        logger.warning("[PII-LIVE] Sanitizer failed, sending raw text: %s", e)
        return text, {}


_SYSTEM_PROMPT = (
    "Du bereinigst deutschen Whisper-Transkriptionstext für medizinische Diktiersoftware.\n\n"
    "Entferne diese bekannten Whisper-Artefakte aus dem Text:\n"
    '- "Vielen Dank", "Danke schön", "Danke", "Bitte"\n'
    '- "Tschüss", "Auf Wiedersehen", "Bis zum nächsten Mal"\n'
    '- "Das ist ein Video", "Das ist ein Test"\n'
    '- "Untertitel von", "Abonnieren", ♪, [Musik], [Applaus]\n\n'
    "Erlaubte weitere Korrekturen: Satzzeichen, abgehackte Wörter an Chunk-Grenzen.\n\n"
    "VERBOTEN: Erklärungen schreiben, Kommentare, neue Wörter erfinden, Inhalt ändern.\n"
    "Gib NUR den bereinigten Text aus. Wenn nichts übrig bleibt, gib nichts aus."
)

# LLM meta-commentary patterns — small models sometimes explain instead of outputting empty.
_META_PATTERNS = [
    "kein medizinischer inhalt",
    "kein inhalt",
    "leises geräusch",
    "keine sprache",
    "stille erkannt",
    "halluzination",
    "keine transkription",
    "es gibt keinen",
    "der text enthält",
    "dies ist kein",
    "ich kann",
    "unfortunately",
    "there is no",
]


def _is_meta_commentary(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _META_PATTERNS)


def _call_llm(
    system: str, user: str, max_tokens: int = 200, timeout: int = 4
) -> str | None:
    """Call the configured LLM and return the response content, or None on failure."""
    try:
        settings = get_llm_settings()
        endpoint = (settings.llm_api_endpoint or "http://localhost:11434/v1").rstrip(
            "/"
        )
        model = (
            settings.correction_model or settings.llm_model or "medgemma-4b-it:Q4_K_M"
        )
        api_key = settings.llm_api_key or "loc-123"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }

        response = requests.post(
            f"{endpoint}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            return _strip_thinking(content).strip()

    except Exception as e:
        logger.debug("[CHUNK-FIX] LLM call failed: %s", e)

    return None


_SMOOTH_PROMPT = (
    "Du glättest die Interpunktion eines deutschen Medizindiktats.\n"
    "Das Diktat wurde in kurzen Chunks transkribiert; an den Grenzen wurden "
    "mechanisch Punkte gesetzt, die mitten in Sätze fallen.\n\n"
    "Korrigiere diese falschen Satzenden: Verbinde unterbrochene Sätze, "
    "passe Groß-/Kleinschreibung entsprechend an.\n"
    "Echte Satzenden und Pausen bleiben erhalten.\n\n"
    "VERBOTEN: Wörter hinzufügen, entfernen, umformulieren oder Inhalt ändern.\n"
    "Gib NUR den korrigierten Text aus."
)


def smooth_transcript(text: str) -> str:
    """Smooth chunk-boundary punctuation in an accumulated Parakeet transcript.

    Sanitizes PII before the LLM call and reinjects real names afterwards.
    Returns cleaned text on success, original text on LLM failure.
    """
    if not text or not text.strip():
        return text

    text_for_llm, entity_mapping = _sanitize_live(text)

    system = _SMOOTH_PROMPT
    if entity_mapping:
        system += _PRESERVE_TOKENS_INSTRUCTION

    max_tokens = max(200, len(text_for_llm.split()) * 2)
    result = _call_llm(system, text_for_llm, max_tokens=max_tokens, timeout=20)

    if result and not _is_meta_commentary(result):
        if entity_mapping:
            result = reinject(result, entity_mapping)
        logger.debug("[SMOOTH] %d → %d chars", len(text), len(result))
        return result
    return text


def correct_chunk(raw_text: str, context: str) -> str:
    """Post-process a single raw Whisper chunk with a fast LLM correction pass.

    Sanitizes PII before the LLM call and reinjects real names afterwards.
    Falls back to raw_text on any error or timeout so near-live never blocks.
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    text_for_llm, entity_mapping = _sanitize_live(raw_text)

    system = _SYSTEM_PROMPT
    if entity_mapping:
        system += _PRESERVE_TOKENS_INSTRUCTION

    result = _call_llm(system, text_for_llm)
    if result is not None:
        if entity_mapping:
            result = reinject(result, entity_mapping)
        if _is_meta_commentary(result):
            logger.debug("[CHUNK-FIX] LLM meta-commentary filtered: %r", result[:80])
            return ""
        if result:
            logger.debug("[CHUNK-FIX] %r → %r", raw_text[:60], result[:60])
        else:
            logger.debug("[CHUNK-FIX] hallucination removed: %r", raw_text[:60])
        return result

    return raw_text
