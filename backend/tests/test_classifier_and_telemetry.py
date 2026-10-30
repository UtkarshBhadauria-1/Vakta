from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.classifier import INTENTS, QUERY_TYPES, RuleBasedIntentClassifier
from app.documents import DocumentChunk
from app.retriever import SearchResult
from app.settings import Settings
from app.telemetry import TelemetryRecord, TelemetryStore


class MockRetriever:
    def __init__(self, score: float = 0.90):
        self.score = score
        self.chunks = [
            DocumentChunk(
                chunk_id="test-chunk-1",
                document_id="Q001",
                title="ERP Password Reset",
                text="Visit IT Helpdesk to reset your password.",
                source="faq.json",
                metadata={"category": "grievance"},
            )
        ]

    def search(self, query: str, top_k: int = 4):
        return [SearchResult(chunk=self.chunks[0], score=self.score)]


def test_classifier_detects_all_seven_hcl_intents() -> None:
    classifier = RuleBasedIntentClassifier()

    cases = [
        ("Who is the faculty instructor for the Artificial Intelligence course?", "admissions"),
        ("What does the academic calendar say about semester start dates and holidays?", "schedule"),
        ("How can I pay my tuition fee statement and apply for installment scholarships?", "fees"),
        ("When are the mid-term examinations and what is the minimum attendance required?", "exams"),
        ("My ERP login password is not working and I lost my student ID card", "grievance"),
        ("What time does the hostel gate close at night and how is mess allotment done?", "hostel"),
        ("When is the university library open and how do I borrow books from the reading room?", "library"),
    ]

    for question, expected_intent in cases:
        result = classifier.classify(question)
        assert result.intent == expected_intent, f"Query '{question}' got intent '{result.intent}', expected '{expected_intent}'"
        assert result.confidence >= 0.60, f"Query '{question}' had low confidence {result.confidence}"
        assert result.matched is True
        assert result.query_type in QUERY_TYPES


def test_unmatched_and_out_of_domain_queries_have_zero_confidence() -> None:
    classifier = RuleBasedIntentClassifier()

    unrelated_queries = [
        "What is the average surface temperature of Mars?",
        "Tell me a funny joke about dolphins and penguins",
        "quick brown fox jumps over the lazy dog",
        "1234567890 !@#$%^&*",
    ]

    for query in unrelated_queries:
        result = classifier.classify(query)
        assert result.confidence == 0.0, f"Query '{query}' unexpectedly had confidence {result.confidence}"
        assert result.matched is False
        assert result.intent in INTENTS


def test_confidence_score_properties_and_margins() -> None:
    classifier = RuleBasedIntentClassifier()

    # Clear single-domain query should produce high confidence
    clear_result = classifier.classify("What are the hostel gate timings and mess rules?")
    assert 0.85 <= clear_result.confidence <= 0.99

    # Query with competing domain tokens should yield lower confidence than a pure clear query
    # "When is the tuition fee deadline on the academic calendar?" (fees vs schedule)
    competing_result = classifier.classify("When is the tuition fee deadline on the academic calendar?")
    assert competing_result.confidence <= clear_result.confidence

    # Every score must strictly obey the mathematical bounds [0.0, 1.0]
    for result in (clear_result, competing_result):
        assert 0.0 <= result.confidence <= 1.0


def test_user_query_type_heuristics() -> None:
    classifier = RuleBasedIntentClassifier()

    assert classifier.classify("My ERP password is reset and login is broken").query_type == "query_type_5"
    assert classifier.classify("How do I apply for hostel room allotment?").query_type == "query_type_4"
    assert classifier.classify("When is the tuition fee due date?").query_type == "query_type_3"
    assert classifier.classify("Who is the faculty professor for Data Science?").query_type == "query_type_2"
    assert classifier.classify("Where is the university library?").query_type == "query_type_1"


def test_telemetry_record_matches_exact_hcl_six_fields() -> None:
    store = TelemetryStore()
    record = store.record(
        session_id="S0001",
        user_query_type="query_type_4",
        intent="hostel",
        confidence_score=0.896,
        escalated=0,
        user_rating=4,
    )

    data = record.to_dict()
    assert set(data.keys()) == {
        "session_id",
        "user_query_type",
        "intent",
        "confidence_score",
        "escalated",
        "user_rating",
    }
    assert data["session_id"] == "S0001"
    assert data["user_query_type"] == "query_type_4"
    assert data["intent"] == "hostel"
    assert data["confidence_score"] == 0.896
    assert data["escalated"] == 0
    assert data["user_rating"] == 4


def test_privacy_guarantee_no_pii_or_raw_queries_persisted(monkeypatch) -> None:
    monkeypatch.setattr(main, "generate_answer", lambda *args: "Mocked answer without PII.")
    store = TelemetryStore()
    app = main.create_app(
        retriever=MockRetriever(),
        config=Settings(groq_api_key="test-key"),
        telemetry=store,
    )
    client = TestClient(app)

    pii_query = (
        "My name is John Doe, roll number 2023CS01, email john.doe@university.edu, "
        "and phone 9876543210. I need to reset my ERP password."
    )

    response = client.post("/api/chat", json={"question": pii_query})
    assert response.status_code == 200

    records = store.get_records()
    assert len(records) == 1
    record_dict = records[0].to_dict()

    serialized_telemetry_str = str(record_dict).lower()

    # Verify zero PII or raw query strings exist in the telemetry store
    for forbidden in ("john", "doe", "2023cs01", "university.edu", "9876543210", "password", "reset my"):
        assert forbidden not in serialized_telemetry_str, f"Forbidden PII token '{forbidden}' leaked into telemetry!"


def test_api_chat_enriches_response_with_session_and_telemetry(monkeypatch) -> None:
    monkeypatch.setattr(main, "generate_answer", lambda *args: "Mocked assistant answer.")
    store = TelemetryStore()
    app = main.create_app(
        retriever=MockRetriever(),
        config=Settings(groq_api_key="test-key"),
        telemetry=store,
    )
    client = TestClient(app)

    # 1. Check health reports classifier status
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["intent_classifier_ready"] is True
    assert health_resp.json()["telemetry_records_count"] == 0

    # 2. Chat with automatic session generation
    resp = client.post("/api/chat", json={"question": "Where is the library located?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "library"
    assert body["confidence_score"] >= 0.60
    assert body["session_id"] == "S0001"
    assert body["user_query_type"] in QUERY_TYPES

    # 3. Chat with caller-provided session ID
    resp2 = client.post("/api/chat", json={"question": "When is the tuition fee due?", "session_id": "CUSTOM-100"})
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["session_id"] == "CUSTOM-100"
    assert body2["intent"] == "fees"

    # 4. Verify telemetry store accumulated both sessions
    assert len(store.get_records()) == 2
