# shared-utils

Domain-free infrastructure helpers shared by the chatbot BFF services
([`hub/chatbot-service`](../chatbot-service) and [`hub/ran-chatbot-service`](../ran-chatbot-service)):

- `utc_now()` — current UTC timestamp as an ISO 8601 string.
- `normalize_session_id()` — returns a stripped session id, or generates a new UUID one if missing/blank.
- `build_deps()` — builds the `_deps` envelope (`{"status": "ok"}` or `{"status": "degraded", "unavailable": [...]}`) from named dependency checks.
- `probe_http()` — generic HTTP reachability probe used by `/ready` endpoints, treating 200/401/403/404/405 as reachable.

These four functions were previously byte-for-byte duplicated between the two services. Anything
service-specific (e.g. `chatbot-service`'s `parse_iso()`/`get_mcp_items()`/`fetch_servicenow_incident_count()`)
stays in that service — this package intentionally only holds the exact overlap, with no premature
abstraction of anything else.

Both services depend on this package via a local `uv` path source (the same pattern already used
by [`hub/telco-oran`](../telco-oran) as a shared dependency of `ran-anomaly-detector`/`ran-rca-service`).

## Usage

```bash
cd hub/shared-utils
uv sync --group dev
uv run pytest
```
