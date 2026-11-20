"""Camadas de oferta da EPTC: Área Azul, semáforos e corredores de ônibus."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import linemerge, unary_union

SIMPLIFY_METRES = 3.0
METRIC_CRS = 31982  # SIRGAS 2000 / UTM 22S


def _read(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(f"zip://{path}")


def blue_zone(path: Path) -> gpd.GeoDataFrame:
    """Vagas da Área Azul agrupadas por face de quadra (logradouro, numeral, lado, tipo).

    O cadastro desenha cada vaga como um segmento de cerca de 5 m; para o mapa,
    as vagas contíguas viram uma linha com a contagem de vagas.
    """
    spaces = _read(path).to_crs(METRIC_CRS)
    keys = ["LOGRADO", "NUMERAL", "POSICAO", "TIPO"]
    spaces[keys] = spaces[keys].astype(str).fillna("")
    rows = []
    for (street, number, side, kind), group in spaces.groupby(keys):
        union = unary_union(list(group.geometry))
        merged = linemerge(union) if union.geom_type == "MultiLineString" else union
        rows.append(
            {
                "street": street,
                "number": number,
                "side": side,
                "kind": kind,
                "spaces": len(group),
                "geometry": merged,
            }
        )
    blocks = gpd.GeoDataFrame(rows, crs=METRIC_CRS)
    blocks["geometry"] = blocks.geometry.simplify(SIMPLIFY_METRES)
    return blocks.to_crs(4326)


def signals(path: Path) -> gpd.GeoDataFrame:
    layer = _read(path).to_crs(4326)
    frame = pd.DataFrame(
        {
            "code": layer["COD"].astype(str),
            "description": layer["DESCRIC"]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip(),
            "kind": layer["TIPO"].astype(str),
            "detector": layer["DETETOR"].astype(str),
            "status": layer["SITUACA"].astype(str),
        }
    )
    return gpd.GeoDataFrame(frame, geometry=layer.geometry.values, crs=4326)


def bus_corridors(path: Path) -> gpd.GeoDataFrame:
    layer = _read(path).to_crs(METRIC_CRS)
    frame = pd.DataFrame(
        {
            "name": layer["NOME_CO"].astype(str),
            "kind": layer["TRANSPO"].astype(str),
            "hours": layer["HORARIO1"].fillna("").astype(str),
            "section": layer["TRECHO"].fillna("").astype(str),
            "status": layer["SITUACA"].fillna("").astype(str),
        }
    )
    corridors = gpd.GeoDataFrame(frame, geometry=layer.geometry.values, crs=METRIC_CRS)
    corridors["geometry"] = corridors.geometry.simplify(SIMPLIFY_METRES)
    return corridors.to_crs(4326)
