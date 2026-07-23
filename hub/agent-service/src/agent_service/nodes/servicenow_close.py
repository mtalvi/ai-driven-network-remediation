"""ServiceNow incident lifecycle: create-and-resolve after successful remediation.

When ``SERVICENOW_CREATE_RESOLVED`` is enabled and remediation or lightspeed
succeeds, this node creates an informational ServiceNow incident in resolved
state so every automated action has a corresponding audit trail in ITSM.
When the flag is disabled (the default), this node is a no-op.

The graph topology must never route escalations here — the escalate node
owns that ticket.  If this node is reached with decision == "escalate",
it raises ``RuntimeError`` so the mis-wiring is caught immediately.
"""

from loguru import logger

from agent_service.config import SERVICENOW_CREATE_RESOLVED
from agent_service.utils import invoke_tool as _invoke_tool

_PRIORITY_MAP = {"critical": 1, "high": 2, "medium": 3, "low": 4}
_DEFAULT_PRIORITY = 4


def _build_resolution_description(state) -> str:
    rca = state.root_cause_analysis
    log_event = state.log_event
    result = state.remediation_result

    lines = [
        "Auto-remediated by AI-driven network remediation agent.",
        "",
        f"Failure Type: {rca.failure_type}",
        f"Severity: {rca.estimated_severity}",
        f"Edge Site: {log_event.edge_site_id}",
        f"Namespace: {log_event.namespace}",
        f"Pod: {log_event.pod_name}",
        "",
        f"RCA Summary: {rca.summary}",
    ]
    if result:
        lines += [
            "",
            "--- Remediation ---",
            f"Action: {result.action_taken}",
            f"Tool: {result.tool_used}",
            f"Job ID: {result.job_id}",
            f"Duration: {result.duration_seconds:.1f}s",
            f"Output: {result.output_summary}",
        ]
    return "\n".join(lines) + "\n"


async def servicenow_close_node(state) -> dict:
    """Create a pre-resolved ServiceNow incident for successful remediations."""

    if state.decision == "escalate":
        raise RuntimeError(
            "servicenow_close_node reached with decision='escalate'; "
            "graph wiring error — escalations must route directly to notify"
        )

    if not SERVICENOW_CREATE_RESOLVED:
        logger.debug("SERVICENOW_CREATE_RESOLVED is disabled, skipping resolved ticket creation")
        return {}

    # Only create a resolved ticket if remediation actually succeeded
    result = state.remediation_result
    if not result or not result.success:
        return {}

    rca = state.root_cause_analysis
    log_event = state.log_event
    if not rca or not log_event:
        return {}

    # Build the incident payload from RCA and log event context
    short_description = (
        f"[AI-NOC][Resolved] {rca.failure_type} – {log_event.pod_name}"
        f" in {log_event.namespace} ({log_event.edge_site_id})"
    )
    priority = _PRIORITY_MAP.get(rca.estimated_severity, _DEFAULT_PRIORITY)
    description = _build_resolution_description(state)

    # Step 1: Create the incident via MCP tool
    logger.info(f"Creating resolved ServiceNow incident: {short_description}")
    try:
        create_resp = await _invoke_tool(
            "create_incident",
            {
                "short_description": short_description,
                "description": description,
                "priority": priority,
            },
        )
    except Exception as exc:
        logger.warning(f"ServiceNow create-resolved failed: {exc}")
        return {}

    if not create_resp.get("success"):
        logger.warning(f"ServiceNow create-resolved failed: {create_resp.get('error', 'unknown')}")
        return {}

    ticket = create_resp.get("ticket_number", "") or create_resp.get("number", "")
    if not ticket:
        return {}

    # Step 2: Immediately resolve the incident with remediation details
    resolution_notes = (
        f"Auto-remediated: {result.action_taken} via {result.tool_used} "
        f"(job {result.job_id}, {result.duration_seconds:.1f}s). "
        f"RCA: {rca.summary}"
    )
    try:
        await _invoke_tool(
            "resolve_incident",
            {
                "ticket_number": ticket,
                "resolution_notes": resolution_notes,
            },
        )
    except Exception as exc:
        logger.warning(f"ServiceNow resolve failed for {ticket}: {exc}")

    logger.info(f"ServiceNow resolved ticket created: {ticket}")
    return {"servicenow_ticket": ticket}
