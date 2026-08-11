"""Domain-free infrastructure helpers shared across chatbot BFF services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_session_id(session_id: str | None) -> str:
    return session_id.strip() if session_id and session_id.strip() else str(uuid4())


def build_deps(checks: dict[str, bool]) -> dict[str, Any]:
    """Build the _deps envelope from named dependency checks.

    checks: {"kafka": True, "servicenow": False, "llm": True}
    returns: {"status": "ok"} or {"status": "degraded", "unavailable": ["servicenow"]}
    """
    unavailable = [name for name, ok in checks.items() if not ok]
    if not unavailable:
        return {"status": "ok"}
    return {"status": "degraded", "unavailable": sorted(unavailable)}
