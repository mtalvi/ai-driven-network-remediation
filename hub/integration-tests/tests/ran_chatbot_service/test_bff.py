"""Integration tests for the Telco O-RAN chatbot BFF service (ran-chatbot-service).

These run against a deployed ran-chatbot-service (via port-forward or direct URL).
Set RAN_CHATBOT_SERVICE_URL env var to override the default http://localhost:8008.

Unlike hub/chatbot-service's BFF, this service has no /api/summary, /api/integrations,
or /api/demo/trigger endpoints — it is a thin channel layer with only /health, /ready,
and /api/chat, backed by a background Kafka consumer (see hub/ran-chatbot-service's
README) rather than per-request calls, so these tests don't need to trigger or wait
for any Kafka event themselves.
"""


def test_health(ran_chatbot_client):
    """Service is alive and reports correct identity."""
    response = ran_chatbot_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ran-chatbot-bff"
    assert "version" in data


def test_ready(ran_chatbot_client):
    """Readiness probe reports Kafka + LLM dependency status but always passes."""
    response = ran_chatbot_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "kafka" in data["checks"]
    assert "llm" in data["checks"]
    assert isinstance(data["checks"]["kafka"], bool)
    assert isinstance(data["checks"]["llm"], bool)


def test_chat(ran_chatbot_client):
    """Chat endpoint accepts a message and returns a structured reply, with or
    without real anomaly context (gracefully degrades if none has been detected
    yet)."""
    response = ran_chatbot_client.post(
        "/api/chat",
        json={"message": "What's wrong with cell 42?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert "session_id" in data
    assert "model" in data
    assert data["model"]["name"]
    assert data["model"]["source"]
    assert "context" in data
    assert "anomaly_count" in data["context"]
    assert data["context"]["anomaly_count"] >= 0
    assert "_deps" in data
    assert data["_deps"]["status"] in {"ok", "degraded"}


def test_chat_empty_message(ran_chatbot_client):
    """Chat endpoint handles empty message gracefully without calling the LLM."""
    response = ran_chatbot_client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "Please enter a question."
    assert "session_id" in data


def test_chat_preserves_session_history(ran_chatbot_client):
    """Two chat requests with the same session_id are tracked as one conversation."""
    session_id = "integration-test-session"

    first = ran_chatbot_client.post(
        "/api/chat",
        json={"message": "Any anomalies right now?", "session_id": session_id},
    )
    second = ran_chatbot_client.post(
        "/api/chat",
        json={"message": "What about the previous one?", "session_id": session_id},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["session_id"] == session_id
    assert second.json()["session_id"] == session_id
