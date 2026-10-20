"""Tests for backend.components.services.term_correction_service."""

from backend.components.services.term_correction_service import (
    correct_terms,
    koelner_phonetik,
)


def test_koelner_phonetik_classic_example():
    # Textbook Kölner Phonetik example: "Meier"/"Maier"/"Mayer" all encode
    # to the same code despite different spellings.
    assert koelner_phonetik("Meier") == koelner_phonetik("Maier") == "67"
    assert koelner_phonetik("Mayer") == "67"


def test_koelner_phonetik_ignores_non_letters():
    assert koelner_phonetik("A-B 1") == koelner_phonetik("AB")


def test_koelner_phonetik_empty_string():
    assert koelner_phonetik("") == ""


def test_correct_terms_replaces_close_match_above_threshold():
    text = "Die Patientin nimmt Sertalin seit drei Wochen."

    corrected, replacements = correct_terms(text, ["Sertralin"], threshold=70.0)

    assert "Sertralin" in corrected
    assert "Sertalin" not in corrected
    assert len(replacements) == 1
    assert replacements[0]["original"] == "Sertalin"
    assert replacements[0]["replacement"] == "Sertralin"
    assert replacements[0]["score"] >= 70.0


def test_correct_terms_leaves_text_unchanged_below_threshold():
    text = "Der Patient hat starke Kopfschmerzen."

    corrected, replacements = correct_terms(text, ["Sertralin"], threshold=95.0)

    assert corrected == text
    assert replacements == []


def test_correct_terms_no_glossary_is_noop():
    text = "Ein beliebiger Text."

    corrected, replacements = correct_terms(text, [], threshold=85.0)

    assert corrected == text
    assert replacements == []


def test_correct_terms_does_not_replace_exact_match():
    text = "Sertralin wurde verordnet."

    corrected, replacements = correct_terms(text, ["Sertralin"], threshold=70.0)

    assert corrected == text
    assert replacements == []


def test_correct_terms_preserves_surrounding_punctuation():
    text = "Diagnose: Vorhofflimern, Kontrolle in 4 Wochen."

    corrected, replacements = correct_terms(text, ["Vorhofflimmern"], threshold=70.0)

    assert corrected == "Diagnose: Vorhofflimmern, Kontrolle in 4 Wochen."
    assert replacements[0]["replacement"] == "Vorhofflimmern"


def test_correct_terms_short_terms_are_ignored():
    # Terms under 3 characters are too ambiguous to correct to.
    corrected, replacements = correct_terms("Er nahm ab.", ["ab", "AB"], 50.0)

    assert corrected == "Er nahm ab."
    assert replacements == []


def test_correct_terms_handles_a_catalog_sized_glossary_quickly():
    """A whole ICD-sized dictionary must not take minutes per transcript."""
    import random
    import string
    import time

    rng = random.Random(42)
    glossary = [
        "".join(rng.choices(string.ascii_lowercase, k=rng.randint(6, 14)))
        for _ in range(20_000)
    ] + ["Sertralin"]
    text = " ".join(["Die Patientin nimmt Sertalin seit drei Wochen."] * 120)

    start = time.perf_counter()
    corrected, replacements = correct_terms(text, glossary, threshold=90.0)
    elapsed = time.perf_counter() - start

    assert "Sertralin" in corrected
    assert elapsed < 10, f"correct_terms took {elapsed:.1f}s"


# Regression: matching on the phonetic code alone rewrote error-free text
# ("Notaufnahme" -> "Metformin"), because Kölner Phonetik drops vowels and
# unrelated words end up with near-identical codes.
_GLOSSARY = [
    "Metformin",
    "Appendektomie",
    "Thrombozyten",
    "Dyspnoe",
    "Pneumonie",
    "Myokardinfarkt",
    "Bisoprolol",
    "Pantoprazol",
    "Levothyroxin",
    "Hämoglobin",
]


def test_correct_terms_leaves_error_free_text_alone():
    text = (
        "Der Patient stellte sich in der Notaufnahme vor. Daher besteht eine "
        "Indikation zur Antikoagulation, das ein Thema der Mobilisation war. "
        "Wir begannen eine Therapie bei Verdacht auf einen Myokardinfarkt."
    )

    corrected, replacements = correct_terms(text, _GLOSSARY, threshold=85.0)

    assert replacements == []
    assert corrected == text


def test_correct_terms_keeps_inflected_correct_terms():
    text = "Die Diagnose eines akuten Myokardinfarkts wurde gestellt."

    corrected, replacements = correct_terms(text, _GLOSSARY, threshold=85.0)

    assert replacements == []
    assert corrected == text


def test_correct_terms_fixes_real_asr_misspellings():
    cases = {
        "Levotyroxen": "Levothyroxin",
        "Pantobrazol": "Pantoprazol",
        "Bisopronol": "Bisoprolol",
        "Hämogloben": "Hämoglobin",
        "Mitformin": "Metformin",
    }
    for wrong, right in cases.items():
        corrected, _ = correct_terms(
            f"Die Patientin erhält {wrong} täglich.", _GLOSSARY, threshold=85.0
        )
        assert corrected == f"Die Patientin erhält {right} täglich.", wrong


def test_correct_terms_joins_a_split_term():
    corrected, _ = correct_terms(
        "Sie nimmt mit Formin 1000 mg.", _GLOSSARY, threshold=85.0
    )

    assert corrected == "Sie nimmt Metformin 1000 mg."


def test_correct_terms_never_maps_a_long_phrase_to_one_word():
    # Three words may not collapse into a single-word term.
    corrected, replacements = correct_terms(
        "daher besteht eine Indikation", ["Thrombozyten"], threshold=50.0
    )

    assert replacements == []
