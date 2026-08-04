"""Unit tests for helper functions: dependency envelope, anomaly stub, chat formatting."""

from ran_chatbot_service.chat import build_chat_context, format_chat_reply
from ran_chatbot_service.kafka import fetch_recent_anomalies
from ran_chatbot_service.utils import build_deps, normalize_session_id


class TestBuildDeps:
    def test_all_ok(self):
        assert build_deps({"kafka": True, "llm": True}) == {"status": "ok"}

    def test_empty_checks(self):
        assert build_deps({}) == {"status": "ok"}

    def test_single_failure(self):
        result = build_deps({"kafka": True, "llm": False})
        assert result == {"status": "degraded", "unavailable": ["llm"]}

    def test_multiple_failures_sorted(self):
        result = build_deps({"llm": False, "kafka": False})
        assert result == {"status": "degraded", "unavailable": ["kafka", "llm"]}


class TestNormalizeSessionId:
    def test_returns_provided_id(self):
        assert normalize_session_id("session-123") == "session-123"

    def test_generates_id_when_missing(self):
        assert normalize_session_id(None)

    def test_generates_id_when_blank(self):
        assert normalize_session_id("   ")


class TestFetchRecentAnomalies:
    def test_returns_stub_anomalies_and_true(self):
        anomalies, ok = fetch_recent_anomalies()
        assert ok is True
        assert len(anomalies) > 0
        for anomaly in anomalies:
            assert {"cell_id", "band", "anomaly_type", "anomaly", "root_cause", "recommended_fix"} <= set(
                anomaly.keys()
            )

    def test_returns_a_copy_not_shared_mutable_state(self):
        first, _ = fetch_recent_anomalies()
        first.append({"cell_id": 999})
        second, _ = fetch_recent_anomalies()
        assert len(second) < len(first)


class TestBuildChatContext:
    def test_includes_anomaly_details(self):
        anomalies = [
            {
                "cell_id": 42,
                "band": "Band 29",
                "anomaly_type": "LowRsrp",
                "anomaly": "Low RSRP: -125.0 dBm < -110.0 dBm",
                "root_cause": "Poor radio conditions.",
                "recommended_fix": "Section 4.2 — Antenna Tilt Adjustment",
            }
        ]
        prompt = build_chat_context("What's wrong with cell 42?", anomalies, [])
        assert "Cell 42" in prompt
        assert "Band 29" in prompt
        assert "LowRsrp" in prompt
        assert "Poor radio conditions." in prompt
        assert "Antenna Tilt Adjustment" in prompt
        assert "What's wrong with cell 42?" in prompt

    def test_handles_no_anomalies(self):
        prompt = build_chat_context("Any issues?", [], [])
        assert "No recent RAN anomalies detected." in prompt

    def test_includes_recent_conversation_history(self):
        history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        prompt = build_chat_context("next question", [], history)
        assert "user: hello" in prompt
        assert "assistant: hi" in prompt


class TestFormatChatReply:
    def test_with_anomalies_and_live_reply(self):
        anomalies = [
            {
                "cell_id": 42,
                "band": "Band 29",
                "anomaly_type": "LowRsrp",
                "anomaly": "Low RSRP: -125.0 dBm < -110.0 dBm",
                "root_cause": "Poor radio conditions.",
                "recommended_fix": "Section 4.2 — Antenna Tilt Adjustment",
            }
        ]
        reply = format_chat_reply("What's wrong?", "Cell 42 has weak signal.", anomalies)
        assert "Anomalies detected: 1" in reply
        assert "Cell 42" in reply
        assert "Poor radio conditions." in reply
        assert "Antenna Tilt Adjustment" in reply
        assert "Cell 42 has weak signal." in reply

    def test_with_no_anomalies(self):
        reply = format_chat_reply("Any issues?", "All clear.", [])
        assert "Anomalies detected: 0" in reply
        assert "No RAN anomalies currently detected." in reply

    def test_falls_back_when_model_reply_is_empty(self):
        reply = format_chat_reply("Status?", "", [])
        assert "fallback" in reply.lower()
