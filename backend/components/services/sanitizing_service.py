
# Standard library
import re
import difflib
import requests


def _extract_mapping(original: str, sanitized: str) -> dict[str, str]:
    
    matcher = difflib.SequenceMatcher(None, original, sanitized)
    mapping: dict = {}
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            orig_chunk = original[i1:i2]  # z.B. "Herr Müller" 
            san_chunk = sanitized[j1:j2]  # z.B. "[PERSON]"
            for token in re.findall(r'\[[A-Z_]+_?\d*\]', san_chunk):
                mapping[token] =orig_chunk
    
    return mapping

def sanitize(text: str, endpoint: str, api_key: str | None, department: str) -> \
    tuple[str, dict[str, str]]:
    """
    Calls EntityGuard, then difss original vs. sanitized to build the entity mapping
    Returns (sanitized_text, entity_mapping). Raises on failure (fail-closed)
    """    
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    base = endpoint.rstrip("/")
    response = requests.post(
        f"{base}/api/v1/entityguard/sanitize",
        json={"text": text, "department": department},
        headers=headers,
        timeout=10
    )
    response.raise_for_status()
    sanitized = response.json()["sanitized_text"]
    mapping = _extract_mapping(text, sanitized)
    return sanitized, mapping

def reinject(text: str, entity_mapping: dict[str, str]) -> str:
    """Deterministic String replace: [PERSON] -> 'Dr. Müller' etc."""
    for placeholder, original in entity_mapping.items():
        text = text.replace(placeholder, original)
    return text

_PRESERVE_TOKENS_INSTRUCTION = (
    "\n\nWICHTIG: Alle Platzhalter in eckigen Klammern wie [PERSON], [LOCATION] etc. "
    "müssen exakt so im Text erhalten bleiben. Nicht umformulieren, nicht entfernen."
)
