import importlib

import pytest


def test_defaults():
    config = importlib.reload(importlib.import_module("ran_anomaly_detector.config"))

    assert config.KAFKA_BOOTSTRAP == "kafka:9092"
    assert config.KAFKA_METRICS_TOPIC == "ran-combined-metrics"
    assert config.KAFKA_GROUP_ID == "ran-anomaly-detector"
    assert config.KAFKA_CONSUMER_ENABLED is True
    assert config.HISTORY_WINDOW_SIZE == 10
    assert config.RECENT_ANOMALIES_LIMIT == 100


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP", "kafka.example:9092")
    monkeypatch.setenv("KAFKA_METRICS_TOPIC", "custom-metrics")
    monkeypatch.setenv("KAFKA_GROUP_ID", "test-group")
    monkeypatch.setenv("KAFKA_CONSUMER_ENABLED", "false")
    monkeypatch.setenv("HISTORY_WINDOW_SIZE", "5")
    monkeypatch.setenv("RECENT_ANOMALIES_LIMIT", "20")

    config = importlib.reload(importlib.import_module("ran_anomaly_detector.config"))

    try:
        assert config.KAFKA_BOOTSTRAP == "kafka.example:9092"
        assert config.KAFKA_METRICS_TOPIC == "custom-metrics"
        assert config.KAFKA_GROUP_ID == "test-group"
        assert config.KAFKA_CONSUMER_ENABLED is False
        assert config.HISTORY_WINDOW_SIZE == 5
        assert config.RECENT_ANOMALIES_LIMIT == 20
    finally:
        importlib.reload(config)


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_consumer_enabled_truthy_values(monkeypatch, value):
    monkeypatch.setenv("KAFKA_CONSUMER_ENABLED", value)
    config = importlib.reload(importlib.import_module("ran_anomaly_detector.config"))
    try:
        assert config.KAFKA_CONSUMER_ENABLED is True
    finally:
        importlib.reload(config)
