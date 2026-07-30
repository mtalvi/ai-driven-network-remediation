from ran_anomaly_detector.csv_mapper import parse_csv_records

HEADER = (
    "cell_id,max_capacity,lat,lon,area_type,city,band,frequency,datetime,"
    "ues_usage,rsrp,rsrq,sinr,throughput_mbps,latency_ms"
)


def _row(
    cell_id=42,
    max_capacity=100,
    lat=33.05,
    lon=-96.8,
    area_type="industrial",
    city="Plano",
    band="Band 29",
    frequency="700",
    datetime_="2026-07-29T10:00:00Z",
    ues_usage=50,
    rsrp=-95.0,
    rsrq=-10.0,
    sinr=15.0,
    throughput_mbps=100.0,
    latency_ms=20.0,
) -> str:
    return (
        f"{cell_id},{max_capacity},{lat},{lon},{area_type},{city},{band},{frequency},"
        f"{datetime_},{ues_usage},{rsrp},{rsrq},{sinr},{throughput_mbps},{latency_ms}"
    )


def test_parses_valid_row_into_ran_kpi_record():
    csv_blob = "\n".join([HEADER, _row()])

    records = parse_csv_records(csv_blob)

    assert len(records) == 1
    record = records[0]
    assert record.cell.cell_id == 42
    assert record.cell.max_capacity == 100
    assert record.cell.lat == 33.05
    assert record.cell.lon == -96.8
    assert record.cell.area_type == "industrial"
    assert record.cell.city == "Plano"
    assert record.cell.bands == ["Band 29"]
    assert record.cell.adjacent_cells == []
    assert record.band == "Band 29"
    assert record.frequency == "700"
    assert record.ues_usage == 50
    assert record.rsrp == -95.0
    assert record.rsrq == -10.0
    assert record.sinr == 15.0
    assert record.throughput_mbps == 100.0
    assert record.latency_ms == 20.0
    assert record.datetime.year == 2026


def test_parses_multiple_rows_across_cells_and_bands():
    csv_blob = "\n".join(
        [
            HEADER,
            _row(cell_id=1, band="Band 29"),
            _row(cell_id=1, band="Band 66"),
            _row(cell_id=2, band="Band 29"),
        ]
    )

    records = parse_csv_records(csv_blob)

    assert len(records) == 3
    assert [(r.cell.cell_id, r.band) for r in records] == [(1, "Band 29"), (1, "Band 66"), (2, "Band 29")]


def test_skips_malformed_row_but_keeps_valid_ones():
    csv_blob = "\n".join(
        [
            HEADER,
            _row(cell_id=1),
            "not,a,valid,row,at,all",
            _row(cell_id=2, rsrp="not-a-number"),
            _row(cell_id=3),
        ]
    )

    records = parse_csv_records(csv_blob)

    assert [r.cell.cell_id for r in records] == [1, 3]


def test_missing_required_columns_returns_empty_list():
    csv_blob = "cell_id,band\n1,Band 29"

    records = parse_csv_records(csv_blob)

    assert records == []


def test_empty_csv_returns_empty_list():
    assert parse_csv_records("") == []
