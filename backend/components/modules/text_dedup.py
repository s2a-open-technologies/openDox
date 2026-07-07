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


def merge_overlapping_text(existing: str, new_text: str) -> str:
    """Append new_text to existing, trimming any leading words in new_text

    that duplicate the tail of existing (word-level, case-insensitive).

    Used to reconcile a re-transcribed left-context region: new_text is a
    model's output for [left-context audio + new chunk], and its leading
    words are expected to re-say some of what's already in existing.

    Args:
        existing: Text already emitted (e.g. the live transcript so far).
        new_text: The model's latest output, which may re-say the tail of
            existing before its genuinely new content.

    Returns:
        existing with only the non-overlapping suffix of new_text appended.
        When no overlap is found, behaves exactly like
        `(existing + " " + new_text).strip()`.
    """
    if not existing:
        return new_text.strip()
    if not new_text:
        return existing

    existing_words = existing.split()
    new_words = new_text.split()
    max_k = min(len(existing_words), len(new_words))

    overlap = 0
    for k in range(max_k, 0, -1):
        existing_tail = [w.lower() for w in existing_words[-k:]]
        new_head = [w.lower() for w in new_words[:k]]
        if existing_tail == new_head:
            overlap = k
            break

    if overlap == 0:
        return (existing + " " + new_text).strip()

    remaining = " ".join(new_words[overlap:])
    if not remaining:
        return existing
    return (existing + " " + remaining).strip()


if __name__ == "__main__":
    cases = [
        # (existing, new_text, expected)
        ("", "hello world", "hello world"),
        ("hello world", "", "hello world"),
        ("Der Patient hat", "hat Kopfschmerzen", "Der Patient hat Kopfschmerzen"),
        ("Der Patient hat Kopfschmerzen", "Kopfschmerzen seit gestern",
         "Der Patient hat Kopfschmerzen seit gestern"),
        ("Der Patient", "Fieber und Husten", "Der Patient Fieber und Husten"),
        ("Der Patient HAT", "hat Kopfschmerzen", "Der Patient HAT Kopfschmerzen"),
        ("a b c", "a b c", "a b c"),
    ]
    failures = 0
    for existing, new_text, expected in cases:
        result = merge_overlapping_text(existing, new_text)
        status = "OK" if result == expected else "FAIL"
        if status == "FAIL":
            failures += 1
        print(f"[{status}] merge_overlapping_text({existing!r}, {new_text!r}) "
              f"= {result!r} (expected {expected!r})")
    if failures:
        raise SystemExit(f"{failures} of {len(cases)} cases failed")
    print(f"All {len(cases)} cases passed")
