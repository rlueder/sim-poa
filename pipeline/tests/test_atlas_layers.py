"""Controladores, ônibus, oferta, sinistros e GPS, com entradas sintéticas."""

from __future__ import annotations

import datetime as dt
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from sim_poa.atlas import bus_gps, cameras, crashes, supply, transit

# ── Controladores ─────────────────────────────────────────────────────────


def test_camera_line_with_gaps_and_thousands() -> None:
    row = cameras.parse_line(
        "Av. Bento Goncalves 4021 - CB 13.731 15.627 16.739 17.867 - - - "
        "16.788 17.340 17.186 17.554 952",
        "controlador",
        2025,
    )
    assert row is not None
    assert (row.label, row.direction) == ("Av. Bento Goncalves 4021 - CB", "CB")
    assert row.values[:5] == [13731, 15627, 16739, 17867, None]
    assert row.values[-1] == 952


def test_camera_line_keeps_note_after_direction() -> None:
    row = cameras.parse_line(
        "Av. Benjamin Constant 415 - BC (Corredor Onibus) " + " ".join(["1.000"] * 12),
        "redutor",
        2024,
    )
    assert row is not None and row.direction == "BC"
    assert cameras.street_address(row.label) == "Av. Benjamin Constant 415"


@pytest.mark.parametrize(
    "line",
    [
        "Local/mês Janeiro Fevereiro Março",
        "Dia semana típico: terça, quarta e quinta",
        "Av. X 10 - BC 1.000 2.000",
    ],
)
def test_non_data_lines_are_rejected(line: str) -> None:
    assert cameras.parse_line(line, "controlador", 2025) is None


def test_label_key_matches_report_and_registry_spellings() -> None:
    assert cameras.label_key("Av. Bento Goncalves df 8083 - BC") == cameras.label_key(
        "Av. Bento Gonçalves 8083 - BC"
    )
    assert cameras.label_key(
        "Av. Benjamin Constant 415 - BC (Corredor Onibus)"
    ) == cameras.label_key("Av. Benjamin Constant 415 - BC")


def test_report_kind_and_year_come_from_the_file_name() -> None:
    assert cameras.kind_of("2025FluxoDiaTipicoRedutoresEletronicosVelocidadeMes.pdf") == "redutor"
    assert (
        cameras.kind_of("2025FluxoDiaTipicoControlaroresEletronicosVelocidadeMes.pdf")
        == "controlador"
    )
    assert cameras.kind_of("2025FrotaCadastradaPortoAlegre.pdf") is None


# ── GTFS ──────────────────────────────────────────────────────────────────


def _feed(path: Path) -> Path:
    files = {
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "U,1,1,1,1,1,0,0,20251001,20251031\nS,0,0,0,0,0,1,0,20251001,20251031\n",
        "calendar_dates.txt": "service_id,date,exception_type\nU,20251015,2\nS,20251015,1\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,U,t1\nR1,U,t2\nR2,S,t3\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "t1,07:00:00,07:00:00,A,1\nt1,,,B,2\nt1,07:20:00,07:20:00,C,3\n"
        "t2,07:50:00,07:50:00,A,1\nt2,,,B,2\nt2,08:30:00,08:30:00,C,3\n"
        "t3,24:10:00,24:10:00,A,1\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Parada A,-30.0,-51.2\n"
        "B,Parada B,-30.01,-51.2\nC,Parada C,-30.02,-51.2\n",
    }
    with zipfile.ZipFile(path, "w") as feed:
        for name, body in files.items():
            feed.writestr(name, body)
    return path


def test_services_follow_calendar_and_exceptions(tmp_path: Path) -> None:
    with zipfile.ZipFile(_feed(tmp_path / "g.zip")) as feed:
        assert transit.active_services(feed, dt.date(2025, 10, 22)) == {"U"}
        # 15/10 é quarta, mas U foi suspenso e S acrescentado nesse dia.
        assert transit.active_services(feed, dt.date(2025, 10, 15)) == {"S"}
        assert transit.typical_weekday(feed).weekday() == 2


def test_stop_counts_use_interpolated_times(tmp_path: Path) -> None:
    with zipfile.ZipFile(_feed(tmp_path / "g.zip")) as feed:
        passes = transit.stop_passes(feed, dt.date(2025, 10, 22))
    by_stop = passes.groupby(["stop_id", "hour"])["trip_id"].nunique().to_dict()
    # t2 passa em B às 08:10 (meio caminho entre 07:50 e 08:30).
    assert by_stop == {("A", 7): 2, ("B", 7): 1, ("B", 8): 1, ("C", 7): 1, ("C", 8): 1}


# ── Camadas de oferta ─────────────────────────────────────────────────────


def _zip_layer(tmp_path: Path, name: str, frame: gpd.GeoDataFrame) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    frame.to_file(folder / f"{name}.shp")
    archive = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for file in folder.iterdir():
            z.write(file, file.name)
    return archive


def test_blue_zone_groups_spaces_by_block_face(tmp_path: Path) -> None:
    x, y = 480_000.0, 6_677_000.0
    spaces = gpd.GeoDataFrame(
        {
            "LOGRADO": ["AV. MAUA", "AV. MAUA", "AV. MAUA"],
            "NUMERAL": ["841", "841", "900"],
            "POSICAO": ["OPOSTO", "OPOSTO", "OPOSTO"],
            "TIPO": ["CONVENCIONAL", "CONVENCIONAL", "IDOSO"],
        },
        geometry=[
            LineString([(x, y), (x + 5, y)]),
            LineString([(x + 5, y), (x + 10, y)]),
            LineString([(x + 50, y), (x + 55, y)]),
        ],
        crs=31982,
    )
    blocks = supply.blue_zone(_zip_layer(tmp_path, "aae", spaces)).set_index("number")
    assert blocks.loc["841", "spaces"] == 2
    assert blocks.loc["841", "geometry"].geom_type == "LineString"
    assert blocks.loc["900", "kind"] == "IDOSO"


# ── Sinistros ─────────────────────────────────────────────────────────────


def test_crash_grid_counts_by_year_and_severity() -> None:
    frame = pd.DataFrame(
        {
            "year": [2021, 2021, 2022, 2022],
            "lat": [-30.03, -30.0300001, -30.03, None],
            "lon": [-51.2, -51.2000001, -51.2, None],
            "injury": [True, False, True, False],
            "severe": [False, False, True, False],
            "hour": [7, 8, 18, None],
        }
    )
    cells, summary = crashes.grid(frame)
    assert len(cells) == 1
    assert cells[0]["years"] == {"2021": [2, 1, 0], "2022": [1, 1, 1]}
    assert summary["without_coordinates"] == 1
    assert summary["by_year"]["2022"] == [2, 1, 1]
    assert summary["by_hour"][7] == 1


# ── GPS dos ônibus ────────────────────────────────────────────────────────


def test_bus_speeds_are_aggregated_per_segment_and_hour() -> None:
    x, y = 480_000.0, 6_677_000.0
    streets = gpd.GeoDataFrame(
        {"CDSEG": [1, 2], "NMIDELOG": ["BORGES DE MEDEIROS", "LONGE"]},
        geometry=[
            LineString([(x, y), (x + 200, y)]),
            LineString([(x, y + 500), (x + 200, y + 500)]),
        ],
        crs=31982,
    )
    speeds = [20.0] * 20 + [0.0] * 10 + [40.0] * 5
    points = gpd.GeoDataFrame(
        {"kmh": speeds, "hour": [8] * 30 + [9] * 5},
        geometry=[Point(x + i, y + 5) for i in range(35)],
        crs=31982,
    )
    segments, summary = bus_gps.speeds_by_segment(points, streets)
    assert summary["snapped"] == 35 and summary["segments"] == 1
    hours = segments.iloc[0]["hours"]
    # Às 9h há só 5 pontos, abaixo do mínimo: a hora não é publicada.
    assert set(hours) == {"8"}
    median, stopped, count = hours["8"]
    assert (median, stopped, count) == (20.0, pytest.approx(0.333, abs=0.001), 30)
