"""In-memory rolling history of RAN KPI records, keyed by (cell_id, band)."""

from __future__ import annotations

from collections import deque

from telco_oran.domain.cell_band_metrics import CellBandMetrics
from telco_oran.domain.ran_kpi_record import RanKpiRecord

DEFAULT_HISTORY_SIZE = 10

CellBandKey = tuple[int, str]


class MetricsStore:
    """Keeps a bounded rolling window of KPI records per (cell_id, band).

    AnomalyDetector needs a short trailing history (last 3 readings) to catch
    trend-based anomalies like ThroughputDrop/UesSpikeOrDrop. Kafka delivers
    readings independently over time, so this store accumulates them in-process
    and rebuilds a CellBandMetrics aggregate on every new reading for a given key.
    """

    def __init__(self, history_size: int = DEFAULT_HISTORY_SIZE) -> None:
        if history_size < 1:
            raise ValueError("history_size must be >= 1")
        self._history_size = history_size
        self._windows: dict[CellBandKey, deque[RanKpiRecord]] = {}

    def update(self, record: RanKpiRecord) -> CellBandMetrics:
        """Add a new reading and return the refreshed CellBandMetrics aggregate."""
        key = self._key(record)
        window = self._windows.setdefault(key, deque(maxlen=self._history_size))
        window.append(record)
        return CellBandMetrics(cell=record.cell, band=record.band, records=list(window))

    def clear(self) -> None:
        self._windows.clear()

    @staticmethod
    def _key(record: RanKpiRecord) -> CellBandKey:
        return (record.cell.cell_id, record.band)
