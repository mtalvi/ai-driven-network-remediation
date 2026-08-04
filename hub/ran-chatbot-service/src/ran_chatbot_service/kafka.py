"""Source of enriched RAN anomalies for the chatbot to talk about.

Currently backed by a hardcoded stub (see _STUB_ANOMALIES below) because the
upstream `ran-rca-service` (LLM root cause analysis + RAG recommended fix,
publishing to the `ran-anomalies-enriched` Kafka topic) has not been built
yet. See fetch_recent_anomalies() for the exact swap-over point.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Matches the enriched-anomaly contract agreed with ran-rca-service:
# {cell_id, band, anomaly_type, anomaly, root_cause, recommended_fix}
_STUB_ANOMALIES: list[dict[str, Any]] = [
    {
        "cell_id": 42,
        "band": "Band 29",
        "anomaly_type": "LowRsrp",
        "anomaly": "Low RSRP: -125.0 dBm < -110.0 dBm",
        "root_cause": (
            "Low RSRP typically indicates poor radio conditions, possibly due to distance, "
            "interference, or physical obstructions between the UE and the cell."
        ),
        "recommended_fix": "Refer to Baicells documentation Section 4.2, Page 15 — Antenna Tilt Adjustment",
    },
    {
        "cell_id": 17,
        "band": "Band 71",
        "anomaly_type": "ThroughputDrop",
        "anomaly": "Throughput Drop: 18.89 Mbps (Current) vs. 54.75 Mbps (Avg Prior) - drop > 50%",
        "root_cause": (
            "A sudden throughput drop with stable UE count usually points to backhaul congestion "
            "or a scheduler/PRB allocation issue rather than a radio problem."
        ),
        "recommended_fix": "Refer to Baicells documentation Section 6.1, Page 32 — Backhaul Link Diagnostics",
    },
    {
        "cell_id": 8,
        "band": "Band 41",
        "anomaly_type": "SinrDegradation",
        "anomaly": "SINR Degradation: -2.0 dB < 0.0 dB",
        "root_cause": (
            "Negative SINR suggests interference from a neighboring cell or an external source "
            "overwhelming the desired signal on this band."
        ),
        "recommended_fix": "Refer to Baicells documentation Section 7.3, Page 41 — Interference Mitigation",
    },
    {
        "cell_id": 8,
        "band": "Band 41",
        "anomaly_type": "HighPrbUtilization",
        "anomaly": "High PRB Utilization: 97.0% >= 95.0%",
        "root_cause": (
            "Sustained PRB utilization near capacity indicates the cell is overloaded for its "
            "current configuration, likely due to unplanned traffic growth in the sector."
        ),
        "recommended_fix": "Refer to Baicells documentation Section 5.4, Page 27 — Capacity Expansion / Load Balancing",
    },
]


def fetch_recent_anomalies() -> tuple[list[dict[str, Any]], bool]:
    """Return recently enriched RAN anomalies.

    TODO(ran-rca-service): once ran-rca-service is deployed and publishing to
    the `ran-anomalies-enriched` Kafka topic (see ENRICHED_ANOMALIES_TOPIC in
    config.py), replace this stub with a real KafkaConsumer, following the
    same seek-to-end pattern as
    hub/chatbot-service/src/chatbot_service/kafka.py's fetch_recent_audits().
    Keep the (list[dict], bool) return shape so the /ready dependency-check
    call site in __init__.py does not need to change.
    """
    logger.debug("Returning %d stub RAN anomalies (ran-rca-service not yet available)", len(_STUB_ANOMALIES))
    return list(_STUB_ANOMALIES), True
