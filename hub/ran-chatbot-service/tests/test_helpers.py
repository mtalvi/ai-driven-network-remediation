"""Unit tests for helper functions: dependency envelope, chat formatting.

Kafka consumption itself (AnomaliesConsumer) is tested separately in
test_kafka_consumer.py.
"""

import httpx
import pytest
import respx
from ran_chatbot_service.chat import build_chat_context, call_model, format_chat_reply
from ran_chatbot_service.config import MODEL_API_URL
from ran_chatbot_service.models import ModelSource
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


class TestBuildChatContext:
    def test_includes_anomaly_details(self, sample_anomalies):
        prompt = build_chat_context("What's wrong with cell 42?", sample_anomalies, [])
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

    def test_blank_root_cause_and_fix_render_as_na(self, sample_anomaly):
        """Regression test: ran-rca-service publishes root_cause/recommended_fix as ""
        (not omitted) when its own LLM/RAG enrichment fails, observed during E2E
        testing. That must render as "n/a", not a blank line."""
        anomaly = sample_anomaly.model_copy(update={"root_cause": "", "recommended_fix": ""})
        prompt = build_chat_context("What's wrong?", [anomaly], [])
        assert "Root cause: n/a" in prompt
        assert "Recommended fix: n/a" in prompt

    def test_uses_the_five_most_recent_anomalies(self, sample_anomaly):
        """Regression test: the AnomaliesConsumer buffer is in ascending Kafka
        offset order (oldest first), so the 5 most recent are the tail of the
        list, not the head."""
        anomalies = [sample_anomaly.model_copy(update={"cell_id": i}) for i in range(7)]
        prompt = build_chat_context("Status?", anomalies, [])
        for cell_id in range(2, 7):
            assert f"Cell {cell_id}" in prompt
        for cell_id in range(0, 2):
            assert f"Cell {cell_id} (" not in prompt


class TestCallModel:
    """call_model() now takes a shared httpx.AsyncClient (constructed once at app
    startup, see __init__.py's lifespan) instead of creating a new one per call —
    these tests verify both the HTTP response handling and that reusing a single
    client instance across multiple calls works correctly."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_live_reply(self):
        respx.post(MODEL_API_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"text": "Cell 42 has weak signal."}]})
        )
        async with httpx.AsyncClient() as client:
            reply, source = await call_model("prompt", client)

        assert reply == "Cell 42 has weak signal."
        assert source == ModelSource.LIVE

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_reported_with_status_code(self):
        respx.post(MODEL_API_URL).mock(return_value=httpx.Response(404))
        async with httpx.AsyncClient() as client:
            reply, source = await call_model("prompt", client)

        assert reply == ""
        assert source == "http-404"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_choices_reported_as_empty(self):
        respx.post(MODEL_API_URL).mock(return_value=httpx.Response(200, json={"choices": []}))
        async with httpx.AsyncClient() as client:
            reply, source = await call_model("prompt", client)

        assert reply == ""
        assert source == ModelSource.EMPTY

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error_reported_as_unreachable(self):
        respx.post(MODEL_API_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        async with httpx.AsyncClient() as client:
            reply, source = await call_model("prompt", client)

        assert reply == ""
        assert source == ModelSource.UNREACHABLE

    @pytest.mark.asyncio
    @respx.mock
    async def test_reuses_the_same_client_instance_across_multiple_calls(self):
        """Regression test for the shared-client change: calling call_model() twice
        with the same client (as concurrent /api/chat requests now do) must not
        raise or corrupt state — httpx.AsyncClient is designed for exactly this."""
        route = respx.post(MODEL_API_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"text": "ok"}]})
        )
        async with httpx.AsyncClient() as client:
            first = await call_model("prompt one", client)
            second = await call_model("prompt two", client)

        assert first == ("ok", ModelSource.LIVE)
        assert second == ("ok", ModelSource.LIVE)
        assert route.call_count == 2


class TestFormatChatReply:
    def test_with_anomalies_and_live_reply(self, sample_anomalies):
        reply = format_chat_reply("What's wrong?", "Cell 42 has weak signal.", sample_anomalies)
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

    def test_blank_root_cause_and_fix_render_as_na(self, sample_anomaly):
        anomaly = sample_anomaly.model_copy(update={"root_cause": "", "recommended_fix": ""})
        reply = format_chat_reply("What's wrong?", "insight", [anomaly])
        assert "Root Cause:\n- n/a" in reply
        assert "Recommended Fix:\n- n/a" in reply

    def test_latest_anomaly_is_the_last_element_not_the_first(self, sample_anomaly):
        """Regression test: anomalies is in ascending Kafka offset order (oldest
        first), so the newest/latest anomaly is anomalies[-1], not anomalies[0]."""
        oldest = sample_anomaly.model_copy(update={"cell_id": 1})
        newest = sample_anomaly.model_copy(update={"cell_id": 2})
        reply = format_chat_reply("What's wrong?", "insight", [oldest, newest])
        assert "Latest anomaly: Cell 2" in reply
        assert "Latest anomaly: Cell 1" not in reply
