"""Demo trigger: inject a synthetic RAN KPI reading into the real pipeline.

Mirrors hub/chatbot-service/src/chatbot_service/kafka.py's build_demo_event()/
publish_demo_event() split, but the wire format here is CSV text (matching
hub/ran-anomaly-detector/src/ran_anomaly_detector/csv_mapper.py's
REQUIRED_COLUMNS), not JSON — ran-anomaly-detector expects a raw CSV blob on
ran-combined-metrics, not a JSON envelope.

Publishing a fresh, never-before-seen (cell_id, band) pair means only the
"instant" anomaly rules (LowRsrp, SinrDegradation, HighPrbUtilization,
CellOutage — see telco_oran.domain.anomaly_detector) can fire; the trend
rules (ThroughputDrop, UesSpikeOrDrop) need >=3 prior readings for that
cell+band and can't trigger from a single demo click.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from shared.utils import utc_now

from .config import DEMO_METRICS_TOPIC, KAFKA_BOOTSTRAP

logger = logging.getLogger(__name__)

CSV_COLUMNS = (
    "cell_id",
    "max_capacity",
    "lat",
    "lon",
    "area_type",
    "city",
    "band",
    "frequency",
    "datetime",
    "ues_usage",
    "rsrp",
    "rsrq",
    "sinr",
    "throughput_mbps",
    "latency_ms",
)

# city="Demo City" makes it unmistakable in the UI that this is synthetic,
# not a real network reading. cell_id 9001/9002 are reserved for demo use —
# unlikely to collide with real KPI feeds.
_SCENARIOS: dict[str, dict[str, Any]] = {
    "low_signal": {
        "cell_id": 9001,
        "max_capacity": 100,
        "lat": 33.05,
        "lon": -96.8,
        "area_type": "urban",
        "city": "Demo City",
        "band": "Band 71",
        "frequency": "600",
        "ues_usage": 10,
        "rsrp": -125.0,
        "rsrq": -15.0,
        "sinr": 8.0,
        "throughput_mbps": 50.0,
        "latency_ms": 20.0,
    },
    "cell_outage": {
        "cell_id": 9002,
        "max_capacity": 100,
        "lat": 33.05,
        "lon": -96.8,
        "area_type": "rural",
        "city": "Demo City",
        "band": "Band 29",
        "frequency": "700",
        "ues_usage": 0,
        "rsrp": -120.0,
        "rsrq": -20.0,
        "sinr": -10.0,
        "throughput_mbps": 0.0,
        "latency_ms": 200.0,
    },
}
DEFAULT_SCENARIO = "low_signal"


def build_demo_csv(scenario: str) -> tuple[str, dict[str, Any]]:
    """Build a single-row CSV blob for a demo scenario.

    Returns (csv_blob, meta) where meta is {"scenario", "cell_id", "band"} —
    the normalized scenario name actually used (falls back to
    DEFAULT_SCENARIO for unknown input, same as chatbot_service's
    build_demo_event()) plus the cell/band the operator should look for.
    """
    normalized = scenario.strip().lower()
    spec = _SCENARIOS.get(normalized)
    if spec is None:
        normalized = DEFAULT_SCENARIO
        spec = _SCENARIOS[normalized]

    row = {**spec, "datetime": utc_now()}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerow(row)

    meta = {"scenario": normalized, "cell_id": spec["cell_id"], "band": spec["band"]}
    return buf.getvalue(), meta


def publish_demo_metrics(csv_blob: str) -> int:
    """Publish a demo CSV reading to ran-combined-metrics. Returns the message offset.

    No value_serializer: ran-anomaly-detector's csv_mapper expects raw CSV
    text, so the value is UTF-8-encoded bytes, not JSON.
    """
    from kafka import KafkaProducer

    producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    try:
        future = producer.send(DEMO_METRICS_TOPIC, value=csv_blob.encode("utf-8"))
        metadata = future.get(timeout=10)
    finally:
        # close() flushes internally, so no separate flush() call is needed;
        # the finally block also guarantees the producer (its background
        # sender thread + socket) isn't leaked if future.get() raises.
        producer.close(timeout=10)
    logger.info("Published demo RAN metrics to %s at offset %d", DEMO_METRICS_TOPIC, metadata.offset)
    return int(metadata.offset)
