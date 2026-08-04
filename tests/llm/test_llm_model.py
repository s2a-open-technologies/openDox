"""Tests for backend.components.llm.llm_model.SummarizeModel.

Covers three production gaps found while debugging real usage issues:
(1) the ChatOpenAI client had no request timeout, so a hung or very slow
local model left the background task stuck at status="processing_llm"
forever; (2) a response consisting only of a <think> reasoning block was
silently stripped down to an empty string and saved as a "finished" summary
with no indication anything went wrong; (3) a bare provider domain (e.g.
"https://ollama.com", missing "/v1") was accepted verbatim as base_url —
the openai SDK appends "/chat/completions" directly to whatever it's given
with no normalization, so real chat calls silently landed on the
provider's website (HTML) instead of its API, while the separate
/v1/models connectivity test (which *did* reconstruct the URL correctly)
reported success — masking the bug until someone actually tried to
generate a summary.
"""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import backend.components.models  # noqa: F401  (registers all tables on metadata)
from backend.components.llm import llm_model as llm_model_module
from backend.components.llm.llm_model import SummarizeModel, normalize_openai_base_url
from backend.components.sql import sql_engine


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://ollama.com", "https://ollama.com/v1"),
        ("https://ollama.com/", "https://ollama.com/v1"),
        ("https://ollama.com/v1", "https://ollama.com/v1"),
        ("https://ollama.com/v1/", "https://ollama.com/v1"),
        ("http://localhost:11434/v1", "http://localhost:11434/v1"),
    ],
)
def test_normalize_openai_base_url(raw, expected):
    assert normalize_openai_base_url(raw) == expected


@pytest.fixture
def patched_engine(monkeypatch):
    """Point sql_engine.engine at an isolated in-memory SQLite DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(sql_engine, "engine", engine)
    return engine


def _fake_client(content: str) -> RunnableLambda:
    """A minimal Runnable standing in for ChatOpenAI, returning fixed content."""
    return RunnableLambda(lambda _: AIMessage(content=content))


def _capturing_client(content: str) -> tuple[RunnableLambda, dict]:
    """A fake Runnable that also records the rendered messages it received."""
    captured: dict = {}

    def _invoke(prompt_value):
        captured["messages"] = prompt_value.to_messages()
        return AIMessage(content=content)

    return RunnableLambda(_invoke), captured


def test_constructs_chat_openai_with_a_timeout(monkeypatch, patched_engine):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_model_module, "ChatOpenAI", FakeChatOpenAI)

    SummarizeModel()

    assert captured.get("timeout") == llm_model_module.LLM_REQUEST_TIMEOUT_SECONDS
    assert captured["timeout"] is not None


def test_constructs_chat_openai_with_a_custom_timeout_override(
    monkeypatch, patched_engine
):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_model_module, "ChatOpenAI", FakeChatOpenAI)

    SummarizeModel(timeout=15)

    assert captured["timeout"] == 15


def test_normalizes_a_bare_base_url_before_passing_to_chat_openai(
    monkeypatch, patched_engine
):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_model_module, "ChatOpenAI", FakeChatOpenAI)

    SummarizeModel(base_url="https://ollama.com")

    assert captured["base_url"] == "https://ollama.com/v1"


def test_generate_response_returns_stripped_content(patched_engine):
    model = SummarizeModel()
    model.client = _fake_client("Klare Antwort ohne Denkblock.")

    result = model.generate_response("irrelevant input")

    assert result == "Klare Antwort ohne Denkblock."


def test_generate_response_raises_when_only_thinking_block(patched_engine):
    model = SummarizeModel()
    model.client = _fake_client("<think>endlose Grübelei ohne Ergebnis</think>")

    with pytest.raises(ValueError, match="empty"):
        model.generate_response("irrelevant input")


def test_generate_response_raises_on_whitespace_only_output(patched_engine):
    model = SummarizeModel()
    model.client = _fake_client("   \n  ")

    with pytest.raises(ValueError, match="empty"):
        model.generate_response("irrelevant input")


def test_placeholder_rule_reaches_default_prompt(patched_engine):
    """The default fallback prompt must carry the anti-hallucination rule."""
    model = SummarizeModel()
    model.client, captured = _capturing_client("Ergebnis")

    model.generate_response("Text")

    system_content = captured["messages"][0].content
    assert "Platzhalter" in system_content
    assert "[PERSON]" in system_content


def test_placeholder_rule_reaches_custom_category_prompt_without_it(patched_engine):
    """A freshly created category prompt has no idea about the rule.

    It must still be enforced, since the admin who wrote it has no way of
    knowing the local model tends to invent bracket placeholders.
    """
    model = SummarizeModel()
    model.client, captured = _capturing_client("Ergebnis")
    custom_prompt = "Du bist ein hilfreicher Assistent für Notizen."

    model.generate_response("Text", custom_system_prompt=custom_prompt)

    system_content = captured["messages"][0].content
    assert custom_prompt in system_content
    assert "Platzhalter" in system_content
    assert "[PERSON]" in system_content


def test_get_system_prompt_no_longer_hardcodes_the_placeholder_rule(patched_engine):
    """The rule lives solely in generate_response() now.

    Duplicating it in prompt text would let the two copies drift out of
    sync over time.
    """
    model = SummarizeModel()

    assert "Erfinde niemals neue Platzhalter" not in model.get_system_prompt()
