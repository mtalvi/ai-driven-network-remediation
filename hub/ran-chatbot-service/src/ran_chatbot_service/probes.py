"""Generic HTTP reachability probe, used by the /ready endpoint."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import SSL_VERIFY

logger = logging.getLogger(__name__)


async def probe_http(url: str, timeout: float = 4.0) -> dict[str, Any]:
    """Probe a service endpoint. Treats 200/401/403/404/405 as reachable."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=SSL_VERIFY) as client:
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
