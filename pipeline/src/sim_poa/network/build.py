"""Montagem da rede viária do SUMO a partir de data/raw/ e conferência do resultado."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry.base import BaseGeometry

from sim_poa.atlas import edom, supply
from sim_poa.atlas.build import EDOM_DIR, EDOM_ZONES
from sim_poa.atlas.export import write_geojson, write_json
from sim_poa.network import checks
from sim_poa.network.clip import city_outline, clip, study_area
from sim_poa.network.convert import netconvert, set_signals, write_typemap
from sim_poa.network.speeds import default_speeds_kmh

OSM_DIR = "osm-geofabrik-sul"
LAYERS_DIR = "camadas-eptc"
SIGNALS_PATTERN = "_EPS_CadastroSemaforico_*.zip"
NET_FILE = "poa.net.xml.gz"

# Vias que o site mostra; as locais ficam de fora para o arquivo caber no orçamento.
SITE_ROAD_CLASSES = frozenset(
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
    }
)
MAX_TELEPORT_SHARE = 0.001
SITE_SIMPLIFY_METRES = 5.0


@dataclass
class NetworkReport:
    files: dict[str, int] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    checks_failed: list[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(self.files.values())


def _single(folder: Path, pattern: str) -> Path:
    """O arquivo mais recente do padrão.

    Os cadastros da EPTC levam a data no nome (`_EPS_CadastroSemaforico_20261021.zip`)
    e o extrato do OSM também (`sul-261119.osm.pbf`), então a ordem alfabética é a
    cronológica. O nome escolhido vai para o relatório.
    """
    found = sorted(folder.glob(pattern))
    if not found:
        raise FileNotFoundError(f"{pattern} ausente em {folder}; rode pnpm data:fetch")
    return found[-1]


def _step(name: str) -> float:
    print(f"── rede: {name}")
    return time.monotonic()


def site_roads(edges: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Vias principais para o mapa, num arquivo pequeno.

    Numa via de mão dupla o SUMO cria duas arestas com a mesma geometria
    (`X` e `-X`); fica uma, com o maior número de faixas entre os dois sentidos.
    Depois, trechos seguidos com o mesmo nome, classe, faixas e velocidade viram
    uma linha só.
    """
    roads = edges[edges["highway"].isin(SITE_ROAD_CLASSES) & edges["passenger"]]
    lanes = dict(zip(roads["edge"], roads["lanes"], strict=True))
    forward = roads[~(roads["edge"].str.startswith("-") & roads["edge"].str[1:].isin(lanes))]
    forward = forward.assign(
        lanes=[
            max(n, lanes.get(f"-{e}", 0))
            for e, n in zip(forward["edge"], forward["lanes"], strict=True)
        ]
    )
    keys = ["name", "highway", "lanes", "speed_kmh"]
    merged = (
        forward[[*keys, "geometry"]].to_crs(checks.METRIC_CRS).dissolve(by=keys, as_index=False)
    )
    merged["geometry"] = shapely.simplify(
        shapely.line_merge(merged.geometry.values), SITE_SIMPLIFY_METRES
    )
    return merged.to_crs(4326)


def signal_frame(
    before: checks.SignalComparison,
    after: checks.SignalComparison,
    removed: list[str],
    city: BaseGeometry,
) -> gpd.GeoDataFrame:
    """Semáforos do cadastro e os da rede sem registro, com a situação de cada um."""
    registry = after.inventory
    status = np.select(
        [before.inventory["matched"].to_numpy(), registry["matched"].to_numpy()],
        ["na rede", "ligado pelo cadastro"],
        default="sem semáforo na rede",
    )
    inventory = gpd.GeoDataFrame(
        {
            "source": "cadastro",
            "code": registry["code"],
            "description": registry["description"],
            "kind": registry["kind"],
            "status": status,
        },
        geometry=registry.geometry,
        crs=4326,
    )
    extra = after.network[~after.network["matched"]]
    dropped = before.network[before.network["node"].isin(removed)]
    network = gpd.GeoDataFrame(
        {
            "source": "rede",
            "code": pd.concat([extra["node"], dropped["node"]], ignore_index=True),
            "description": "",
            "kind": "",
            "status": np.concatenate(
                [
                    np.where(extra.within(city), "só na rede", "fora do município"),
                    np.full(len(dropped), "desligado"),
                ]
            ),
        },
        geometry=pd.concat([extra.geometry, dropped.geometry], ignore_index=True),
        crs=4326,
    )
    return gpd.GeoDataFrame(pd.concat([inventory, network], ignore_index=True), crs=4326)


def build(raw_dir: Path, derived_dir: Path, site_dir: Path, reports_dir: Path) -> NetworkReport:
    report = NetworkReport()
    summary = report.summary
    zones_zip = raw_dir / EDOM_DIR / EDOM_ZONES
    city = city_outline(zones_zip)

    started = _step("recorte do OSM")
    source = _single(raw_dir / OSM_DIR, "*.osm.pbf")
    clipped = clip(source, study_area(city), derived_dir / "recorte.osm")
    summary["osm"] = {
        "extract": source.name,
        "ways": clipped.ways,
        "nodes": clipped.nodes,
        "restrictions": clipped.restrictions,
        "signal_nodes": clipped.signals,
        "seconds": round(time.monotonic() - started),
    }

    started = _step("netconvert")
    typemap = write_typemap(derived_dir / "tipos.typ.xml", default_speeds_kmh())
    base = netconvert(derived_dir / "recorte.osm", typemap, derived_dir / "poa.base.net.xml.gz")
    summary["netconvert"] = {
        "warnings": len(base.warnings),
        "warning_kinds": base.warning_kinds(),
        "seconds": round(time.monotonic() - started),
    }

    _step("semáforos")
    inventory_file = _single(raw_dir / LAYERS_DIR, SIGNALS_PATTERN)
    inventory = supply.signals(inventory_file)
    base_net = checks.load_net(base.net)
    before = checks.compare_signals(checks.network_signals(base_net), inventory)
    fixes = checks.signal_corrections(before, checks.junctions(base_net), city)
    net_file = set_signals(base.net, derived_dir / NET_FILE, fixes.add, fixes.remove)
    net = checks.load_net(net_file)
    after = checks.compare_signals(checks.network_signals(net), inventory)
    summary["signals"] = {
        "inventory_file": inventory_file.name,
        "before": before.counts,
        "added": len(fixes.add),
        "removed": len(fixes.remove),
        "unplaced": len(fixes.unplaced),
        "unplaced_by_kind": fixes.unplaced["kind"].value_counts().to_dict(),
        "after": after.counts,
        "network_only_in_city": int((~after.network["matched"] & after.network.within(city)).sum()),
        "after_by_kind": {
            str(kind): {"matched": int(group["matched"].sum()), "total": len(group)}
            for kind, group in after.inventory.groupby("kind")
        },
    }

    _step("entradas da cidade e zonas")
    edges = checks.edge_table(net)
    gates = checks.gates(edges, city)
    zones = edom.read_zones(zones_zip, set())
    anchors = checks.zone_anchors(edges, zones[zones["in_city"]])
    empty = anchors.loc[anchors["edges"].eq(0), "zone"].tolist()
    summary["network"] = {
        "edges": len(edges),
        "drivable_edges": int(edges["passenger"].sum()),
        "drivable_km": round(float(edges.loc[edges["passenger"], "length_m"].sum()) / 1000),
        "junctions": len(net.getNodes()),
        "traffic_lights": len(net.getTrafficLights()),
    }
    summary["gates"] = gates.drop(columns="geometry").to_dict(orient="records")
    summary["zones"] = {
        "city_zones": len(anchors),
        "without_edges": empty,
        "fewest_edges": int(anchors["edges"].min()),
    }
    if empty:
        report.checks_failed.append("zonas sem arestas de carro")

    started = _step("conectividade entre zonas")
    missing = checks.reachability(net_file, anchors, derived_dir / "checks")
    pairs = len(anchors) * (len(anchors) - 1)
    summary["reachability"] = {
        "pairs": pairs,
        "without_route": len(missing),
        "examples": missing.head(20).to_dict(orient="records"),
        "seconds": round(time.monotonic() - started),
    }
    if len(missing):
        report.checks_failed.append("pares de zonas sem rota")

    _step("corredores")
    corridors = checks.corridor_free_flow(net, edges, city)
    summary["corridors"] = corridors.drop(columns="geometry").to_dict(orient="records")

    started = _step("teste mesoscópico")
    smoke = checks.smoke_test(net_file, derived_dir / "checks")
    smoke["seconds"] = round(time.monotonic() - started)
    summary["smoke_test"] = smoke
    share = smoke["teleport_share"]
    if share is None or share >= MAX_TELEPORT_SHARE:
        report.checks_failed.append("teletransportes no teste mesoscópico")

    _step("saídas do site")
    out = site_dir / "network"
    report.files["network/roads.geojson"] = write_geojson(out / "roads.geojson", site_roads(edges))
    report.files["network/signals.geojson"] = write_geojson(
        out / "signals.geojson", signal_frame(before, after, fixes.remove, city)
    )
    report.files["network/gates.geojson"] = write_geojson(
        out / "gates.geojson", gates[["name", "highway", "lanes", "direction", "geometry"]]
    )
    report.files["network/corridors.geojson"] = write_geojson(
        out / "corridors.geojson", corridors[corridors["routed"]]
    )
    site_summary = {
        k: summary[k] for k in ("osm", "network", "signals", "zones", "reachability", "smoke_test")
    }
    report.files["network/summary.json"] = write_json(out / "summary.json", site_summary)
    write_json(reports_dir / "network.json", summary)
    return report
