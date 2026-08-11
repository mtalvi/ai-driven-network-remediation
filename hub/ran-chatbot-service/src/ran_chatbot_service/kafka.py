"""Source of enriched RAN anomalies for the chatbot to talk about.

Reads recent enriched anomalies (root_cause + recommended_fix added) that
ran-rca-service publishes to the ran-anomalies-enriched Kafka topic.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from .config import ENRICHED_ANOMALIES_MAX_MESSAGES, ENRICHED_ANOMALIES_TOPIC, KAFKA_BOOTSTRAP
from .models import EnrichedAnomaly

logger = logging.getLogger(__name__)


def fetch_recent_anomalies() -> tuple[list[EnrichedAnomaly], bool]:
    """Read recent enriched RAN anomalies from Kafka using seek-to-end.

    Mirrors hub/chatbot-service/src/chatbot_service/kafka.py's fetch_recent_audits(),
    minus the timestamp-based cutoff: enriched anomaly records
    (contracts/ran-anomaly-enriched.schema.json) carry no timestamp field, so this
    just takes the most recent ENRICHED_ANOMALIES_MAX_MESSAGES records instead of
    filtering by a lookback window.

    Returns (anomalies, kafka_reachable).
    """
    from kafka import KafkaConsumer

    anomalies: list[EnrichedAnomaly] = []
    try:
        consumer = KafkaConsumer(
            ENRICHED_ANOMALIES_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            consumer_timeout_ms=2500,
            request_timeout_ms=10000,
            value_deserializer=lambda m: m.decode("utf-8", errors="replace"),
        )
    except Exception:
        logger.warning("Failed to connect to Kafka at %s", KAFKA_BOOTSTRAP, exc_info=True)
        return anomalies, False

    try:
        consumer.poll(timeout_ms=800)
        partitions = consumer.assignment()
        if not partitions:
            logger.debug("No partitions assigned for topic %s", ENRICHED_ANOMALIES_TOPIC)
            return anomalies, True

        max_per_partition = max(10, ENRICHED_ANOMALIES_MAX_MESSAGES // max(1, len(partitions)))
        for tp in partitions:
            end_offset = consumer.end_offsets([tp])[tp]
            start_offset = max(0, end_offset - max_per_partition)
            consumer.seek(tp, start_offset)

        for msg in consumer:
            # model_validate_json wraps both malformed JSON and schema mismatches
            # (missing/misnamed/mistyped fields) in the same ValidationError, so a
            # renamed field upstream is caught here instead of surfacing as a silent
            # None deep in the chat reply.
            try:
                anomalies.append(EnrichedAnomaly.model_validate_json(msg.value))
            except ValidationError:
                logger.warning("Skipping enriched anomaly that failed schema validation at offset %s", msg.offset)
                continue
            if len(anomalies) >= ENRICHED_ANOMALIES_MAX_MESSAGES:
                break
    except Exception:
        logger.exception("Error consuming from Kafka topic %s", ENRICHED_ANOMALIES_TOPIC)
        return anomalies, False
    finally:
        consumer.close()

    logger.info("Fetched %d enriched anomalies from %s", len(anomalies), ENRICHED_ANOMALIES_TOPIC)
    return anomalies, True
