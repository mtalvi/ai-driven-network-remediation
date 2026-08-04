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
enabled/disabled separately in Helm.

## Current status: anomaly data is a stub

`ran-rca-service` (which will publish enriched anomalies — `root_cause` + `recommended_fix` —
to the `ran-anomalies-enriched` Kafka topic) has not been built yet. Until it lands, this service
returns a hardcoded set of example enriched anomalies from
[`kafka.py`](src/ran_chatbot_service/kafka.py), matching the agreed output contract exactly:

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

See the `TODO(ran-rca-service)` comment on `fetch_recent_anomalies()` in
[`kafka.py`](src/ran_chatbot_service/kafka.py) for exactly what to change once that service is
deployed — a real `KafkaConsumer` against `ENRICHED_ANOMALIES_TOPIC`
(`ran-anomalies-enriched`, already wired in [`config.py`](src/ran_chatbot_service/config.py)),
following the same seek-to-end pattern as
[`hub/chatbot-service/src/chatbot_service/kafka.py`](../chatbot-service/src/chatbot_service/kafka.py)'s
`fetch_recent_audits()`. No other code (including the `/ready` dependency check or `/api/chat`)
needs to change for that swap.

## Usage

```bash
cd hub/ran-chatbot-service
uv sync --group dev
uv run pytest
```
