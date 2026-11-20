"""Velocidade dos ônibus no Centro Histórico, a partir do GPS do estudo de mobilidade.

O arquivo `BusGPSCentro` tem 4,6 milhões de pontos de duas semanas: 20 a 26 de
outubro de 2019 e 4 a 10 de julho de 2021. Só a semana de 2019 entra, nos dias
úteis, porque 2021 cai no período da pandemia. Cada ponto é associado ao eixo
de logradouro mais próximo (até `SNAP_METRES`); por eixo e hora, publica-se a
mediana da velocidade dos ônibus em movimento e a parcela de pontos parados.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pyogrio

FIRST_DAY = dt.date(2019, 10, 21)
LAST_DAY = dt.date(2019, 10, 25)
SNAP_METRES = 15.0
MOVING_KMH = 3.0
MIN_POINTS = 30
METRIC_CRS = 31982


def read_points(path: Path) -> gpd.GeoDataFrame:
    layer = f"zip://{path}!BusGPSCentro/BusGPSCentro.shp"
    points = pyogrio.read_dataframe(
        layer,
        columns=["VELOCIDADE", "DIA", "HORA"],
        where=f"DIA >= '{FIRST_DAY.isoformat()}' AND DIA <= '{LAST_DAY.isoformat()}'",
    )
    points["kmh"] = pd.to_numeric(points["VELOCIDADE"], errors="coerce")
    points["hour"] = (pd.to_numeric(points["HORA"], errors="coerce") // 3600).astype("Int64")
    return points.dropna(subset=["kmh", "hour"]).to_crs(METRIC_CRS)


def speeds_by_segment(
    points: gpd.GeoDataFrame, centrelines: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    streets = centrelines[["CDSEG", "NMIDELOG", "geometry"]].to_crs(METRIC_CRS)
    bounds = points.total_bounds
    streets = streets.cx[bounds[0] - 100 : bounds[2] + 100, bounds[1] - 100 : bounds[3] + 100]
    joined = gpd.sjoin_nearest(points, streets, max_distance=SNAP_METRES, how="inner")
    # Um ponto equidistante de dois eixos volta duas vezes, com o mesmo índice;
    # fica a primeira correspondência.
    joined = joined[~joined.index.duplicated(keep="first")]
    joined["moving"] = joined["kmh"].gt(MOVING_KMH)
    rows = []
    for (segment, hour), group in joined.groupby(["CDSEG", "hour"]):
        if len(group) < MIN_POINTS:
            continue
        moving = group.loc[group["moving"], "kmh"]
        rows.append(
            {
                "segment": int(segment),
                "hour": int(hour),
                "points": len(group),
                "median_moving": round(float(moving.median()), 1) if len(moving) else None,
                "stopped": round(1 - float(group["moving"].mean()), 3),
            }
        )
    table = pd.DataFrame(rows)
    summary = {
        "days": [FIRST_DAY.isoformat(), LAST_DAY.isoformat()],
        "points": len(points),
        "snapped": len(joined),
        "segments": int(table["segment"].nunique()) if len(table) else 0,
    }
    if table.empty:
        return gpd.GeoDataFrame(columns=["segment", "name", "hours", "geometry"], crs=4326), summary
    by_segment: dict[int, dict[str, list[Any]]] = {}
    for record in table.to_dict(orient="records"):
        by_segment.setdefault(int(record["segment"]), {})[str(record["hour"])] = [
            record["median_moving"],
            record["stopped"],
            record["points"],
        ]
    hours = pd.Series(by_segment)
    geometry = streets.drop_duplicates("CDSEG").set_index("CDSEG").loc[hours.index]
    segments = gpd.GeoDataFrame(
        {
            "segment": hours.index.astype(int),
            "name": geometry["NMIDELOG"].astype(str).values,
            "hours": hours.values,
        },
        geometry=geometry.geometry.values,
        crs=METRIC_CRS,
    )
    segments["geometry"] = segments.geometry.simplify(2.0)
    return segments.to_crs(4326), summary
