from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, box

from sim_poa.network import checks
from sim_poa.network.build import signal_frame, site_roads
from sim_poa.network.clip import ROAD_CLASSES
from sim_poa.network.convert import ConvertResult
from sim_poa.network.speeds import CTB_URBAN_KMH, OSM_TO_CTB, default_speeds_kmh

# Perto do Centro de Porto Alegre: 0,0001° dá uns 10 m nos dois eixos.
CITY = box(-51.20, -30.05, -51.10, -29.95)


def _edges(*rows: tuple[str, str, str, int, list[tuple[float, float]]]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        [
            {
                "edge": edge,
                "name": name,
                "highway": highway,
                "lanes": lanes,
                "speed_kmh": 50.0,
                "length_m": 100.0,
                "passenger": True,
                "geometry": LineString(coords),
            }
            for edge, name, highway, lanes, coords in rows
        ],
        geometry="geometry",
        crs=4326,
    )


def _points(rows: list[tuple[str, float, float]], column: str) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {column: [r[0] for r in rows]},
        geometry=[Point(r[1], r[2]) for r in rows],
        crs=4326,
    )


def test_every_network_road_class_has_a_traffic_code_speed() -> None:
    assert set(OSM_TO_CTB) == ROAD_CLASSES
    speeds = default_speeds_kmh()
    assert speeds["primary"] == CTB_URBAN_KMH["arterial"] == 60
    assert speeds["residential"] == 30
    assert speeds["motorway"] == 80
    assert speeds["tertiary"] == 40


def test_warning_kinds_fold_identifiers() -> None:
    result = ConvertResult(
        net=None,  # type: ignore[arg-type]
        warnings=[
            "Not joining junctions 12,34 (parallel incoming -56#1,78).",
            "Not joining junctions 9,10 (parallel incoming 11,-12#3).",
            "Not joining junctions 1,2,3,4 (parallel incoming 5,6).",
            "Ignoring restriction relation '123'.",
        ],
    )
    assert result.warning_kinds() == {
        "Not joining junctions N,… (parallel incoming N,…).": 3,
        "Ignoring restriction relation '…'.": 1,
    }


def test_gates_are_major_roads_crossing_the_boundary_once() -> None:
    edges = _edges(
        ("in", "Av. Entrada", "primary", 2, [(-51.25, -30.0), (-51.15, -30.0)]),
        ("out", "Av. Entrada", "primary", 2, [(-51.15, -30.0), (-51.25, -30.0)]),
        ("inside", "Av. Dentro", "primary", 2, [(-51.18, -30.0), (-51.15, -30.0)]),
        ("local", "Rua Local", "residential", 1, [(-51.25, -30.01), (-51.15, -30.01)]),
        ("through", "Av. Passa", "trunk", 2, [(-51.25, -30.02), (-51.05, -30.02)]),
    )
    gates = checks.gates(edges, CITY)
    assert dict(zip(gates["edge"], gates["direction"], strict=True)) == {
        "in": "entrada",
        "out": "saída",
    }


def test_zone_anchor_is_the_edge_nearest_the_zone_point() -> None:
    zones = gpd.GeoDataFrame(
        {"zone": [1, 2]},
        geometry=[box(-51.20, -30.05, -51.15, -30.00), box(-51.15, -30.05, -51.10, -30.00)],
        crs=4326,
    )
    edges = _edges(
        ("near", "", "residential", 1, [(-51.176, -30.025), (-51.174, -30.025)]),
        ("far", "", "residential", 1, [(-51.199, -30.049), (-51.198, -30.049)]),
    )
    anchors = checks.zone_anchors(edges, zones).set_index("zone")
    assert anchors.loc[1, "edges"] == 2
    assert anchors.loc[1, "anchor"] == "near"
    assert anchors.loc[2, "edges"] == 0
    assert anchors["anchor"].isna().tolist() == [False, True]


def test_signals_match_within_thirty_metres() -> None:
    network = _points([("a", -51.1500, -30.0000), ("b", -51.1400, -30.0000)], "node")
    inventory = _points([("x", -51.1501, -30.0001), ("y", -51.1300, -30.0000)], "code")
    comparison = checks.compare_signals(network, inventory)
    assert comparison.network["matched"].tolist() == [True, False]
    assert comparison.inventory["matched"].tolist() == [True, False]
    assert comparison.counts["inventario_sem_semaforo_na_rede"] == 1


def test_signal_corrections_follow_the_inventory_only_where_it_is_clear() -> None:
    network = _points(
        [
            ("ok", -51.1500, -30.0000),  # casa com o cadastro
            ("stray", -51.1400, -30.0000),  # nenhum registro a 80 m: desliga
            ("approach", -51.1300, -30.0000),  # registro a uns 50 m: fica
            ("outside", -51.0500, -30.0000),  # fora do município: fica
        ],
        "node",
    )
    inventory = _points(
        [
            ("x", -51.1500, -30.0000),
            ("y", -51.1305, -30.0000),
            ("needs_node", -51.1600, -30.0000),
            ("no_node", -51.1700, -30.0000),
        ],
        "kind",
    )
    comparison = checks.compare_signals(network, inventory)
    nodes = gpd.GeoDataFrame(
        {"node": ["j1", "ok"], "type": ["priority", "traffic_light"]},
        geometry=[Point(-51.1601, -30.0000), Point(-51.1500, -30.0000)],
        crs=4326,
    )
    fixes = checks.signal_corrections(comparison, nodes, CITY)
    assert fixes.add == ["j1"]
    assert fixes.remove == ["stray"]
    assert fixes.unplaced["kind"].tolist() == ["y", "no_node"]


def test_cheapest_path_takes_the_lowest_total_cost() -> None:
    successors = {"a": ["b", "c"], "b": ["d"], "c": ["d"]}
    cost = {"a": 1.0, "b": 5.0, "c": 2.0, "d": 1.0, "e": 1.0}
    assert checks.cheapest_path(successors, cost, "a", "d") == ["a", "c", "d"]
    assert checks.cheapest_path(successors, cost, "a", "a") == ["a"]
    assert checks.cheapest_path(successors, cost, "a", "e") is None


def test_parse_statistics_reads_the_sumo_summary() -> None:
    output = """
Statistics (avg of 3598):
 RouteLength: 5123.45
Vehicles:
 Inserted: 3600
 Running: 2
 Waiting: 0
Teleports: 4 (Jam: 3, Yield: 1)
"""
    stats = checks.parse_statistics(output)
    assert stats["inserted"] == 3600
    assert stats["running"] == 2
    assert stats["teleports"] == 4
    assert stats["teleport_share"] == pytest.approx(4 / 3600)


def test_parse_statistics_without_teleports() -> None:
    stats = checks.parse_statistics("Vehicles:\n Inserted: 10\n Running: 0\n Waiting: 0\n")
    assert stats["teleports"] == 0
    assert stats["teleport_share"] == 0


def test_site_roads_keeps_one_direction_and_merges_runs() -> None:
    edges = _edges(
        ("1", "Av. A", "primary", 2, [(-51.15, -30.0), (-51.14, -30.0)]),
        ("-1", "Av. A", "primary", 3, [(-51.14, -30.0), (-51.15, -30.0)]),
        ("2", "Av. A", "primary", 2, [(-51.14, -30.0), (-51.13, -30.0)]),
        ("-2", "Av. A", "primary", 3, [(-51.13, -30.0), (-51.14, -30.0)]),
        ("3", "Rua B", "residential", 1, [(-51.14, -30.0), (-51.14, -29.99)]),
    )
    roads = site_roads(edges)
    assert len(roads) == 1
    row = roads.iloc[0]
    assert (row["name"], row["lanes"]) == ("Av. A", 3)
    assert row.geometry.geom_type == "LineString"
    assert row.geometry.length == pytest.approx(0.02, rel=1e-3)


def test_signal_frame_labels_each_signal() -> None:
    inventory = _points(
        [("x", -51.1500, -30.0), ("y", -51.1600, -30.0), ("z", -51.1700, -30.0)], "code"
    ).assign(description="", kind="MISTO")
    before_net = _points(
        [("a", -51.1500, -30.0), ("gone", -51.1400, -30.0), ("far", -51.0500, -30.0)], "node"
    )
    after_net = _points(
        [("a", -51.1500, -30.0), ("new", -51.1600, -30.0), ("far", -51.0500, -30.0)], "node"
    )
    before = checks.compare_signals(before_net, inventory)
    after = checks.compare_signals(after_net, inventory)
    frame = signal_frame(before, after, ["gone"], CITY)
    assert dict(zip(frame["code"], frame["status"], strict=True)) == {
        "x": "na rede",
        "y": "ligado pelo cadastro",
        "z": "sem semáforo na rede",
        "far": "fora do município",
        "gone": "desligado",
    }


def test_run_tool_reports_the_tool_output_on_failure(tmp_path: Path) -> None:
    from sim_poa.network.sumo_env import ToolError, run_tool

    script = tmp_path / "ferramenta.py"
    script.write_text("import sys\nprint('sem rede', file=sys.stderr)\nsys.exit(3)\n")
    with pytest.raises(ToolError, match=r"(?s)ferramenta\.py falhou \(código 3\).*sem rede"):
        run_tool([sys.executable, str(script)])
