"""Generic HTTP reachability probe, used by /ready endpoints."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def probe_http(url: str, timeout: float = 4.0, verify: bool | str = True) -> dict[str, Any]:
    """Probe a service endpoint. Treats 200/401/403/404/405 as reachable.

    `verify` is passed straight through to httpx (bool, or a CA bundle path
    string) — callers supply their own service-specific SSL_VERIFY setting,
    since this package has no config module of its own.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=verify) as client:
            resp = await client.get(url)
            reachable = resp.status_code in {200, 401, 403, 404, 405}
            return {
                "status": "up" if reachable else f"http-{resp.status_code}",
                "http_code": resp.status_code,
                "reachable": reachable,
            }
    except Exception:
        logger.debug("Probe failed for %s", url, exc_info=True)
        return {"status": "down", "http_code": None, "reachable": False}
