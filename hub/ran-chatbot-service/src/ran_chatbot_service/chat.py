"""LLM chat: context building, model calls, and reply formatting."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import (
    MODEL_API_URL,
    MODEL_MAX_TOKENS,
    MODEL_NAME,
    MODEL_TIMEOUT_SECONDS,
    SSL_VERIFY,
)

logger = logging.getLogger(__name__)


def _format_anomalies(anomalies: list[dict[str, Any]]) -> str:
    """Format enriched RAN anomalies for LLM context."""
    if not anomalies:
        return "No recent RAN anomalies detected."
    lines = []
    for a in anomalies[:5]:
        lines.append(
            f"  - Cell {a.get('cell_id')} ({a.get('band')}) [{a.get('anomaly_type')}]: {a.get('anomaly')}\n"
            f"    Root cause: {a.get('root_cause', 'n/a')}\n"
            f"    Recommended fix: {a.get('recommended_fix', 'n/a')}"
        )
    return "\n".join(lines)


def build_chat_context(
    user_message: str,
    anomalies: list[dict[str, Any]],
    history: list[dict[str, str]],
) -> str:
    """Build a context-rich prompt for the LLM."""
    recent = history[-4:]
    convo = "\n".join(f"{item['role']}: {item['content']}" for item in recent) or "none"
    anomalies_context = _format_anomalies(anomalies)

    return (
        "You are a telco RAN engineer assistant for an O-RAN anomaly detection and root cause "
        "analysis system.\n"
        "Answer the operator's request directly with concise, actionable analysis about the "
        "detected RAN cell anomalies below.\n"
        "When discussing an anomaly, mention: the affected cell/band, the anomaly type, the "
        "likely root cause, and the recommended fix (including which vendor documentation "
        "section it references).\n"
        "Do NOT repeat headers or formatting — just provide your insight.\n"
        "Keep output under 250 words.\n\n"
        f"Model: {MODEL_NAME}\n\n"
        f"Recently detected RAN anomalies:\n{anomalies_context}\n\n"
        f"Recent conversation: {convo}\n\n"
        f"Operator request: {user_message}\n\n"
        "Your analysis:"
    )


async def call_model(prompt: str) -> tuple[str, str]:
    """Call the LLM endpoint. Returns (reply_text, source).

    NOTE: Minimal implementation sufficient for V1 (single vLLM endpoint).
    Consider replacing with litellm/llama-index if we need streaming,
    multi-model fallback, or token management.
    """
    if not MODEL_API_URL:
        return "", "disabled"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": MODEL_MAX_TOKENS,
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=MODEL_TIMEOUT_SECONDS, verify=SSL_VERIFY) as client:
            resp = await client.post(MODEL_API_URL, json=payload)
        if resp.status_code != 200:
            logger.warning("LLM returned HTTP %d from %s", resp.status_code, MODEL_API_URL)
            return "", f"http-{resp.status_code}"
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            text = (choices[0].get("text") or choices[0].get("message", {}).get("content") or "").strip()
            if text:
                logger.debug("LLM replied with %d chars", len(text))
                return text, "live"
        return "", "empty"
    except Exception:
        logger.warning("LLM unreachable at %s", MODEL_API_URL, exc_info=True)
        return "", "unreachable"


def format_chat_reply(
    user_message: str,
    raw_reply: str,
    anomalies: list[dict[str, Any]],
) -> str:
    """Format LLM output into a structured reply, or generate a deterministic fallback."""
    if not anomalies:
        cells_line = "- No RAN anomalies currently detected."
        root_cause = "n/a"
        recommended_fix = "n/a"
    else:
        latest = anomalies[0]
        cells_line = (
            f"- Latest anomaly: Cell {latest.get('cell_id')} ({latest.get('band')}) "
            f"[{latest.get('anomaly_type')}] — {latest.get('anomaly')}"
        )
        root_cause = latest.get("root_cause", "n/a")
        recommended_fix = latest.get("recommended_fix", "n/a")

    if raw_reply:
        model_insight = raw_reply.strip()
    else:
        model_insight = "Live model unavailable; using deterministic operational fallback."

    return (
        "Summary:\n"
        f"- Anomalies detected: {len(anomalies)}\n"
        f"{cells_line}\n"
        f"- Request: {user_message}\n\n"
        "Root Cause:\n"
        f"- {root_cause}\n\n"
        "Recommended Fix:\n"
        f"- {recommended_fix}\n\n"
        "Model Output:\n"
        f"- {model_insight}\n\n"
        "Next Action:\n"
        "1. Review the recommended fix against current field conditions.\n"
        "2. Dispatch a technician or trigger remote reconfiguration if applicable.\n"
        "3. Confirm KPI recovery after the fix is applied."
    )
