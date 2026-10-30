from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.documents import DocumentChunk
from app.retriever import SearchResult
from app.settings import Settings
from app.telemetry import TelemetryStore


class StubRetriever:
    def __init__(self, score: float = 0.90, empty: bool = False):
        self.score = score
        self.empty = empty
        self.chunks = [
            DocumentChunk(
                chunk_id="chunk-faq-it",
                document_id="Q001",
                title="Reset ERP password",
                text="Visit the IT Helpdesk on campus or portal to reset your password.",
                source="faq.json",
                metadata={"category": "grievance"},
            )
        ]

    def search(self, query: str, top_k: int = 4):
        if self.empty or self.score < 0.24:
            return []
        return [SearchResult(chunk=self.chunks[0], score=self.score)]


def create_test_client(
    retriever=None,
    groq_api_key: str | None = "test-key",
    monkeypatch=None,
    telemetry: TelemetryStore | None = None,
):
    if monkeypatch:
        monkeypatch.setattr(main, "generate_answer", lambda *args: "Grounded test answer from knowledge base.")
    store = telemetry or TelemetryStore()
    app = main.create_app(
        retriever=retriever or StubRetriever(),
        config=Settings(groq_api_key=groq_api_key),
        telemetry=store,
    )
    return TestClient(app), store


# ==============================================================================
# Escalation Tests
# ==============================================================================

def test_explicit_human_request_triggers_escalation(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    queries = [
        "I want to speak to a human.",
        "Please connect me to an officer.",
        "I need to talk to the university helpdesk.",
        "Can I speak with a real person?",
    ]

    for q in queries:
        resp = client.post("/api/chat", json={"question": q})
        assert resp.status_code == 200
        body = resp.json()
        assert body["escalated"] is True
        assert body["escalation_reason"] == "explicit_request"
        assert body["requires_clarification"] is False
        assert "marked this conversation for possible staff follow-up" in body["answer"]
        assert "No staff member has been notified" in body["answer"]
        assert "cannot create a support ticket" in body["answer"]


def test_grievance_intent_triggers_escalation_without_evidence() -> None:
    # Empty retriever simulates no evidence found for this specific complaint
    client, store = create_test_client(retriever=StubRetriever(empty=True))

    resp = client.post("/api/chat", json={"question": "I have a major complaint about harassment in the campus cafeteria"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is True
    assert body["escalation_reason"] == "grievance"
    assert body["intent"] == "grievance"
    assert "This grievance is flagged locally" in body["answer"]
    assert "no support ticket or staff notification" in body["answer"]
    assert "official Grievance Cell" in body["answer"]


def test_grievance_with_evidence_appends_escalation_notice(monkeypatch) -> None:
    client, store = create_test_client(retriever=StubRetriever(score=0.92), monkeypatch=monkeypatch)

    resp = client.post("/api/chat", json={"question": "My ERP password is reset and login is broken"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is True
    assert body["escalation_reason"] == "grievance"
    assert body["intent"] == "grievance"
    assert "Human Follow-Up Recommended" in body["answer"]
    assert "Grounded test answer" in body["answer"]


def test_low_confidence_classification_requests_clarification() -> None:
    client, store = create_test_client(retriever=StubRetriever(empty=True))

    # Out-of-domain query produces confidence 0.0 (< 0.60)
    resp = client.post("/api/chat", json={"question": "What is the atmospheric composition of Jupiter?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is False
    assert body["requires_clarification"] is True
    assert body["escalation_reason"] == "low_confidence"
    assert "not completely certain which category" in body["answer"]


def test_low_confidence_does_not_claim_human_handoff() -> None:
    client, store = create_test_client(retriever=StubRetriever(empty=True))

    resp = client.post("/api/chat", json={"question": "quantum tunneling flux"})
    assert resp.status_code == 200
    body = resp.json()
    assert "agent has been contacted" not in body["answer"].lower()
    assert "ticket was created" not in body["answer"].lower()
    assert body["escalated"] is False


def test_normal_well_supported_questions_are_not_escalated(monkeypatch) -> None:
    client, store = create_test_client(retriever=StubRetriever(score=0.95), monkeypatch=monkeypatch)

    resp = client.post("/api/chat", json={"question": "Who is the faculty instructor for Artificial Intelligence?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is False
    assert body["escalation_reason"] is None
    assert body["requires_clarification"] is False
    assert body["used_context"] is True


def test_insufficient_retrieval_evidence_does_not_fabricate(monkeypatch) -> None:
    # Retriever returns score below threshold (0.10 < 0.24)
    client, store = create_test_client(retriever=StubRetriever(score=0.10), monkeypatch=monkeypatch)

    resp = client.post("/api/chat", json={"question": "Where can students park private aircraft?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["used_context"] is False
    assert body["sources"] == []
    assert "couldn't find reliable information" in body["answer"].lower()


def test_retrieval_similarity_and_classifier_confidence_remain_distinct(monkeypatch) -> None:
    # Query has clear intent (fees) with high classifier confidence, but 0 retrieval evidence
    client, store = create_test_client(retriever=StubRetriever(empty=True), monkeypatch=monkeypatch)

    resp = client.post("/api/chat", json={"question": "Can I pay my tuition fee using extraterrestrial gold bullion?"})
    assert resp.status_code == 200
    body = resp.json()
    # Classifier recognized the 'fees' keywords
    assert body["intent"] == "fees"
    assert body["confidence_score"] >= 0.60
    # But RAG found no evidence
    assert body["used_context"] is False
    assert body["sources"] == []


def test_multiple_escalation_triggers_produce_one_coherent_response_and_one_telemetry_record(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    # Contains BOTH explicit request ("speak to a human") AND grievance ("unresolved complaint")
    dual_query = "I have an unresolved complaint about my hostel room, please connect me to a human officer."
    resp = client.post("/api/chat", json={"question": dual_query, "session_id": "S9999"})
    assert resp.status_code == 200
    body = resp.json()

    # Priority 1 applies
    assert body["escalated"] is True
    assert body["escalation_reason"] == "explicit_request"

    # Exactly one telemetry record exists for this session
    records = [r for r in store.get_records() if r.session_id == "S9999"]
    assert len(records) == 1
    assert records[0].escalated == 1


def test_existing_response_fields_remain_present(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    resp = client.post("/api/chat", json={"question": "When is the tuition fee due date?"})
    assert resp.status_code == 200
    data = resp.json()

    for expected_key in (
        "answer",
        "sources",
        "used_context",
        "session_id",
        "intent",
        "confidence_score",
        "user_query_type",
        "escalated",
        "escalation_reason",
        "requires_clarification",
    ):
        assert expected_key in data, f"Missing required response field: '{expected_key}'"


# ==============================================================================
# Feedback API Tests (POST /api/feedback)
# ==============================================================================

def test_feedback_valid_ratings(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    # Seed session
    chat_resp = client.post("/api/chat", json={"question": "When does the library open?"})
    session_id = chat_resp.json()["session_id"]

    # Test boundary 1
    resp1 = client.post("/api/feedback", json={"session_id": session_id, "user_rating": 1})
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True
    assert resp1.json()["user_rating"] == 1
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating == 1

    # Test intermediate 3
    resp3 = client.post("/api/feedback", json={"session_id": session_id, "user_rating": 3})
    assert resp3.status_code == 200
    assert resp3.json()["user_rating"] == 3
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating == 3

    # Test boundary 5
    resp5 = client.post("/api/feedback", json={"session_id": session_id, "user_rating": 5})
    assert resp5.status_code == 200
    assert resp5.json()["user_rating"] == 5
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating == 5


def test_feedback_rejects_ratings_out_of_range(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)
    chat_resp = client.post("/api/chat", json={"question": "Library timing"})
    session_id = chat_resp.json()["session_id"]

    # Rating 0 (below 1)
    resp_low = client.post("/api/feedback", json={"session_id": session_id, "user_rating": 0})
    assert resp_low.status_code == 422

    # Rating 6 (above 5)
    resp_high = client.post("/api/feedback", json={"session_id": session_id, "user_rating": 6})
    assert resp_high.status_code == 422

    # Negative rating
    resp_neg = client.post("/api/feedback", json={"session_id": session_id, "user_rating": -5})
    assert resp_neg.status_code == 422


def test_feedback_rejects_missing_or_blank_session_id() -> None:
    client, _ = create_test_client()

    # Missing session_id
    assert client.post("/api/feedback", json={"user_rating": 4}).status_code == 422

    # Blank session_id
    assert client.post("/api/feedback", json={"session_id": "   ", "user_rating": 4}).status_code == 422


def test_feedback_unknown_session_returns_404() -> None:
    client, _ = create_test_client()

    resp = client.post("/api/feedback", json={"session_id": "NON_EXISTENT_SESSION_999", "user_rating": 5})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_submitting_feedback_does_not_create_duplicate_telemetry_record(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    chat_resp = client.post("/api/chat", json={"question": "Fee payment schedule"})
    session_id = chat_resp.json()["session_id"]
    initial_count = len(store.get_records())

    # Submit feedback 3 times
    client.post("/api/feedback", json={"session_id": session_id, "user_rating": 2})
    client.post("/api/feedback", json={"session_id": session_id, "user_rating": 4})
    client.post("/api/feedback", json={"session_id": session_id, "user_rating": 5})

    # Total records count must still be exactly initial_count
    assert len(store.get_records()) == initial_count
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating == 5


def test_invalid_feedback_does_not_mutate_telemetry(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    chat_resp = client.post("/api/chat", json={"question": "Hostel room allotment"})
    session_id = chat_resp.json()["session_id"]

    # Initial rating is None
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating is None

    # Failed feedback attempt with invalid rating 9
    client.post("/api/feedback", json={"session_id": session_id, "user_rating": 9})

    # Rating should remain None
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating is None


# ==============================================================================
# Privacy and Telemetry Integrity Tests
# ==============================================================================

def test_telemetry_contains_strictly_six_hcl_columns(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    client.post("/api/chat", json={"question": "When does registration begin?"})
    records = store.get_records()
    assert len(records) >= 1

    for rec in records:
        d = rec.to_dict()
        assert set(d.keys()) == {
            "session_id",
            "user_query_type",
            "intent",
            "confidence_score",
            "escalated",
            "user_rating",
        }
        assert isinstance(d["escalated"], int)
        assert d["escalated"] in (0, 1)


def test_raw_questions_and_pii_not_stored_in_telemetry(monkeypatch) -> None:
    client, store = create_test_client(monkeypatch=monkeypatch)

    sensitive_text = (
        "I am Alice Cooper, roll number 2024CS99, phone 9998887776, "
        "email alice.cooper@college.edu. I want to speak to an officer about fees."
    )

    client.post("/api/chat", json={"question": sensitive_text})
    records = store.get_records()
    dump = str([r.to_dict() for r in records]).lower()

    for pii in ("alice", "cooper", "2024cs99", "9998887776", "college.edu", "speak to an officer"):
        assert pii not in dump, f"PII token '{pii}' leaked into telemetry records!"


def test_provider_credentials_not_returned_by_api(monkeypatch) -> None:
    client, _ = create_test_client(groq_api_key="super-secret-groq-key-999", monkeypatch=monkeypatch)

    chat_resp = client.post("/api/chat", json={"question": "Where is the accounts office?"})
    health_resp = client.get("/api/health")
    feedback_resp = client.post("/api/feedback", json={"session_id": "S0001", "user_rating": 5})

    for resp in (chat_resp, health_resp, feedback_resp):
        assert "super-secret-groq-key-999" not in resp.text
