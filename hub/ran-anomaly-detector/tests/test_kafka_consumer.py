import threading
import time

import pytest

import ran_anomaly_detector.kafka.consumer as consumer_module
from ran_anomaly_detector.kafka.consumer import MetricsConsumer


class _FakeMessage:
    def __init__(self, topic: str, partition: int, offset: int, value: bytes) -> None:
        self.topic = topic
        self.partition = partition
        self.offset = offset
        self.value = value


class _FakeKafkaConsumer:
    """Minimal stand-in for kafka.KafkaConsumer, delivering a fixed batch once then idling."""

    def __init__(self, *args, **kwargs) -> None:
        self.closed = False
        self._delivered = False

    def poll(self, timeout_ms: int = 1000):
        if self._delivered or self.closed:
            return {}
        self._delivered = True
        return {
            ("ran-combined-metrics", 0): [
                _FakeMessage("ran-combined-metrics", 0, 0, b"first"),
                _FakeMessage("ran-combined-metrics", 0, 1, b"second"),
            ]
        }

    def close(self) -> None:
        self.closed = True


def test_topic_is_required():
    with pytest.raises(ValueError):
        MetricsConsumer(lambda value: None, bootstrap_servers="kafka:9092", topic="", group_id="g")


def test_start_dispatches_polled_messages_to_handler(monkeypatch):
    monkeypatch.setattr(consumer_module, "KafkaConsumer", _FakeKafkaConsumer)

    received: list[bytes] = []
    lock = threading.Lock()

    def handler(value: bytes) -> None:
        with lock:
            received.append(value)

    consumer = MetricsConsumer(
        handler,
        bootstrap_servers="kafka:9092",
        topic="ran-combined-metrics",
        group_id="test-group",
        poll_timeout_ms=50,
    )
    consumer.start()

    deadline = time.time() + 2
    while time.time() < deadline and len(received) < 2:
        time.sleep(0.05)

    assert consumer.is_connected
    consumer.stop()

    assert received == [b"first", b"second"]


def test_handler_exception_does_not_crash_consumer_loop(monkeypatch):
    monkeypatch.setattr(consumer_module, "KafkaConsumer", _FakeKafkaConsumer)

    call_count = {"n": 0}

    def failing_handler(value: bytes) -> None:
        call_count["n"] += 1
        raise RuntimeError("boom")

    consumer = MetricsConsumer(
        failing_handler,
        bootstrap_servers="kafka:9092",
        topic="ran-combined-metrics",
        group_id="test-group",
        poll_timeout_ms=50,
    )
    consumer.start()

    deadline = time.time() + 2
    while time.time() < deadline and call_count["n"] < 2:
        time.sleep(0.05)

    consumer.stop()

    assert call_count["n"] == 2


def test_is_connected_false_before_start():
    consumer = MetricsConsumer(
        lambda value: None,
        bootstrap_servers="kafka:9092",
        topic="ran-combined-metrics",
        group_id="test-group",
    )

    assert consumer.is_connected is False
