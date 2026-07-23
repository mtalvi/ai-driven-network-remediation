from unittest.mock import patch

import pytest
from helpers import make_rca, make_state

from agent_service.models import RemediationResult
from agent_service.nodes.servicenow_close import servicenow_close_node

STUB_TICKET = "INC0050001"


@pytest.fixture(autouse=True)
def _enable_create_resolved():
    """Enable resolved-ticket creation for all tests; individual tests override as needed."""
    with patch("agent_service.nodes.servicenow_close.SERVICENOW_CREATE_RESOLVED", True):
        yield


def _stub_remediation(**overrides):
    defaults = dict(
        action_taken="restart-nginx",
        tool_used="mcp-noc-aap",
        success=True,
        job_id="42",
        duration_seconds=8.5,
        output_summary="Pod restarted successfully",
        timestamp="2026-07-20T10:00:00Z",
    )
    defaults.update(overrides)
    return RemediationResult(**defaults)


def _make_capture_invoke(ticket=STUB_TICKET):
    calls = []

    async def _capture(tool_name, kwargs):
        calls.append({"tool_name": tool_name, "kwargs": kwargs})
        if tool_name == "create_incident":
            return {"success": True, "ticket_number": ticket, "sys_id": "abc123"}
        if tool_name == "resolve_incident":
            return {"success": True, "ticket_number": ticket, "state": "Resolved"}
        return {}

    return calls, _capture


# ─────────────────────────────────────────────────────────────────────────────
# Happy path: successful remediation creates and resolves a ticket
# ─────────────────────────────────────────────────────────────────────────────


class TestServicenowCloseHappyPath:
    async def test_creates_and_resolves_ticket(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result["servicenow_ticket"] == STUB_TICKET
        assert len(calls) == 2
        assert calls[0]["tool_name"] == "create_incident"
        assert calls[1]["tool_name"] == "resolve_incident"

    async def test_short_description_contains_resolved_tag(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            await servicenow_close_node(state)

        short_desc = calls[0]["kwargs"]["short_description"]
        assert "[AI-NOC][Resolved]" in short_desc
        assert "OOMKilled" in short_desc
        assert "nginx-abc123" in short_desc

    async def test_resolution_notes_contain_rca_and_remediation_details(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            await servicenow_close_node(state)

        resolve_kwargs = calls[1]["kwargs"]
        assert resolve_kwargs["ticket_number"] == STUB_TICKET
        assert "restart-nginx" in resolve_kwargs["resolution_notes"]
        assert "Container killed by OOM" in resolve_kwargs["resolution_notes"]

    async def test_priority_maps_from_severity(self):
        state = make_state(
            root_cause_analysis=make_rca(estimated_severity="critical"),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            await servicenow_close_node(state)

        assert calls[0]["kwargs"]["priority"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# No-op cases: node should return empty dict and not call ServiceNow
# ─────────────────────────────────────────────────────────────────────────────


class TestServicenowCloseNoOp:
    async def test_escalate_decision_raises(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="escalate",
            servicenow_ticket="INC0099999",
        )

        with pytest.raises(RuntimeError, match="graph wiring error"):
            await servicenow_close_node(state)

    async def test_failed_remediation_is_noop(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(success=False),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result == {}
        assert len(calls) == 0

    async def test_no_remediation_result_is_noop(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=None,
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result == {}
        assert len(calls) == 0

    async def test_no_rca_is_noop(self):
        state = make_state(
            root_cause_analysis=None,
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result == {}
        assert len(calls) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Lightspeed path: also creates a resolved ticket on success
# ─────────────────────────────────────────────────────────────────────────────


class TestServicenowCloseLightspeed:
    async def test_lightspeed_success_creates_resolved_ticket(self):
        state = make_state(
            root_cause_analysis=make_rca(failure_type="DNSFailure"),
            decision="lightspeed",
            remediation_result=_stub_remediation(
                action_taken="lightspeed-playbook",
                tool_used="ansible-lightspeed",
            ),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result["servicenow_ticket"] == STUB_TICKET
        assert len(calls) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Error handling: ServiceNow failures are non-fatal
# ─────────────────────────────────────────────────────────────────────────────


class TestServicenowCloseErrorHandling:
    async def test_create_failure_returns_empty(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )

        async def _fail_create(tool_name, kwargs):
            return {"success": False, "error": "connection refused"}

        with patch("agent_service.nodes.servicenow_close._invoke_tool", _fail_create):
            result = await servicenow_close_node(state)

        assert result == {}

    async def test_create_exception_returns_empty(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )

        async def _explode(tool_name, kwargs):
            raise ConnectionError("MCP server unreachable")

        with patch("agent_service.nodes.servicenow_close._invoke_tool", _explode):
            result = await servicenow_close_node(state)

        assert result == {}

    async def test_resolve_failure_still_returns_ticket(self):
        """Even if resolve_incident fails, the ticket was created and should be returned."""
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        call_count = {"n": 0}

        async def _create_ok_resolve_fail(tool_name, kwargs):
            call_count["n"] += 1
            if tool_name == "create_incident":
                return {"success": True, "ticket_number": STUB_TICKET, "sys_id": "x"}
            raise ConnectionError("resolve failed")

        with patch("agent_service.nodes.servicenow_close._invoke_tool", _create_ok_resolve_fail):
            result = await servicenow_close_node(state)

        assert result["servicenow_ticket"] == STUB_TICKET
        assert call_count["n"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Config flag: SERVICENOW_CREATE_RESOLVED=false skips ticket creation
# ─────────────────────────────────────────────────────────────────────────────


class TestServicenowCloseDisabled:
    @pytest.fixture(autouse=True)
    def _disable_create_resolved(self):
        with patch("agent_service.nodes.servicenow_close.SERVICENOW_CREATE_RESOLVED", False):
            yield

    async def test_successful_remediation_skipped_when_disabled(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="remediate",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result == {}
        assert len(calls) == 0

    async def test_lightspeed_success_skipped_when_disabled(self):
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="lightspeed",
            remediation_result=_stub_remediation(),
        )
        calls, fake_invoke = _make_capture_invoke()

        with patch("agent_service.nodes.servicenow_close._invoke_tool", fake_invoke):
            result = await servicenow_close_node(state)

        assert result == {}
        assert len(calls) == 0

    async def test_escalate_still_raises_when_disabled(self):
        """The escalate guard fires regardless of the config flag."""
        state = make_state(
            root_cause_analysis=make_rca(),
            decision="escalate",
            servicenow_ticket="INC0099999",
        )

        with pytest.raises(RuntimeError, match="graph wiring error"):
            await servicenow_close_node(state)
