"""Service-specific helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def get_mcp_items(integrations_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract MCP-group integrations from the integrations payload."""
    return [i for i in integrations_data.get("integrations", []) if i.get("group") == "mcp"]
