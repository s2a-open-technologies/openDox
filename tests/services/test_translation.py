"""Sentence-wise translation with a fake LLM: pairing, fallback, number flags."""

import json

import pytest

from backend.components.services.translation import split_sentences, translate
from backend.components.services.translation.check import extract_numbers
from backend.components.services.translation.segmenter import join_sentences
from backend.components.services.translation.translator import language_name

RU = "Пациент принимает 5 мг рамиприла. Аллергии нет.\nДавление 140 на 90."


def _block_llm(answers: dict[str, str] | None = None, calls: list | None = None):
    """Fake LLM: answers a numbered block with a JSON list of "<target>: <src>"."""

    def complete(system: str, message: str) -> str:
        if calls is not None:
            calls.append((system, message))
        if answers and message in answers:
            return answers[message]
        if not message.startswith("1. "):
            return f"DE {message}"  # single-sentence fallback
        lines = [line.split(". ", 1)[1] for line in message.splitlines()]
        return json.dumps([f"DE {line}" for line in lines], ensure_ascii=False)

    return complete


def test_split_keeps_numbers_and_paragraphs():
    sentences = split_sentences("Dosis 2.5 mg. Gut!\nNächster Absatz؟ Ende")

    assert [s.text for s in sentences] == [
        "Dosis 2.5 mg.",
        "Gut!",
        "Nächster Absatz؟",
        "Ende",
    ]
    assert [s.paragraph for s in sentences] == [0, 0, 1, 1]
    assert join_sentences(["a", "b", "c", "d"], [0, 0, 1, 1]) == "a b\nc d"


def test_translate_pairs_every_sentence_and_names_the_languages():
    calls: list = []
    result = translate(RU, "ru", "de", complete=_block_llm(calls=calls))

    assert [s.source for s in result.segments] == [
        "Пациент принимает 5 мг рамиприла.",
        "Аллергии нет.",
        "Давление 140 на 90.",
    ]
    assert result.segments[0].target == "DE Пациент принимает 5 мг рамиприла."
    assert result.text.count("\n") == 1
    assert result.language == "de"
    system, _ = calls[0]
    assert "from Russian into German" in system
    assert "exactly 3 entries" in system


def test_target_language_is_whatever_the_instance_uses():
    calls: list = []
    translate("Привет.", "ru", "en", complete=_block_llm(calls=calls))

    assert "from Russian into English" in calls[0][0]


def test_unusable_block_answer_falls_back_to_single_sentences():
    calls: list = []

    def complete(system: str, message: str) -> str:
        calls.append(message)
        if message.startswith("1. "):
            return "Hier ist die Übersetzung: kein JSON"
        return f"DE {message}"

    result = translate("Один. Два.", "ru", "de", complete=complete)

    assert [s.target for s in result.segments] == ["DE Один.", "DE Два."]
    assert calls == ["1. Один.\n2. Два.", "Один.", "Два."]


def test_wrong_sentence_count_falls_back_too():
    answers = {"1. Один.\n2. Два.": json.dumps(["nur einer"])}

    result = translate("Один. Два.", "ru", "de", complete=_block_llm(answers))

    assert [s.target for s in result.segments] == ["DE Один.", "DE Два."]


def test_differing_numbers_are_flagged_per_sentence():
    answers = {
        "1. Принимает 5 мг.\n2. Давление 140.": json.dumps(
            ["Nimmt 50 mg.", "Blutdruck 140."]
        )
    }

    result = translate(
        "Принимает 5 мг. Давление 140.", "ru", "de", complete=_block_llm(answers)
    )

    first, second = result.segments
    assert first.flagged
    assert first.missing_numbers == ["5"] and first.extra_numbers == ["50"]
    assert not second.flagged


def test_arabic_indic_digits_count_as_the_same_numbers():
    assert extract_numbers("الجرعة ٥ ملغ و ٢٫٥") == extract_numbers("Dosis 5 mg, 2,5")
    assert extract_numbers("١٢٬٥٠٠") == extract_numbers("12.500")


def test_llm_errors_are_not_swallowed():
    def broken(system: str, message: str) -> str:
        raise RuntimeError("LLM down")

    with pytest.raises(RuntimeError):
        translate("Один.", "ru", "de", complete=broken)


def test_unknown_language_code_is_passed_through():
    assert language_name("xx") == "xx"
    assert language_name("AR") == "Arabic"
