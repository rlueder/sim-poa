from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import cast

import openpyxl
import pandas as pd
import pytest

from sim_poa.atlas import edom
from sim_poa.atlas.excel import as_code, as_number, excel_serial, minutes_of_day

HEADER = [
    "ZONA",
    "FE_MOT",
    "ID_MOR",
    "ID_DESL",
    "MOTIVO.DA.VIAGEM",
    "ZONA_O",
    "HOR_O",
    "ZONA_D",
    "HOR_D",
    "MODO_PRINC",
    "FE_IDADE_AJ",
]


def _workbook(tmp_path: Path, rows: list[list[object]]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = edom.SHEET_TRIPS
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    path = tmp_path / "edom.xlsx"
    wb.save(path)
    return path


def _trip(
    trip: str, o: int, d: int, dep: str, arr: str, mode: object, weight: float, purpose: str
) -> list[object]:
    h1, m1 = map(int, dep.split(":"))
    h2, m2 = map(int, arr.split(":"))
    return [o, 1, f"p{trip}", trip, purpose, o, dt.time(h1, m1), d, dt.time(h2, m2), mode, weight]


def test_excel_serial_handles_the_1900_leap_year_bug() -> None:
    # Na planilha real, o código de modo 10 aparece como 10/01/1900.
    assert excel_serial(dt.datetime(1900, 1, 10)) == 10
    assert excel_serial(dt.datetime(1900, 2, 14)) == 45
    assert excel_serial(dt.datetime(1900, 3, 1)) == 61
    assert excel_serial(dt.datetime(2023, 10, 23)) == 45222


@pytest.mark.parametrize(
    ("value", "expected"),
    [(dt.datetime(1900, 1, 16), 16.0), ("12,5", 12.5), (" NA ", None), ("--", None), (True, None)],
)
def test_as_number(value: object, expected: float | None) -> None:
    assert as_number(value) == expected


def test_as_code_rejects_fractions() -> None:
    assert as_code("10") == 10
    with pytest.raises(ValueError, match="não inteiro"):
        as_code(10.5)


def test_minutes_of_day() -> None:
    assert minutes_of_day(dt.time(7, 45)) == 465
    assert minutes_of_day("17:30:00") == 1050
    assert minutes_of_day(None) is None


def test_read_trips_normalises_codes_times_and_overnight(tmp_path: Path) -> None:
    path = _workbook(
        tmp_path,
        [
            _trip("a", 1, 2, "07:45", "08:30", dt.datetime(1900, 1, 10), 34.0, "Trabalho"),
            _trip("b", 2, 1, "23:30", "00:20", 16, 10.0, "OUTROS"),
            [None] * len(HEADER),
        ],
    )
    trips = edom.read_trips(path)
    assert list(trips["trip_id"]) == ["a", "b"]
    assert list(trips["mode"]) == [10, 16]
    assert list(trips["purpose"]) == ["TRABALHO", "OUTROS"]
    assert list(trips["arrive_min"]) == [510, 24 * 60 + 20]


def test_read_trips_fails_on_unknown_mode_and_missing_columns(tmp_path: Path) -> None:
    path = _workbook(tmp_path, [_trip("a", 1, 2, "07:00", "07:30", 99, 1.0, "OUTROS")])
    with pytest.raises(ValueError, match="fora do dicionário"):
        edom.read_trips(path)

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = edom.SHEET_TRIPS
    ws.append(["ID_DESL", "ZONA_O"])
    broken = tmp_path / "quebrado.xlsx"
    wb.save(broken)
    with pytest.raises(ValueError, match="colunas ausentes"):
        edom.read_trips(broken)


def _frame(rows: list[tuple[int, int, int, int, int, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["zone_o", "zone_d", "depart_min", "arrive_min", "mode", "weight"]
    ).assign(purpose="OUTROS")


def test_peak_by_arrival_uses_arrival_time_and_motorised_filter() -> None:
    trips = _frame(
        [
            (1, 2, 400, 430, 10, 100.0),  # chega 07:10, motorizada
            (1, 2, 410, 470, 16, 500.0),  # chega 07:50, a pé
            (1, 2, 420, 480, 2, 80.0),  # chega 08:00, motorizada
            (1, 2, 470, 500, 10, 60.0),  # chega 08:20
        ]
    )
    start, total = edom.peak_by_arrival(trips, motorized=True, first_start=360, last_start=480)
    assert (start, total) == (420, 180.0)  # 07:00-08:00: chegadas às 07:10 e às 08:00
    start, total = edom.peak_by_arrival(trips, motorized=False, first_start=360, last_start=480)
    assert total == 680.0


def test_desire_lines_drop_thin_pairs_and_intrazonal_trips() -> None:
    thick = [(1, 2, 400, 430, 10, 10.0)] * edom.MIN_RECORDS_PER_PAIR
    thin = [(2, 3, 400, 430, 2, 1000.0)] * (edom.MIN_RECORDS_PER_PAIR - 1)
    intra = [(1, 1, 400, 430, 16, 50.0)] * 10
    lines = edom.desire_lines(_frame(thick + thin + intra), {1: (0, 0), 2: (1, 1), 3: (2, 2)})
    assert list(zip(lines["zone_o"], lines["zone_d"], strict=True)) == [(1, 2)]
    assert float(lines.iloc[0]["trips"]) == 50.0


def test_departure_profile_is_a_sliding_hour() -> None:
    trips = _frame([(1, 2, 7 * 60, 7 * 60 + 30, 10, 30.0), (1, 2, 7 * 60 + 30, 8 * 60, 16, 10.0)])
    profile = edom.departure_profile(trips)
    assert profile.loc[6 * 60 + 30, "OUTROS"] == 30  # 06:30-07:30 pega só a das 07:00
    assert profile.loc[7 * 60, "OUTROS"] == 40
    assert profile.loc[7 * 60 + 45, "OUTROS"] == 0
    assert len(profile) == 96


def test_zone_summary_splits_hours_and_groups() -> None:
    trips = _frame([(1, 2, 7 * 60, 7 * 60 + 30, 10, 30.0), (1, 2, 8 * 60, 8 * 60 + 5, 16, 10.0)])
    summary = edom.zone_summary(trips).set_index("zone")
    assert summary.loc[1, "produced"] == 40
    assert summary.loc[2, "attracted"] == 40
    by_hour = cast(list[float], summary.loc[1, "produced_by_hour"])
    assert len(by_hour) == 24
    assert by_hour[7] == 30 and by_hour[8] == 10
    assert sum(by_hour) == summary.loc[1, "produced"]
    assert summary.loc[1, "mode_share"] == {"individual": 0.75, "ativo": 0.25}


def _zones_zip(tmp_path: Path) -> Path:
    """Três polígonos como no ZONAS_OD.zip: zonas 1 e 10 e uma do resto do estado."""
    import zipfile

    import geopandas as gpd
    from shapely.geometry import box

    frame = gpd.GeoDataFrame(
        {"ZT": ["1", "10", "E4300001"], "CD_MUN": ["4314902", "4314902", "4300001"]},
        geometry=[
            box(-51.25, -30.05, -51.20, -30.00),
            box(-51.20, -30.05, -51.15, -30.00),
            box(-51.15, -30.05, -51.10, -30.00),
        ],
        crs=4326,
    ).to_crs(31982)
    folder = tmp_path / "zonas"
    folder.mkdir()
    frame.to_file(folder / "ZONAS_OD.shp")
    target = tmp_path / "ZONAS_OD.zip"
    with zipfile.ZipFile(target, "w") as out:
        for part in folder.iterdir():
            out.write(part, part.name)
    return target


def test_locate_trips_uses_coordinates_not_survey_codes(tmp_path: Path) -> None:
    trips = pd.DataFrame(
        {
            # Os códigos da planilha estão "trocados" de propósito: 2 é a zona 10.
            "survey_zone_o": [1, 2, 2],
            "survey_zone_d": [2, 1, 1],
            "lat_o": [-30.02, -30.02, -30.02],
            "lon_o": [-51.22, -51.17, -51.17],
            "lat_d": [-30.02, -30.02, -30.02],
            "lon_d": [-51.17, -51.12, -51.30],
        }
    )
    located = edom.locate_trips(trips, _zones_zip(tmp_path))
    assert located["zone_o"].tolist() == [1, 10, 10]
    # Zona sem número (resto do estado) e ponto fora de todos os polígonos ficam sem zona.
    assert located["zone_d"].iloc[0] == 10
    assert pd.isna(located["zone_d"].iloc[1])
    assert pd.isna(located["zone_d"].iloc[2])


def test_read_trips_keeps_coordinates_and_survey_codes(tmp_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = edom.SHEET_TRIPS
    ws.append([*HEADER, "LAT_O", "LONG_O", "LAT_D", "LONG_D"])
    ws.append(
        [*_trip("1", 2, 3, "07:00", "07:30", 10, 5.0, "TRABALHO"), -30.02, -51.17, -30.03, -51.22]
    )
    path = tmp_path / "edom.xlsx"
    wb.save(path)
    trips = edom.read_trips(path)
    row = trips.iloc[0]
    assert (row["survey_zone_o"], row["survey_zone_d"]) == (2, 3)
    assert (row["lat_o"], row["lon_o"], row["lat_d"], row["lon_d"]) == (
        -30.02,
        -51.17,
        -30.03,
        -51.22,
    )
    assert "zone_o" not in trips.columns
