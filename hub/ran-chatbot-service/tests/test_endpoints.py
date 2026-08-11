"""Unit tests for the RAN chatbot BFF endpoints."""

from unittest.mock import AsyncMock, patch


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "ran-chatbot-bff"
    assert "version" in data


@patch("ran_chatbot_service.probe_http", new_callable=AsyncMock)
def test_ready_all_up(mock_probe, client):
    mock_probe.return_value = {"status": "up", "http_code": 200, "reachable": True}
    client.app.state.kafka_consumer.is_connected = True

    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["checks"] == {"kafka": True, "llm": True}


@patch("ran_chatbot_service.probe_http", new_callable=AsyncMock)
def test_ready_llm_unreachable(mock_probe, client):
    mock_probe.return_value = {"status": "down", "http_code": None, "reachable": False}
    client.app.state.kafka_consumer.is_connected = True

    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["llm"] is False


@patch("ran_chatbot_service.probe_http", new_callable=AsyncMock)
def test_ready_kafka_unreachable(mock_probe, client):
    mock_probe.return_value = {"status": "up", "http_code": 200, "reachable": True}
    client.app.state.kafka_consumer.is_connected = False

    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["kafka"] is False


@patch("ran_chatbot_service.call_model", new_callable=AsyncMock)
def test_chat(mock_model, client, sample_anomalies):
    mock_model.return_value = ("Cell 42 has weak signal due to distance from the antenna.", "live")
    client.app.state.recent_anomalies.extend(sample_anomalies)
    client.app.state.kafka_consumer.is_connected = True

    resp = client.post("/api/chat", json={"message": "What's wrong with cell 42?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["_deps"] == {"status": "ok"}
    assert "reply" in data
    assert data["model"]["name"]
    assert data["model"]["source"] == "live"
    assert "session_id" in data
    assert data["context"]["anomaly_count"] > 0


@patch("ran_chatbot_service.call_model", new_callable=AsyncMock)
def test_chat_model_unavailable(mock_model, client, sample_anomalies):
    mock_model.return_value = ("", "unreachable")
    client.app.state.recent_anomalies.extend(sample_anomalies)
    client.app.state.kafka_consumer.is_connected = True

    resp = client.post("/api/chat", json={"message": "Status?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["_deps"] == {"status": "degraded", "unavailable": ["llm"]}
    assert "fallback" in data["reply"].lower()
    assert data["model"]["source"] == "unreachable"


@patch("ran_chatbot_service.call_model", new_callable=AsyncMock)
def test_chat_model_http_error_reported_as_degraded(mock_model, client, sample_anomalies):
    """Regression test: an HTTP error from the LLM (e.g. a 404 for an unregistered
    model) must be reported as degraded, not silently treated as healthy."""
    mock_model.return_value = ("", "http-404")
    client.app.state.recent_anomalies.extend(sample_anomalies)
    client.app.state.kafka_consumer.is_connected = True

    resp = client.post("/api/chat", json={"message": "Status?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["_deps"] == {"status": "degraded", "unavailable": ["llm"]}
    assert data["model"]["source"] == "http-404"


@patch("ran_chatbot_service.call_model", new_callable=AsyncMock)
def test_chat_kafka_unreachable(mock_model, client):
    mock_model.return_value = ("insight", "live")
    client.app.state.kafka_consumer.is_connected = False

    resp = client.post("/api/chat", json={"message": "Status?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["_deps"] == {"status": "degraded", "unavailable": ["kafka"]}
    assert data["context"]["anomaly_count"] == 0


def test_chat_empty_message(client):
    resp = client.post("/api/chat", json={"message": "  "})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Please enter a question."


@patch("ran_chatbot_service.call_model", new_callable=AsyncMock)
def test_chat_preserves_session_history(mock_model, client, sample_anomalies):
    mock_model.return_value = ("ok", "live")
    client.app.state.recent_anomalies.extend(sample_anomalies)
    client.app.state.kafka_consumer.is_connected = True
    session_id = "test-session-1"

    first = client.post("/api/chat", json={"message": "hello", "session_id": session_id})
    second = client.post("/api/chat", json={"message": "follow up", "session_id": session_id})

    assert first.json()["session_id"] == session_id
    assert second.json()["session_id"] == session_id
