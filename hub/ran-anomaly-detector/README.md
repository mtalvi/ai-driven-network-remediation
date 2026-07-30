# ran-anomaly-detector

Rule-based RAN/O-RAN anomaly detection workflow. Consumes RAN KPI readings (CSV) from the
`ran-combined-metrics` Kafka topic, maps them onto the [`telco-oran`](../telco-oran) domain model
(`Cell`, `RanKpiRecord`, `CellBandMetrics`), and runs the existing deterministic `AnomalyDetector`
against a rolling per-cell/band history — no LLM involved.

This is an independent workflow/deployment from `agent-service`: it does not touch the existing
pod-failure remediation LangGraph, and can be enabled/disabled separately in Helm.

## Output

For each detected anomaly, one JSON record is produced:

```json
{
  "cell_id": 42,
  "band": "Band 29",
  "anomaly_type": "LowRsrp",
  "anomaly": "Low RSRP: -125.0 dBm < -110.0 dBm"
}
```

This service only logs/exposes anomalies (via `/anomalies`), kept in a bounded in-memory buffer —
no database or object storage is used, confirmed as sufficient by design. LLM-based root cause
analysis and RAG-based recommended fixes are separate, planned follow-up work (extending this
output with `root_cause`/`recommended_fix` fields).

## Usage

```bash
cd hub/ran-anomaly-detector
uv sync --group dev
uv run pytest
```
