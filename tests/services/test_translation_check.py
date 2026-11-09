"""Tests for the deterministic translation consistency check."""

from backend.components.services.translation.check import (
    compare,
    count_negations,
    extract_numbers,
)

REFERENCE = (
    "Ramipril 5 Milligramm morgens und Bisoprolol 2,5 Milligramm. "
    "Allergien sind nicht bekannt. Kein Fieber."
)


def test_numbers_normalise_decimal_comma():
    assert extract_numbers("2,5 mg und 2.5 mg, 1000 mg") == {"2.5": 2, "1000": 1}


def test_numbers_ignore_digits_inside_words():
    assert extract_numbers("CHA2DS2-VASc-Score 4, Typ 2") == {"4": 1, "2": 1}


def test_faithful_translation_passes():
    candidate = (
        "Ramipril 5 Milligramm am Morgen, Bisoprolol 2.5 Milligramm. "
        "Allergien sind nicht bekannt. Kein Fieber."
    )
    result = compare(REFERENCE, candidate, terms=["Ramipril", "Bisoprolol"])
    assert result.ok


def test_changed_dose_is_flagged():
    candidate = (
        "Ramipril 50 Milligramm, Bisoprolol 2,5 Milligramm. Nicht bekannt. Kein Fieber."
    )
    result = compare(REFERENCE, candidate)
    assert result.missing_numbers == ["5"]
    assert result.extra_numbers == ["50"]
    assert not result.ok


def test_lost_negation_is_flagged():
    candidate = (
        "Ramipril 5 Milligramm, Bisoprolol 2,5 Milligramm. Allergien bekannt. Fieber."
    )
    result = compare(REFERENCE, candidate)
    assert result.negations_lost == 2
    assert not result.ok


def test_missing_term_is_flagged_but_spelling_variant_is_not():
    result = compare(
        "Spironolacton reduziert.",
        "Die Dosis von Spironolakton wurde reduziert.",
        terms=["Spironolacton", "Kalium"],
    )
    assert result.missing_terms == ["Kalium"]


def test_negations_can_be_skipped_for_cross_language_checks():
    result = compare(
        "У пациента нет температуры.",
        "Der Patient hat kein Fieber.",
        check_negations=False,
    )
    assert result.ok


def test_counts_prohibitions_as_negation():
    assert count_negations("NSAR sind zu vermeiden, ohne Ausnahme.") == 2


def test_german_thousands_separator_equals_plain_number():
    assert extract_numbers("Metformin 1.000 Milligramm, Hb 13,4") == {
        "1000": 1,
        "13.4": 1,
    }


def test_denial_verbs_and_weder_noch_count_as_negations():
    assert count_negations("Er bestreitet Brustschmerzen.") == 1
    assert count_negations("Weder Fieber noch Atemnot.") == 2
    assert count_negations("Kein Fieber und keine Atemnot.") == 2


def test_term_accepts_listed_synonyms():
    result = compare(
        "Pneumonie.", "Lungenentzündung rechts.", terms=["Pneumonie|Lungenentzündung"]
    )
    assert result.ok
