"""Integration tests for the Telco O-RAN chatbot BFF service (ran-chatbot-service).

These run against a deployed ran-chatbot-service (via port-forward or direct URL).
Set RAN_CHATBOT_SERVICE_URL env var to override the default http://localhost:8008.

Unlike hub/chatbot-service's BFF, this service has no /api/summary or
/api/integrations endpoints — it is a thin channel layer with /health, /ready,
/api/chat, /api/anomalies (GET + DELETE), and /api/demo/trigger, backed by a
background Kafka consumer (see hub/ran-chatbot-service's README) rather than
per-request calls, so most of these tests don't need to trigger or wait for
any Kafka event themselves. test_demo_trigger is the exception: it actually
publishes a synthetic reading to ran-combined-metrics, the same way a real
operator clicking the webapp's demo button would. test_clear_anomalies wipes
the live buffer, so it's pinned via @pytest.mark.order to run after
test_demo_trigger explicitly (not relying on file-declaration order, which
isn't guaranteed under e.g. a future pytest-randomly addition or a -k filter).
"""

import pytest


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


def test_anomalies(ran_chatbot_client):
    """Anomalies endpoint returns the current in-memory buffer (possibly empty if
    nothing has been detected/enriched yet), newest first."""
    response = ran_chatbot_client.get("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "anomalies" in data
    assert data["count"] == len(data["anomalies"])
    assert "_deps" in data
    assert data["_deps"]["status"] in {"ok", "degraded"}
    for anomaly in data["anomalies"]:
        assert "cell_id" in anomaly
        assert "band" in anomaly
        assert "anomaly_type" in anomaly
        assert "anomaly" in anomaly
        assert "root_cause" in anomaly
        assert "recommended_fix" in anomaly


def test_demo_trigger(ran_chatbot_client):
    """Demo trigger publishes a synthetic reading to ran-combined-metrics and
    reports where to look for it (cell_id/band), the same real input topic
    ran-anomaly-detector consumes from."""
    response = ran_chatbot_client.post("/api/demo/trigger", json={"scenario": "low_signal"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["scenario"] == "low_signal"
    assert data["cell_id"] == 9001
    assert data["band"]
    assert data["topic"] == "ran-combined-metrics"
    assert isinstance(data["kafka_offset"], int)
    assert "_deps" in data
    assert data["_deps"]["status"] in {"ok", "degraded"}


def test_demo_trigger_unknown_scenario_falls_back_to_default(ran_chatbot_client):
    response = ran_chatbot_client.post("/api/demo/trigger", json={"scenario": "not-a-real-scenario"})
    assert response.status_code == 200
    assert response.json()["scenario"] == "low_signal"


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


@pytest.mark.order(after="test_demo_trigger")
def test_clear_anomalies(ran_chatbot_client):
    """Clearing the buffer empties it immediately (verified via a follow-up
    GET). Explicitly ordered to run after test_demo_trigger (rather than
    relying on file-declaration order) since it wipes whatever's currently
    buffered, including anything that test published."""
    response = ran_chatbot_client.delete("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"
    assert data["count"] == 0
    assert "_deps" in data

    follow_up = ran_chatbot_client.get("/api/anomalies")
    assert follow_up.json()["count"] == 0
