"""Tests for backend.components.services.term_correction_service."""

from backend.components.services.term_correction_service import (
    correct_terms,
    koelner_phonetik,
    parse_glossary,
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


def test_parse_glossary_splits_and_dedupes():
    prompt = "Sertralin, Metformin;\nSertralin\nIbuprofen, ab"

    assert parse_glossary(prompt) == ["Sertralin", "Metformin", "Ibuprofen"]


def test_parse_glossary_empty_input():
    assert parse_glossary("") == []
    assert parse_glossary(None) == []


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
