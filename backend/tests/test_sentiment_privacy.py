from fastapi.testclient import TestClient

from app.main import create_app
from app.sentiment import analyze_sentiment
from app.settings import Settings
from app.telemetry import TelemetryStore


class EmptyRetriever:
    chunks = []

    def search(self, query: str, top_k: int = 4):
        return []


def make_client() -> tuple[TestClient, TelemetryStore]:
    store = TelemetryStore()
    app = create_app(
        retriever=EmptyRetriever(),
        config=Settings(groq_api_key=None),
        telemetry=store,
    )
    return TestClient(app), store


def test_lightweight_sentiment_labels_and_negation() -> None:
    assert analyze_sentiment("Thanks, that was helpful and clear.").label == "positive"
    assert analyze_sentiment("I am frustrated and worried about this broken service.").label == "negative"
    assert analyze_sentiment("When does the library close?").label == "neutral"
    assert analyze_sentiment("The answer was not helpful.").label == "negative"
    assert analyze_sentiment("The result was not bad.").label == "positive"


def test_negative_no_evidence_is_flagged_locally_without_claiming_delivery() -> None:
    client, store = make_client()
    response = client.post("/api/chat", json={"question": "I am frustrated about a fee question not listed here."})
    assert response.status_code == 200
    body = response.json()
    assert body["sentiment_label"] == "negative"
    assert body["escalated"] is True
    assert body["escalation_reason"] == "negative_sentiment"
    assert "marked the conversation locally" in body["answer"]
    assert "does not create a ticket or notify staff" in body["answer"]
    assert len(store.get_records()) == 1


def test_opt_out_header_prevents_chat_telemetry_and_session_id() -> None:
    client, store = make_client()
    response = client.post(
        "/api/chat",
        json={"question": "When does the library close?", "session_id": "PREVIOUS-SESSION"},
        headers={"X-Telemetry-Opt-Out": "1"},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] is None
    assert store.get_records() == []


def test_opt_out_header_prevents_feedback_mutation() -> None:
    client, store = make_client()
    chat_response = client.post("/api/chat", json={"question": "When does the library close?"})
    session_id = chat_response.json()["session_id"]
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating is None

    response = client.post(
        "/api/feedback",
        json={"session_id": session_id, "user_rating": 5},
        headers={"X-Telemetry-Opt-Out": "true"},
    )
    assert response.status_code == 200
    assert "not recorded" in response.json()["message"].lower()
    record = store.get_record(session_id)
    assert record is not None
    assert record.user_rating is None


def test_cors_allows_telemetry_opt_out_header() -> None:
    client, _ = make_client()
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-telemetry-opt-out",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "x-telemetry-opt-out" in allowed_headers
