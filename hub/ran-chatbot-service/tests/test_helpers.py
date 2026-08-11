"""Unit tests for helper functions: dependency envelope, Kafka fetch, chat formatting."""

import json

from ran_chatbot_service.chat import build_chat_context, format_chat_reply
from ran_chatbot_service.kafka import fetch_recent_anomalies
from ran_chatbot_service.models import EnrichedAnomaly
from ran_chatbot_service.utils import build_deps, normalize_session_id

_SAMPLE_ANOMALY_DICT = {
    "cell_id": 42,
    "band": "Band 29",
    "anomaly_type": "LowRsrp",
    "anomaly": "Low RSRP: -125.0 dBm < -110.0 dBm",
    "root_cause": "Poor radio conditions.",
    "recommended_fix": "Section 4.2 — Antenna Tilt Adjustment",
}
_SAMPLE_ANOMALY = EnrichedAnomaly(**_SAMPLE_ANOMALY_DICT)


class _FakeMessage:
    def __init__(self, value: str, offset: int = 0) -> None:
        self.value = value
        self.offset = offset


class _FakeKafkaConsumer:
    """Minimal stand-in for kafka.KafkaConsumer supporting the seek-to-end read
    pattern used by fetch_recent_anomalies() (assignment/end_offsets/seek/iter)."""

    def __init__(self, *args, messages: list[_FakeMessage] | None = None, **kwargs) -> None:
        self._messages = list(messages or [])
        self.closed = False

    def poll(self, timeout_ms: int = 800):
        return {}

    def assignment(self):
        return {"tp0"}

    def end_offsets(self, partitions):
        return {p: len(self._messages) for p in partitions}

    def seek(self, partition, offset) -> None:
        pass

    def __iter__(self):
        return iter(self._messages)

    def close(self) -> None:
        self.closed = True


class _NoPartitionsKafkaConsumer(_FakeKafkaConsumer):
    def assignment(self):
        return set()


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
    def test_returns_parsed_enriched_anomalies(self, monkeypatch):
        messages = [_FakeMessage(json.dumps(_SAMPLE_ANOMALY_DICT), offset=0)]
        monkeypatch.setattr("kafka.KafkaConsumer", lambda *a, **kw: _FakeKafkaConsumer(messages=messages))

        anomalies, ok = fetch_recent_anomalies()

        assert ok is True
        assert anomalies == [_SAMPLE_ANOMALY]

    def test_skips_malformed_messages(self, monkeypatch):
        messages = [
            _FakeMessage("not valid json", offset=0),
            _FakeMessage(json.dumps(_SAMPLE_ANOMALY_DICT), offset=1),
        ]
        monkeypatch.setattr("kafka.KafkaConsumer", lambda *a, **kw: _FakeKafkaConsumer(messages=messages))

        anomalies, ok = fetch_recent_anomalies()

        assert ok is True
        assert anomalies == [_SAMPLE_ANOMALY]

    def test_skips_messages_missing_required_fields(self, monkeypatch):
        """Regression test: a producer-side rename/omission of a required field
        (e.g. cell_id) must be caught here, not silently propagate as None deep
        into the chat reply."""
        incomplete = {k: v for k, v in _SAMPLE_ANOMALY_DICT.items() if k != "cell_id"}
        messages = [
            _FakeMessage(json.dumps(incomplete), offset=0),
            _FakeMessage(json.dumps(_SAMPLE_ANOMALY_DICT), offset=1),
        ]
        monkeypatch.setattr("kafka.KafkaConsumer", lambda *a, **kw: _FakeKafkaConsumer(messages=messages))

        anomalies, ok = fetch_recent_anomalies()

        assert ok is True
        assert anomalies == [_SAMPLE_ANOMALY]

    def test_returns_empty_when_no_partitions_assigned(self, monkeypatch):
        monkeypatch.setattr("kafka.KafkaConsumer", lambda *a, **kw: _NoPartitionsKafkaConsumer())

        anomalies, ok = fetch_recent_anomalies()

        assert ok is True
        assert anomalies == []

    def test_kafka_unreachable_returns_false(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise RuntimeError("connection refused")

        monkeypatch.setattr("kafka.KafkaConsumer", _raise)

        anomalies, ok = fetch_recent_anomalies()

        assert ok is False
        assert anomalies == []


class TestBuildChatContext:
    def test_includes_anomaly_details(self):
        anomalies = [_SAMPLE_ANOMALY]
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

    def test_blank_root_cause_and_fix_render_as_na(self):
        """Regression test: ran-rca-service publishes root_cause/recommended_fix as ""
        (not omitted) when its own LLM/RAG enrichment fails, observed during E2E
        testing. That must render as "n/a", not a blank line."""
        anomaly = _SAMPLE_ANOMALY.model_copy(update={"root_cause": "", "recommended_fix": ""})
        prompt = build_chat_context("What's wrong?", [anomaly], [])
        assert "Root cause: n/a" in prompt
        assert "Recommended fix: n/a" in prompt


class TestFormatChatReply:
    def test_with_anomalies_and_live_reply(self):
        anomalies = [_SAMPLE_ANOMALY]
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

    def test_blank_root_cause_and_fix_render_as_na(self):
        anomaly = _SAMPLE_ANOMALY.model_copy(update={"root_cause": "", "recommended_fix": ""})
        reply = format_chat_reply("What's wrong?", "insight", [anomaly])
        assert "Root Cause:\n- n/a" in reply
        assert "Recommended Fix:\n- n/a" in reply
