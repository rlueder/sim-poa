from __future__ import annotations

from pathlib import Path

import osmium
import pytest
from shapely.geometry import box

from sim_poa.network.clip import clip


def _node(writer: osmium.SimpleWriter, node_id: int, lon: float, lat: float, **tags: str) -> None:
    writer.add_node(osmium.osm.mutable.Node(id=node_id, location=(lon, lat), tags=tags))


def _way(writer: osmium.SimpleWriter, way_id: int, nodes: list[int], **tags: str) -> None:
    writer.add_way(osmium.osm.mutable.Way(id=way_id, nodes=nodes, tags=tags))


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "extrato.osm.pbf"
    writer = osmium.SimpleWriter(str(path))
    _node(writer, 1, -51.20, -30.03, highway="traffic_signals")
    _node(writer, 2, -51.19, -30.03)
    _node(writer, 3, -51.10, -30.03)  # fora da área
    _node(writer, 4, -51.09, -30.03)  # fora da área
    _node(writer, 5, -51.20, -30.02)
    _node(writer, 6, -51.20, -30.04)
    # Avenida que sai da área: entra inteira, até o nó 3.
    _way(writer, 10, [1, 2, 3], highway="primary", name="Av. Teste")
    # Via inteiramente fora: não entra.
    _way(writer, 11, [3, 4], highway="residential")
    # Caminho de pedestre dentro da área: classe fora da rede.
    _way(writer, 12, [1, 5], highway="footway")
    # Rua dentro da área.
    _way(writer, 13, [6, 1], highway="residential")
    writer.add_relation(
        osmium.osm.mutable.Relation(
            id=100,
            members=[("w", 13, "from"), ("n", 1, "via"), ("w", 10, "to")],
            tags={"type": "restriction", "restriction": "no_left_turn"},
        )
    )
    writer.add_relation(
        osmium.osm.mutable.Relation(
            id=101,
            members=[("w", 11, "from"), ("n", 3, "via"), ("w", 10, "to")],
            tags={"type": "restriction", "restriction": "no_u_turn"},
        )
    )
    writer.close()
    return path


def test_clip_keeps_roads_touching_the_area_with_their_nodes(source: Path, tmp_path: Path) -> None:
    target = tmp_path / "recorte.osm"
    summary = clip(source, box(-51.25, -30.10, -51.15, -30.00), target)
    assert (summary.ways, summary.restrictions, summary.signals) == (2, 1, 1)

    ways, nodes, relations = set(), set(), set()
    for obj in osmium.FileProcessor(str(target)):
        if isinstance(obj, osmium.osm.Way):
            ways.add(obj.id)
        elif isinstance(obj, osmium.osm.Node):
            nodes.add(obj.id)
        else:
            relations.add(obj.id)
    assert ways == {10, 13}
    # O nó 3, fora da área, entra porque a avenida que sai da área termina nele.
    assert nodes == {1, 2, 3, 6}
    # A restrição que cita a via de fora não entra.
    assert relations == {100}


def test_clip_overwrites_a_previous_output(source: Path, tmp_path: Path) -> None:
    target = tmp_path / "recorte.osm"
    target.write_text("antigo")
    clip(source, box(-51.25, -30.10, -51.15, -30.00), target)
    assert target.read_text().startswith("<?xml")
