"""Parse RAN KPI CSV records (as delivered on Kafka) into telco_oran domain objects."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from loguru import logger
from telco_oran.domain.cell import Cell
from telco_oran.domain.ran_kpi_record import RanKpiRecord

REQUIRED_COLUMNS = (
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


def parse_csv_records(raw_csv: str) -> list[RanKpiRecord]:
    """Parse a CSV blob (header + one or more data rows) into RanKpiRecord objects.

    Each row is self-contained: it carries both the KPI measurement fields and the
    (denormalized) static Cell fields for the cell it was measured on, since Kafka
    messages arrive independently with no shared join context.

    Malformed rows are skipped and logged rather than failing the whole message,
    since a single bad reading shouldn't block the rest of the batch.
    """
    records: list[RanKpiRecord] = []

    reader = csv.DictReader(io.StringIO(raw_csv))
    if reader.fieldnames is None:
        logger.warning("Empty RAN metrics CSV message, nothing to parse")
        return records

    missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
    if missing:
        logger.warning("RAN metrics CSV missing required columns {}, skipping message", missing)
        return records

    for line_num, row in enumerate(reader, start=2):  # header occupies line 1
        record = _parse_row(row, line_num)
        if record is not None:
            records.append(record)

    return records


def _parse_row(row: dict[str, str], line_num: int) -> RanKpiRecord | None:
    try:
        band = row["band"].strip()
        cell = Cell(
            cell_id=int(row["cell_id"]),
            max_capacity=int(row["max_capacity"]),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            bands=[band],
            area_type=row["area_type"].strip(),
            city=row["city"].strip(),
            adjacent_cells=[],
        )
        return RanKpiRecord(
            cell=cell,
            datetime=_parse_datetime(row["datetime"]),
            band=band,
            frequency=row["frequency"].strip(),
            ues_usage=int(row["ues_usage"]),
            rsrp=float(row["rsrp"]),
            rsrq=float(row["rsrq"]),
            sinr=float(row["sinr"]),
            throughput_mbps=float(row["throughput_mbps"]),
            latency_ms=float(row["latency_ms"]),
        )
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("Skipping malformed RAN metrics CSV row {}: {}", line_num, exc)
        return None


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
