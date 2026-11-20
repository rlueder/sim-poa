from __future__ import annotations

import csv
import datetime as dt
import io
import zipfile
from pathlib import Path

import pytest

from sim_poa.network.buses import complete_feed, drop_holds, import_buses, run_day
from sim_poa.network.convert import netconvert, write_typemap
from sim_poa.network.speeds import default_speeds_kmh

WEDNESDAY = dt.date(2025, 10, 29)
FIXTURE = Path(__file__).parent / "fixtures" / "cruzamento.osm.xml"

FILES = {
    "agency.txt": (
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "1,Teste,https://exemplo.test,America/Sao_Paulo\n"
    ),
    "routes.txt": (
        "route_id,agency_id,route_short_name,route_long_name,route_type\nL1,1,L1,Linha de teste,3\n"
    ),
    "calendar.txt": (
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "UTIL,1,1,1,1,1,0,0,20250901,20251231\n"
        "DOM,0,0,0,0,0,0,1,20250901,20251231\n"
    ),
    "calendar_dates.txt": "service_id,date,exception_type\n",
    "trips.txt": "route_id,service_id,trip_id\nL1,UTIL,T1\nL1,DOM,T2\n",
    # Como no GTFS de Porto Alegre: horário só nos pontos de controle.
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,07:00:00,07:00:00,A,1\n"
        "T1,,,B,2\n"
        "T1,07:10:00,07:10:00,C,3\n"
        "T2,08:00:00,08:00:00,A,1\n"
        "T2,08:10:00,08:10:00,C,2\n"
    ),
    # Paradas sobre a Rua de Teste do cruzamento sintético (lat -30.03).
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "A,Parada A,-30.03001,-51.2295\n"
        "B,Parada B,-30.03001,-51.2280\n"
        "C,Parada C,-30.03001,-51.2265\n"
    ),
}


@pytest.fixture
def feed(tmp_path: Path) -> Path:
    path = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(path, "w") as out:
        for name, text in FILES.items():
            out.writestr(name, text)
    return path


def _rows(path: Path, name: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as opened:
        return list(csv.DictReader(io.TextIOWrapper(opened.open(name), "utf-8")))


def test_complete_feed_fills_times_and_keeps_the_day(feed: Path, tmp_path: Path) -> None:
    target = tmp_path / "dia.zip"
    assert complete_feed(feed, target, WEDNESDAY) == 1
    assert [r["trip_id"] for r in _rows(target, "trips.txt")] == ["T1"]
    times = _rows(target, "stop_times.txt")
    assert [(r["stop_id"], r["arrival_time"], r["departure_time"]) for r in times] == [
        ("A", "07:00:00", "07:00:00"),
        ("B", "07:05:00", "07:05:00"),
        ("C", "07:10:00", "07:10:00"),
    ]
    assert _rows(target, "stops.txt") == _rows(feed, "stops.txt")


def test_complete_feed_is_byte_for_byte_repeatable(feed: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "1.zip", tmp_path / "2.zip"
    complete_feed(feed, first, WEDNESDAY)
    complete_feed(feed, second, WEDNESDAY)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.sumo
def test_import_buses_places_stops_and_reuses_the_result(feed: Path, tmp_path: Path) -> None:
    typemap = write_typemap(tmp_path / "tipos.typ.xml", default_speeds_kmh())
    net = netconvert(FIXTURE, typemap, tmp_path / "cruzamento.net.xml.gz").net
    day_feed = tmp_path / "dia.zip"
    complete_feed(feed, day_feed, WEDNESDAY)

    result = import_buses(net, day_feed, WEDNESDAY, tmp_path / "onibus")
    assert result.vehicles == 1
    assert result.lines == 1
    assert result.bus_stops == 3

    # Mesma rede e mesmo GTFS: lê o resultado salvo, sem rodar de novo.
    result.routes.write_text(result.routes.read_text() + "<!-- marcador -->\n")
    again = import_buses(net, day_feed, WEDNESDAY, tmp_path / "onibus")
    assert "<!-- marcador -->" in again.routes.read_text()

    # Um ônibus, sem carros: chega sem teletransporte.
    day = run_day(net, again)
    assert (day["inserted"], day["teleports"]) == (1, 0)


def test_drop_holds_keeps_stops_and_departures(tmp_path: Path) -> None:
    routes = tmp_path / "onibus.rou.xml"
    routes.write_text(
        '<routes><route id="r" edges="a b"><stop busStop="s1" duration="10" until="0"/>'
        '<stop busStop="s2" duration="10" until="42.5"/></route>'
        '<vehicle id="v" route="r" depart="25200"/></routes>'
    )
    assert drop_holds(routes) == 2
    text = routes.read_text()
    assert "until" not in text
    assert text.count('duration="10"') == 2
    assert 'depart="25200"' in text
