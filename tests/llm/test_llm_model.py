"""Tests for backend.components.llm.llm_model.OllamaModel.

Covers two production gaps found while debugging a stuck "KI arbeitet..."
task: (1) the ChatOpenAI client had no request timeout, so a hung or very
slow local model left the background task stuck at status="processing_llm"
forever; (2) a response consisting only of a <think> reasoning block was
silently stripped down to an empty string and saved as a "finished" summary
with no indication anything went wrong.
"""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import backend.components.models  # noqa: F401  (registers all tables on metadata)
from backend.components.llm import llm_model as llm_model_module
from backend.components.llm.llm_model import OllamaModel
from backend.components.sql import sql_engine


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


def test_constructs_chat_openai_with_a_timeout(monkeypatch, patched_engine):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_model_module, "ChatOpenAI", FakeChatOpenAI)

    OllamaModel()

    assert captured.get("timeout") == llm_model_module.LLM_REQUEST_TIMEOUT_SECONDS
    assert captured["timeout"] is not None


def test_generate_response_returns_stripped_content(patched_engine):
    model = OllamaModel()
    model.client = _fake_client("Klare Antwort ohne Denkblock.")

    result = model.generate_response("irrelevant input")

    assert result == "Klare Antwort ohne Denkblock."


def test_generate_response_raises_when_only_thinking_block(patched_engine):
    model = OllamaModel()
    model.client = _fake_client("<think>endlose Grübelei ohne Ergebnis</think>")

    with pytest.raises(ValueError, match="empty"):
        model.generate_response("irrelevant input")


def test_generate_response_raises_on_whitespace_only_output(patched_engine):
    model = OllamaModel()
    model.client = _fake_client("   \n  ")

    with pytest.raises(ValueError, match="empty"):
        model.generate_response("irrelevant input")
