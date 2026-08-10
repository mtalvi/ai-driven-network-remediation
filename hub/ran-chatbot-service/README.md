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

## Where the anomaly data comes from

[`kafka.py`](src/ran_chatbot_service/kafka.py)'s `fetch_recent_anomalies()` reads the
`ENRICHED_ANOMALIES_TOPIC` Kafka topic (`ran-anomalies-enriched` by default, see
[`config.py`](src/ran_chatbot_service/config.py)) using a seek-to-end `KafkaConsumer`, following
the same pattern as
[`hub/chatbot-service/src/chatbot_service/kafka.py`](../chatbot-service/src/chatbot_service/kafka.py)'s
`fetch_recent_audits()`. That topic is populated by
[`ran-rca-service`](../ran-rca-service) (LLM root cause analysis + RAG-based recommended fix),
which enriches each anomaly detected by [`ran-anomaly-detector`](../ran-anomaly-detector) with
`root_cause` and `recommended_fix`, matching this output contract
(`contracts/ran-anomaly-enriched.schema.json`):

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

Unlike `fetch_recent_audits()`, there's no timestamp-based lookback filtering here — enriched
anomaly records carry no timestamp field, so `fetch_recent_anomalies()` just takes the most
recent `ENRICHED_ANOMALIES_MAX_MESSAGES` records instead.

## Usage

```bash
cd hub/ran-chatbot-service
uv sync --group dev
uv run pytest
```
