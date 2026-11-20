"""Conferências da rede: entradas da cidade, semáforos, zonas, conectividade e corredores."""

from __future__ import annotations

import heapq
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from sim_poa.network.sumo_env import binary, run_tool, tools_dir, use_sumolib

METRIC_CRS = 31982
GATE_CLASSES = frozenset(
    {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary"}
)
SIGNAL_MATCH_METRES = 30.0
UNSET_METRES = 80.0

# Corredores para o tempo em fluxo livre: os quatro de foco (decisão 4) e as
# outras radiais e perimetrais principais. Nomes como estão no OSM.
CORRIDORS: dict[str, tuple[str, ...]] = {
    "Carlos Gomes": ("Avenida Carlos Gomes",),
    "Protásio Alves": ("Avenida Protásio Alves",),
    "Ipiranga": ("Avenida Ipiranga",),
    "Nilo Peçanha / Nilópolis": (
        "Avenida Doutor Nilo Peçanha",
        "Avenida Nilo Peçanha",
        "Avenida Nilópolis",
    ),
    "Bento Gonçalves": ("Avenida Bento Gonçalves",),
    "Assis Brasil": ("Avenida Assis Brasil",),
    "Farrapos": ("Avenida Farrapos",),
    "Sertório": ("Avenida Sertório",),
    "Edvaldo Pereira Paiva": ("Avenida Edvaldo Pereira Paiva",),
    "Baltazar de Oliveira Garcia": ("Avenida Baltazar de Oliveira Garcia",),
}


def load_net(path: Path) -> Any:
    use_sumolib()
    import sumolib  # type: ignore[import-not-found]  # vem do tools/ do pacote eclipse-sumo

    return sumolib.net.readNet(str(path), withInternal=False)


def edge_table(net: Any) -> gpd.GeoDataFrame:
    """Uma linha por aresta, em WGS 84, com o que as conferências usam."""
    rows = []
    for edge in net.getEdges():
        rows.append(
            {
                "edge": edge.getID(),
                "name": edge.getName() or "",
                "highway": str(edge.getType()).removeprefix("highway."),
                "lanes": edge.getLaneNumber(),
                "speed_kmh": round(edge.getSpeed() * 3.6, 1),
                "length_m": edge.getLength(),
                "passenger": bool(edge.allows("passenger")),
                "geometry": LineString([net.convertXY2LonLat(x, y) for x, y in edge.getShape()]),
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)


def gates(edges: gpd.GeoDataFrame, city: BaseGeometry) -> gpd.GeoDataFrame:
    """Arestas das classes principais que cruzam a divisa do município."""
    major = edges[edges["highway"].isin(GATE_CLASSES) & edges["passenger"]]
    crossing = major[major.intersects(city.boundary)].copy()
    starts = gpd.GeoSeries([Point(g.coords[0]) for g in crossing.geometry], crs=4326)
    ends = gpd.GeoSeries([Point(g.coords[-1]) for g in crossing.geometry], crs=4326)
    start_inside = starts.within(city).to_numpy()
    end_inside = ends.within(city).to_numpy()
    crossing["direction"] = np.where(end_inside, "entrada", "saída")
    return crossing[start_inside != end_inside].reset_index(drop=True)


def zone_anchors(edges: gpd.GeoDataFrame, zones: gpd.GeoDataFrame) -> pd.DataFrame:
    """Para cada zona, quantas arestas de carro ela contém e a mais próxima do seu ponto.

    A aresta-âncora serve só para conferir conectividade; a demanda (fase 3) usa
    todas as arestas da zona.
    """
    drivable = edges[edges["passenger"]].to_crs(METRIC_CRS)
    midpoints = drivable.assign(geometry=drivable.geometry.interpolate(0.5, normalized=True))
    metric_zones = zones.to_crs(METRIC_CRS)
    joined = gpd.sjoin(midpoints, metric_zones[["zone", "geometry"]], predicate="within")
    rows = []
    for zone, polygon in zip(metric_zones["zone"], metric_zones.geometry, strict=True):
        inside = joined[joined["zone"].eq(zone)]
        anchor = None
        if len(inside):
            point = polygon.representative_point()
            anchor = inside.iloc[int(np.argmin(inside.distance(point).to_numpy()))]["edge"]
        rows.append({"zone": int(zone), "edges": len(inside), "anchor": anchor})
    return pd.DataFrame(rows)


@dataclass
class SignalComparison:
    network: gpd.GeoDataFrame
    inventory: gpd.GeoDataFrame

    @property
    def counts(self) -> dict[str, int]:
        return {
            "inventario": len(self.inventory),
            "inventario_casado": int(self.inventory["matched"].sum()),
            "inventario_sem_semaforo_na_rede": int((~self.inventory["matched"]).sum()),
            "rede": len(self.network),
            "rede_casada": int(self.network["matched"].sum()),
            "rede_sem_registro_no_inventario": int((~self.network["matched"]).sum()),
        }


def network_signals(net: Any) -> gpd.GeoDataFrame:
    """Uma linha por nó semaforizado da rede (um controlador pode ter vários nós)."""
    rows = []
    for tls in net.getTrafficLights():
        nodes = {conn[0].getEdge().getToNode() for conn in tls.getConnections()}
        for node in nodes:
            lon, lat = net.convertXY2LonLat(*node.getCoord())
            rows.append({"tls": tls.getID(), "node": node.getID(), "geometry": Point(lon, lat)})
    frame = gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)
    return frame.drop_duplicates("node").reset_index(drop=True)


def _matched(left: gpd.GeoDataFrame, right: gpd.GeoDataFrame) -> np.ndarray:
    near = gpd.sjoin_nearest(
        left, right[["geometry"]], max_distance=SIGNAL_MATCH_METRES, how="left"
    )
    found = near.groupby(level=0)["index_right"].first().reindex(left.index).notna()
    result: np.ndarray = found.to_numpy()
    return result


def compare_signals(net_signals: gpd.GeoDataFrame, inventory: gpd.GeoDataFrame) -> SignalComparison:
    """Casa os semáforos da rede e os do cadastro da EPTC pela distância."""
    a = net_signals.to_crs(METRIC_CRS)
    b = inventory.to_crs(METRIC_CRS)
    network = net_signals.assign(matched=_matched(a, b))
    registry = inventory.assign(matched=_matched(b, a))
    return SignalComparison(network, registry)


def junctions(net: Any) -> gpd.GeoDataFrame:
    """Nós da rede onde um semáforo faz sentido: com alguma aresta chegando."""
    rows = []
    for node in net.getNodes():
        if not node.getIncoming() or node.getType() == "dead_end":
            continue
        lon, lat = net.convertXY2LonLat(*node.getCoord())
        rows.append({"node": node.getID(), "type": node.getType(), "geometry": Point(lon, lat)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)


@dataclass
class SignalCorrections:
    add: list[str]
    remove: list[str]
    unplaced: gpd.GeoDataFrame


def signal_corrections(
    comparison: SignalComparison, nodes: gpd.GeoDataFrame, city: BaseGeometry
) -> SignalCorrections:
    """O que mudar na rede para ela seguir o cadastro, só onde o cadastro é claro.

    Liga um semáforo no nó mais próximo (até `SIGNAL_MATCH_METRES`) de cada
    registro do cadastro sem semáforo na rede. Desliga os semáforos da rede
    dentro do município sem nenhum registro a `UNSET_METRES`: com uma distância
    maior que a do casamento, um semáforo do OSM posto um pouco antes do
    cruzamento não é desligado por engano. Fora do município o cadastro não vale.
    """
    missing = comparison.inventory[~comparison.inventory["matched"]].to_crs(METRIC_CRS)
    candidates = nodes[~nodes["type"].str.startswith("traffic_light")].to_crs(METRIC_CRS)
    near = gpd.sjoin_nearest(
        missing, candidates[["node", "geometry"]], max_distance=SIGNAL_MATCH_METRES, how="left"
    )
    near = near[~near.index.duplicated(keep="first")]
    add = sorted(set(near["node"].dropna()))
    unplaced = comparison.inventory.loc[near.index[near["node"].isna()]]

    network = comparison.network.to_crs(METRIC_CRS)
    inside = network[network.to_crs(4326).within(city)]
    registry = comparison.inventory.to_crs(METRIC_CRS)
    far = gpd.sjoin_nearest(inside, registry[["geometry"]], max_distance=UNSET_METRES, how="left")
    far = far[~far.index.duplicated(keep="first")]
    remove = sorted(set(far.loc[far["index_right"].isna(), "node"]))
    return SignalCorrections(add=add, remove=remove, unplaced=unplaced)


def write_trips(path: Path, pairs: list[tuple[str, str, str]]) -> None:
    root = ET.Element("routes")
    for trip_id, origin, destination in pairs:
        ET.SubElement(
            root, "trip", {"id": trip_id, "depart": "0", "from": origin, "to": destination}
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def route(net_file: Path, trips: Path, output: Path) -> dict[str, list[str]]:
    """Roteia com o duarouter. Viagens sem caminho ficam de fora do resultado."""
    run_tool(
        [
            binary("duarouter"),
            "--net-file",
            str(net_file),
            "--route-files",
            str(trips),
            "--output-file",
            str(output),
            "--ignore-errors",
            "--no-warnings",
            "--no-step-log",
            "--routing-threads",
            "4",
        ],
    )
    routes: dict[str, list[str]] = {}
    for vehicle in ET.parse(output).getroot().iter("vehicle"):
        found = vehicle.find("route")
        if found is not None:
            routes[vehicle.get("id", "")] = found.get("edges", "").split()
    return routes


def reachability(net_file: Path, anchors: pd.DataFrame, folder: Path) -> pd.DataFrame:
    """Roteia todos os pares de zonas pelas arestas-âncora; uma linha por par sem rota."""
    anchored = anchors.dropna(subset=["anchor"])
    ends = list(zip(anchored["zone"].astype(int), anchored["anchor"].astype(str), strict=True))
    pairs = [(f"{o}_{d}", a, b) for o, a in ends for d, b in ends if o != d]
    trips = folder / "zonas.trips.xml"
    write_trips(trips, pairs)
    routed = route(net_file, trips, folder / "zonas.rou.xml")
    missing = [
        {"origin": int(trip_id.split("_")[0]), "destination": int(trip_id.split("_")[1])}
        for trip_id, _, _ in pairs
        if trip_id not in routed
    ]
    return pd.DataFrame(missing, columns=["origin", "destination"])


OFF_CORRIDOR_PENALTY = 20.0


def cheapest_path(
    successors: dict[str, list[str]], cost: dict[str, float], start: str, goal: str
) -> list[str] | None:
    """Dijkstra sobre arestas: o custo de um caminho é a soma do custo das suas arestas."""
    best = {start: cost[start]}
    previous: dict[str, str] = {}
    queue = [(cost[start], start)]
    while queue:
        total, edge = heapq.heappop(queue)
        if edge == goal:
            path = [goal]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return path[::-1]
        if total > best[edge]:
            continue
        for following in successors.get(edge, []):
            candidate = total + cost[following]
            if candidate < best.get(following, float("inf")):
                best[following] = candidate
                previous[following] = edge
                heapq.heappush(queue, (candidate, following))
    return None


def _corridor_ends(street: gpd.GeoDataFrame) -> tuple[Point, Point]:
    """As pontas do corredor: os dois pontos de arestas mais distantes entre si."""
    middle = street.geometry.interpolate(0.5, normalized=True)
    xy = np.column_stack([middle.x, middle.y])
    distances = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=-1)
    i, j = np.unravel_index(int(np.argmax(distances)), distances.shape)
    return middle.iloc[int(i)], middle.iloc[int(j)]


def _edge_heading(street: gpd.GeoDataFrame, near: Point, target: Point) -> str:
    """A aresta do corredor mais perto de `near` cujo sentido aponta para `target`."""
    heads = gpd.GeoSeries([Point(g.coords[-1]) for g in street.geometry], index=street.index)
    tails = gpd.GeoSeries([Point(g.coords[0]) for g in street.geometry], index=street.index)
    forward = street[heads.distance(target) < tails.distance(target)]
    pool = forward if len(forward) else street
    return str(pool.loc[pool.distance(near).idxmin(), "edge"])


def corridor_free_flow(net: Any, edges: gpd.GeoDataFrame, city: BaseGeometry) -> gpd.GeoDataFrame:
    """Extensão e tempo em fluxo livre de cada corredor, nos dois sentidos.

    A rota vai de uma ponta à outra do corredor pelo caminho mais rápido, com o
    tempo das vias de outro nome multiplicado por `OFF_CORRIDOR_PENALTY`, para
    ela seguir a avenida mesmo onde um desvio seria mais rápido. O tempo
    informado é o real, sem a penalidade: comprimento sobre velocidade máxima
    de cada aresta, sem semáforos nem conversões. `on_corridor` é a parte da
    extensão que ficou nas vias com o nome do corredor.
    """
    drivable = edges[edges["passenger"]]
    seconds = dict(
        zip(drivable["edge"], drivable["length_m"] / (drivable["speed_kmh"] / 3.6), strict=True)
    )
    successors = {
        edge_id: [e.getID() for e in net.getEdge(edge_id).getAllowedOutgoing("passenger")]
        for edge_id in seconds
    }
    inside = drivable[drivable.intersects(city)].to_crs(METRIC_CRS)
    by_id = edges.set_index("edge")
    rows = []
    for label, names in CORRIDORS.items():
        on_street = set(drivable.loc[drivable["name"].isin(names), "edge"])
        street = inside[inside["edge"].isin(on_street)]
        if len(street) < 2:
            rows.append({"corridor": label, "direction": "ida", "routed": False})
            continue
        cost = {e: s if e in on_street else s * OFF_CORRIDOR_PENALTY for e, s in seconds.items()}
        first, last = _corridor_ends(street)
        for way, (a, b) in (("ida", (first, last)), ("volta", (last, first))):
            path = cheapest_path(
                successors, cost, _edge_heading(street, a, b), _edge_heading(street, b, b)
            )
            if path is None:
                rows.append({"corridor": label, "direction": way, "routed": False})
                continue
            legs = by_id.loc[path]
            length = float(legs["length_m"].sum())
            on = float(legs.loc[legs.index.isin(on_street), "length_m"].sum())
            rows.append(
                {
                    "corridor": label,
                    "direction": way,
                    "routed": True,
                    "length_km": round(length / 1000, 2),
                    "free_flow_min": round(sum(seconds[e] for e in path) / 60, 1),
                    "on_corridor": round(on / length, 2),
                    "geometry": legs.geometry.union_all(),
                }
            )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)


def smoke_test(
    net_file: Path, folder: Path, seconds: int = 3600, period: float = 1.0
) -> dict[str, Any]:
    """Viagens aleatórias em modo mesoscópico; conta inserções, chegadas e teletransportes."""
    folder.mkdir(parents=True, exist_ok=True)
    trips = folder / "aleatorias.trips.xml"
    use_sumolib()
    run_tool(
        [
            sys.executable,
            str(tools_dir() / "randomTrips.py"),
            "--net-file",
            str(net_file),
            "--output-trip-file",
            str(trips),
            # Com --validate o randomTrips grava rotas; sem isto, em routes.rou.xml no cwd.
            "--route-file",
            str(folder / "aleatorias.rou.xml"),
            "--end",
            str(seconds),
            "--period",
            str(period),
            "--fringe-factor",
            "5",
            "--min-distance",
            "1000",
            "--validate",
            "--seed",
            "42",
            "--vehicle-class",
            "passenger",
        ],
    )
    result = run_tool(
        [
            binary("sumo"),
            "--net-file",
            str(net_file),
            "--route-files",
            str(trips),
            "--mesosim",
            "--end",
            str(seconds * 3),
            "--no-step-log",
            "--no-warnings",
            "--duration-log.statistics",
            "--seed",
            "42",
        ],
    )
    return parse_statistics(result.stdout + result.stderr)


def parse_statistics(output: str) -> dict[str, Any]:
    """Números do resumo que o `sumo --duration-log.statistics` imprime no fim."""

    def number(label: str) -> int | None:
        found = re.search(rf"{label}:\s*(\d+)", output)
        return int(found.group(1)) if found else None

    inserted = number("Inserted")
    teleports = number("Teleports") or 0
    return {
        "inserted": inserted,
        "running": number("Running"),
        "waiting": number("Waiting"),
        "teleports": teleports,
        "teleport_share": teleports / inserted if inserted else None,
    }
