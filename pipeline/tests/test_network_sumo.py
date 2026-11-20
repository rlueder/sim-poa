"""Conversão e conferências da rede sobre o cruzamento sintético, com os binários do SUMO."""

from __future__ import annotations

from pathlib import Path

import pytest

from sim_poa.network import checks
from sim_poa.network.convert import netconvert, set_signals, write_typemap
from sim_poa.network.speeds import default_speeds_kmh

FIXTURE = Path(__file__).parent / "fixtures" / "cruzamento.osm.xml"

pytestmark = pytest.mark.sumo


@pytest.fixture
def network(tmp_path: Path) -> Path:
    # Sem `maxspeed` na travessa, para a velocidade vir do typemap.
    osm = tmp_path / "cruzamento.osm.xml"
    osm.write_text(
        FIXTURE.read_text(encoding="utf-8").replace('<tag k="maxspeed" v="40"/>', ""),
        encoding="utf-8",
    )
    typemap = write_typemap(tmp_path / "tipos.typ.xml", default_speeds_kmh())
    return netconvert(osm, typemap, tmp_path / "cruzamento.net.xml.gz").net


def test_speeds_come_from_osm_or_from_the_traffic_code(network: Path) -> None:
    edges = checks.edge_table(checks.load_net(network)).set_index("name")
    assert set(edges.loc[["Rua de Teste"], "speed_kmh"]) == {50.0}
    # Travessa é `tertiary`: coletora, 40 km/h pelo art. 61 do CTB.
    assert set(edges.loc[["Travessa de Teste"], "speed_kmh"]) == {40.0}


def test_routes_and_signal_changes_on_a_small_network(network: Path, tmp_path: Path) -> None:
    net = checks.load_net(network)
    edges = checks.edge_table(net)
    one_way = edges[edges["name"].eq("Travessa de Teste")]["edge"].tolist()
    trips = tmp_path / "t.trips.xml"
    checks.write_trips(
        trips, [("ok", one_way[0], one_way[-1]), ("contramao", one_way[-1], one_way[0])]
    )
    routed = checks.route(network, trips, tmp_path / "t.rou.xml")
    assert set(routed) == {"ok"}

    centre = next(n for n in checks.junctions(net)["node"] if n == "2")
    signalled = set_signals(network, tmp_path / "com_semaforo.net.xml.gz", [centre], [])
    signals = checks.network_signals(checks.load_net(signalled))
    assert signals["node"].tolist() == ["2"]
