"""Regression guard for the domain model's dataclass type annotations.

A "style cleanup" commit once removed `from datetime import datetime` from
`ran_kpi_record.py` as an apparent unused import, since it's never referenced
as a plain expression outside of `datetime: datetime`. That broke the class
under Python <3.14 with a NameError at class-definition time (the field name
shadows the annotation lookup), while staying silent under Python 3.14+, where
PEP 649 defers annotation evaluation.

`typing.get_type_hints()` forces every annotation to resolve regardless of the
running Python version, so this test catches the same class of bug (an import
only used inside a type annotation getting stripped) independent of which
Python version CI happens to run under.
"""

import typing

from telco_oran.domain.cell import Cell
from telco_oran.domain.cell_band_metrics import CellBandMetrics
from telco_oran.domain.ran_kpi_record import RanKpiRecord

DOMAIN_DATACLASSES = (Cell, RanKpiRecord, CellBandMetrics)


def test_domain_dataclass_type_hints_resolve():
    for cls in DOMAIN_DATACLASSES:
        typing.get_type_hints(cls)


def test_ran_kpi_record_datetime_field_is_actual_datetime_type():
    from datetime import datetime

    hints = typing.get_type_hints(RanKpiRecord)
    assert hints["datetime"] is datetime
