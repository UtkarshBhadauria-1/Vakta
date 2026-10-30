import numpy as np
from fastapi.testclient import TestClient

from app import main
from app.documents import DocumentChunk
from app.rag import build_followup_context
from app.retriever import SearchResult
from app.settings import Settings


class FakeRetriever:
    def __init__(self, score: float = 0.91):
        self.score = score
        self.chunks = [
            DocumentChunk(
                chunk_id="faq-tuition-chunk-1",
                document_id="faq-tuition",
                title="Tuition bills and payment plans",
                text="Tuition statements are available in the student portal under Billing.",
                source="sample_faq.json",
                metadata={"category": "Finances"},
            )
        ]

    def search(self, query: str, top_k: int = 4):
        return [SearchResult(chunk=self.chunks[0], score=self.score)]


def make_settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_chat_returns_generated_answer_and_source(monkeypatch) -> None:
    monkeypatch.setattr(main, "generate_answer", lambda *args: "Check the Billing area of your student portal.")
    client = TestClient(main.create_app(FakeRetriever(), make_settings(groq_api_key="test-key")))
    response = client.post("/api/chat", json={"question": "Where is my tuition bill?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("Check the Billing")
    assert payload["used_context"] is True
    assert payload["sources"][0]["title"] == "Tuition bills and payment plans"
    assert payload["sources"][0]["source"] == "sample_faq.json"


def test_relevant_context_without_groq_key_returns_clear_service_error() -> None:
    client = TestClient(main.create_app(FakeRetriever(), make_settings(groq_api_key=None)))
    response = client.post("/api/chat", json={"question": "Where is my tuition bill?"})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_no_relevant_evidence_does_not_call_groq(monkeypatch) -> None:
    def must_not_run(*args):
        raise AssertionError("Groq must not be called without evidence")

    monkeypatch.setattr(main, "generate_answer", must_not_run)
    config = make_settings(groq_api_key=None, min_relevance_score=0.5)
    client = TestClient(main.create_app(FakeRetriever(score=0.1), config))
    response = client.post("/api/chat", json={"question": "What is the answer?"})
    assert response.status_code == 200
    assert response.json()["used_context"] is False
    assert response.json()["sources"] == []
    assert "couldn't find" in response.json()["answer"]


def test_request_validation_rejects_blank_or_oversized_questions() -> None:
    client = TestClient(main.create_app(FakeRetriever(), make_settings(groq_api_key="test-key")))
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
    assert client.post("/api/chat", json={"question": "x" * 1201}).status_code == 422


def test_health_does_not_expose_provider_credentials() -> None:
    client = TestClient(main.create_app(FakeRetriever(), make_settings(groq_api_key="never-return-this")))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["groq_configured"] is True
    assert "never-return-this" not in response.text


def test_followup_context_uses_student_questions_only() -> None:
    from app.schemas import ConversationTurn

    turns = [
        ConversationTurn(role="user", content="How do I apply for scholarships?"),
        ConversationTurn(role="assistant", content="Your award deadline is October 20."),
        ConversationTurn(role="user", content="When are those due?"),
    ]
    context = build_followup_context(turns)
    assert "How do I apply for scholarships?" in context
    assert "When are those due?" in context
    assert "October 20" not in context


def test_groq_generation_wires_model_key_evidence_and_followup(monkeypatch) -> None:
    from types import SimpleNamespace
    from typing import Any

    from app.rag import generate_answer

    captured: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Check the current scholarship listing."))]
            )

    class FakeGroq:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("groq.Groq", FakeGroq)
    chunk = DocumentChunk(
        chunk_id="faq-scholarships-chunk-1",
        document_id="faq-scholarships",
        title="Scholarships",
        text="Application deadlines differ by award; check the current scholarship portal.",
        source="sample_faq.json",
    )
    answer = generate_answer(
        "When are those due?",
        [SearchResult(chunk=chunk, score=0.88)],
        "test-model-name",
        "test-only-key",
        "How do I apply for scholarships?",
    )

    assert answer == "Check the current scholarship listing."
    assert captured["client"]["api_key"] == "test-only-key"
    request = captured["request"]
    assert request["model"] == "test-model-name"
    prompt = request["messages"][1]["content"]
    assert "Prior student questions" in prompt
    assert "How do I apply for scholarships?" in prompt
    assert "current scholarship portal" in prompt
