"""Recorte do extrato do OpenStreetMap para a área da rede.

O extrato da Região Sul tem centenas de MB. Aqui ficam só as vias de interesse
que têm algum nó dentro do município (mais uma margem), os nós dessas vias e
as restrições de conversão entre elas, gravados em OSM XML, que é o que o
`netconvert` lê. Uma via que cruza a margem entra inteira, para as entradas da
cidade continuarem até depois da divisa.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import osmium
from shapely import prepared
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from sim_poa.atlas.edom import PORTO_ALEGRE_IBGE

METRIC_CRS = 31982
BUFFER_METRES = 2000.0

# Classes de via levadas para a rede. Ficam de fora `service` (estacionamentos,
# acessos a garagem), caminhos de pedestres e ciclovias; ônibus e carros não
# circulam nelas de forma que importe para o modelo da cidade.
ROAD_CLASSES = frozenset(
    {
        "motorway",
        "motorway_link",
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "unclassified",
        "residential",
        "living_street",
    }
)


@dataclass
class ClipSummary:
    ways: int
    nodes: int
    restrictions: int
    signals: int


def city_outline(zones_zip: Path) -> BaseGeometry:
    """Divisa do município como união das zonas da EDOM na cidade, em WGS 84.

    Usa o arquivo original: as zonas simplificadas do atlas deixam frestas entre
    vizinhas, e a união delas ganharia divisas falsas no meio da cidade.
    """
    zones = gpd.read_file(f"zip://{zones_zip}")
    city = zones[zones["CD_MUN"].eq(PORTO_ALEGRE_IBGE)]
    outline: BaseGeometry = city.to_crs(4326).union_all()
    return outline


def study_area(city: BaseGeometry, buffer_metres: float = BUFFER_METRES) -> BaseGeometry:
    """Município mais a margem, em WGS 84."""
    metric = gpd.GeoSeries([city], crs=4326).to_crs(METRIC_CRS)
    area: BaseGeometry = metric.buffer(buffer_metres).to_crs(4326).iloc[0]
    return area


def _wanted(tags: osmium.osm.TagList) -> bool:
    return tags.get("highway") in ROAD_CLASSES and tags.get("area") != "yes"


def clip(source: Path, area: BaseGeometry, target: Path) -> ClipSummary:
    """Grava em `target` (OSM XML) as vias de `ROAD_CLASSES` que tocam `area`."""
    inside = prepared.prep(area)
    min_lon, min_lat, max_lon, max_lat = area.bounds
    ways: set[int] = set()
    nodes: set[int] = set()

    # Primeira passada: com as coordenadas dos nós, escolhe as vias.
    # Os filtros só entregam ao Python as vias com `highway`. Os nós são lidos
    # mesmo assim, porque o cache de coordenadas precisa deles.
    first_pass = (
        osmium.FileProcessor(str(source), osmium.osm.NODE | osmium.osm.WAY)
        .with_locations()
        .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in first_pass:
        if not isinstance(way, osmium.osm.Way) or not _wanted(way.tags):
            continue
        touches = False
        for ref in way.nodes:
            location = ref.location
            if not location.valid():
                continue
            lon, lat = location.lon, location.lat
            if (
                min_lon <= lon <= max_lon
                and min_lat <= lat <= max_lat
                and inside.contains(Point(lon, lat))
            ):
                touches = True
                break
        if touches:
            ways.add(way.id)
            nodes.update(ref.ref for ref in way.nodes)

    # Segunda passada: grava nós, vias e restrições, nessa ordem.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    restrictions = signals = 0
    writer = osmium.SimpleWriter(str(target))
    try:
        for obj in osmium.FileProcessor(str(source)):
            if isinstance(obj, osmium.osm.Node):
                if obj.id in nodes:
                    writer.add_node(obj)
                    signals += obj.tags.get("highway") == "traffic_signals"
            elif isinstance(obj, osmium.osm.Way):
                if obj.id in ways:
                    writer.add_way(obj)
            elif isinstance(obj, osmium.osm.Relation) and obj.tags.get("type") == "restriction":
                members = [m for m in obj.members if m.type == "w"]
                if members and all(m.ref in ways for m in members):
                    writer.add_relation(obj)
                    restrictions += 1
    finally:
        writer.close()
    return ClipSummary(ways=len(ways), nodes=len(nodes), restrictions=restrictions, signals=signals)
