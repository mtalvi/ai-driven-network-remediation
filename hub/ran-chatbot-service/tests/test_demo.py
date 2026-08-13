"""Unit tests for demo.py's CSV-building logic (no Kafka)."""

import csv
import io

from ran_chatbot_service.demo import CSV_COLUMNS, build_demo_csv


def _parse(csv_blob: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(csv_blob)))


class TestBuildDemoCsv:
    def test_low_signal_has_expected_header_and_cell(self):
        csv_blob, meta = build_demo_csv("low_signal")
        rows = _parse(csv_blob)

        assert meta == {"scenario": "low_signal", "cell_id": 9001, "band": "Band 71"}
        assert len(rows) == 1
        assert rows[0]["cell_id"] == "9001"
        assert rows[0]["band"] == "Band 71"
        assert rows[0]["city"] == "Demo City"
        assert csv_blob.splitlines()[0].split(",") == list(CSV_COLUMNS)

    def test_low_signal_only_breaches_the_low_rsrp_threshold(self):
        """Regression test: this scenario must fire exactly one anomaly type
        (LowRsrp) in the real detector, not also SinrDegradation/CellOutage."""
        csv_blob, meta = build_demo_csv("low_signal")
        row = _parse(csv_blob)[0]

        assert float(row["rsrp"]) < -110.0
        assert float(row["sinr"]) >= 0.0
        assert float(row["throughput_mbps"]) != 0.0
        assert meta["cell_id"] == 9001

    def test_cell_outage_breaches_all_cell_outage_thresholds(self):
        """Regression test: this scenario must satisfy every CellOutage
        condition (see telco_oran.domain.anomaly_detector) so it fires
        CellOutage + LowRsrp + SinrDegradation simultaneously."""
        csv_blob, meta = build_demo_csv("cell_outage")
        row = _parse(csv_blob)[0]

        assert meta == {"scenario": "cell_outage", "cell_id": 9002, "band": "Band 29"}
        assert int(row["ues_usage"]) == 0
        assert float(row["throughput_mbps"]) == 0.0
        assert float(row["sinr"]) <= -10.0
        assert float(row["rsrp"]) <= -120.0
        assert float(row["rsrq"]) <= -20.0

    def test_unknown_scenario_falls_back_to_default(self):
        csv_blob, meta = build_demo_csv("not-a-real-scenario")
        assert meta["scenario"] == "low_signal"
        assert meta["cell_id"] == 9001
        assert "9001" in csv_blob

    def test_case_and_whitespace_insensitive(self):
        _, meta = build_demo_csv("  Cell_Outage  ")
        assert meta["scenario"] == "cell_outage"

    def test_datetime_is_a_valid_fresh_iso_timestamp(self):
        from datetime import datetime

        csv_blob, _ = build_demo_csv("low_signal")
        row = _parse(csv_blob)[0]

        # Not asserting against wall-clock time (flaky under CI clock skew),
        # just that it's a well-formed ISO datetime csv_mapper can parse.
        datetime.fromisoformat(row["datetime"])
