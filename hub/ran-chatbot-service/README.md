# ran-chatbot-service

Thin conversational entrypoint (FastAPI BFF) for the Telco O-RAN anomaly detection and root
cause analysis use case. Exposes `POST /api/chat` so operators can ask about recently detected
RAN cell anomalies, their likely root cause, and the recommended fix, in natural language.

This service is a **thin channel layer**: it does not detect anomalies or perform root cause
analysis itself. That domain logic lives in [`ran-anomaly-detector`](../ran-anomaly-detector)
(rule-based detection) and the upstream `ran-rca-service` (LLM root cause analysis + RAG
recommended fix retrieval). This service only builds a conversational prompt from already-
enriched anomaly data and formats the LLM's reply.

This is an independent workflow/deployment from `hub/chatbot-service` (the network remediation
NOC chatbot): different domain, different Kafka topics, different persona/prompt, and it can be
enabled/disabled separately in Helm. The two services do share one thing: a handful of
domain-free infrastructure helpers (`utc_now`, `normalize_session_id`, `build_deps`, `probe_http`)
factored out into [`hub/shared`](../shared/) (`shared.utils` / `shared.probes`), a local package
depended on via a `uv` path source, so fixes to that plumbing aren't duplicated across both
services. `hub/shared` is also used by `ran-anomaly-detector`, `ran-rca-service`, and
`agent-service` for its Kafka consumer and RAG client modules, unrelated to this service.

## Where the anomaly data comes from

[`kafka.py`](src/ran_chatbot_service/kafka.py)'s `AnomaliesConsumer` is a single background thread,
started at app startup (see the `lifespan` in
[`__init__.py`](src/ran_chatbot_service/__init__.py)), that owns the Kafka connection to
`ENRICHED_ANOMALIES_TOPIC` (`ran-anomalies-enriched` by default, see
[`config.py`](src/ran_chatbot_service/config.py)) and continuously fills an in-memory buffer
(`deque(maxlen=ENRICHED_ANOMALIES_MAX_MESSAGES)`) — the same pattern already used by
[`ran-anomaly-detector`](../ran-anomaly-detector)'s `MetricsConsumer`. `POST /api/chat` just reads
that buffer directly: no per-request Kafka I/O, unlike the older per-request
`fetch_recent_audits()`-style approach `hub/chatbot-service` uses. On connect (and every
reconnect), it seeks each partition back a bounded window and drains it so the buffer has recent
history immediately, rather than only filling in as new anomalies trickle in. It intentionally
does **not** use a Kafka consumer group — the topic has multiple partitions, and a shared group
would split them across replicas if this service is ever scaled beyond one, so each replica stays
group-less and independently sees the full topic.

That topic is populated by [`ran-rca-service`](../ran-rca-service) (LLM root cause analysis + RAG-
based recommended fix), which enriches each anomaly detected by
[`ran-anomaly-detector`](../ran-anomaly-detector) with `root_cause` and `recommended_fix`, matching
this output contract (`contracts/ran-anomaly-enriched.schema.json`):

```json
{
  "cell_id": 42,
  "band": "Band 29",
  "anomaly_type": "LowRsrp",
  "anomaly": "Low RSRP: -125.0 dBm < -110.0 dBm",
  "root_cause": "Low RSRP typically indicates poor radio conditions, possibly due to distance, interference, or physical obstructions.",
  "recommended_fix": "Refer to Baicells documentation Section 4.2, Page 15 — Antenna Tilt Adjustment"
}
```

## Usage

```bash
cd hub/ran-chatbot-service
uv sync --group dev
uv run pytest
```

`uv sync` resolves `shared` from the sibling [`hub/shared`](../shared/) directory via a `uv` path
source, so it must exist alongside this one (already true within this repo checkout). For the
same reason, the container image's build context is `hub/`, not this directory — see
`build-ran-chatbot-image` in the root `Makefile`.
