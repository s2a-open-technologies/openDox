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
from backend.components.services.settings_service import get_llm_settings

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "Du korrigierst deutschen Whisper-Transkriptions-Output für medizinische Diktiersoftware.\n"
    "Aufgabe: Korrigiere NUR den neuen Chunk.\n"
    "Erlaubte Korrekturen: falsche Satzzeichen bei Atempausen, abgehackte Wörter an "
    "Chunk-Grenzen, einzelne offensichtliche Transkriptions-Artefakte.\n"
    "VERBOTEN: Inhalt ändern, Wörter hinzufügen oder weglassen, umformulieren.\n"
    "Gib NUR den korrigierten Text zurück — kein Kommentar, keine Erklärung."
)


def correct_chunk(raw_text: str, context: str) -> str:
    """Post-process a raw Whisper chunk with a fast LLM correction pass.

    Uses the configured LLM endpoint (same as summarisation). Falls back to
    raw_text on any error or timeout so near-live never blocks.
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    try:
        settings = get_llm_settings()
        endpoint = (settings.llm_api_endpoint or "http://localhost:11434/v1").rstrip("/")
        model = settings.correction_model or settings.llm_model or "medgemma-4b-it:Q4_K_M"
        api_key = settings.llm_api_key or "loc-123"

        system = _SYSTEM_PROMPT
        if context:
            system += f'\n\nKontext (bereits transkribiert): "{context}"'

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": raw_text},
            ],
            "temperature": 0.0,
            "max_tokens": 200,
        }

        response = requests.post(
            f"{endpoint}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=4,
        )

        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            corrected = _strip_thinking(content).strip()
            if corrected:
                logger.debug("[CHUNK-FIX] %r → %r", raw_text[:60], corrected[:60])
                return corrected

    except Exception as e:
        logger.debug("[CHUNK-FIX] fallback (%s)", e)

    return raw_text
