from dataclasses import dataclass
from datetime import datetime  # noqa: F401 -- used below as the `datetime` field's type

from telco_oran.domain.cell import Cell


@dataclass
class RanKpiRecord:
    """A single RAN KPI measurement snapshot for a cell on a specific frequency band."""

    cell: Cell
    # NOTE: field name intentionally matches the imported `datetime` type. Static linters
    # (flake8/pyflakes F401) misreport the import above as unused because of this — it is
    # used, as this field's annotation. Do NOT remove the import: without it, this class
    # fails to even be defined (NameError) on Python <3.14, since annotations are evaluated
    # eagerly and the field name shadows the type name. See test_domain_type_hints.py.
    datetime: datetime
    band: str
    frequency: str
    ues_usage: int
    rsrp: float
    rsrq: float
    sinr: float
    throughput_mbps: float
    latency_ms: float
