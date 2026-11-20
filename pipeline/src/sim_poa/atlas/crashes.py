"""Sinistros de trânsito da EPTC agregados em grade de 250 m.

O arquivo traz um registro por boletim, com coordenadas. O site mostra a
contagem por célula e ano, separando sinistros com feridos e com vítima grave
ou fatal; os registros individuais não saem daqui.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

CELL_METRES = 250
FIRST_YEAR = 2021
LAT_BOUNDS = (-30.4, -29.8)
LON_BOUNDS = (-51.4, -50.9)
METRIC_CRS = 31982
_FIELDS = [
    "Ano",
    "HoraAproxi",
    "Latitude",
    "Longitude",
    "Ferido",
    "VitimaGrav",
    "Morte",
    "MortePoste",
    "Fatais",
]


def read(path: Path) -> pd.DataFrame:
    frame: pd.DataFrame = pyogrio.read_dataframe(
        f"zip://{path}", columns=_FIELDS, read_geometry=False
    )
    frame = frame[pd.to_numeric(frame["Ano"], errors="coerce").ge(FIRST_YEAR)].copy()
    frame["year"] = frame["Ano"].astype(int)
    for column in ("Ferido", "VitimaGrav", "Morte", "MortePoste", "Fatais"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["injury"] = frame["Ferido"].gt(0) | frame["VitimaGrav"].gt(0)
    frame["severe"] = frame[["VitimaGrav", "Morte", "MortePoste", "Fatais"]].gt(0).any(axis=1)
    hours = frame["HoraAproxi"].astype(str).str.extract(r"^(\d{1,2})")[0]
    frame["hour"] = pd.to_numeric(hours, errors="coerce")
    frame["lat"] = pd.to_numeric(frame["Latitude"], errors="coerce")
    frame["lon"] = pd.to_numeric(frame["Longitude"], errors="coerce")
    return frame


def grid(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Células com sinistros e um resumo da cidade por ano e hora."""
    with_coordinates = frame.dropna(subset=["lat", "lon"])
    # Caixa que envolve Porto Alegre com folga; fora dela é erro de coordenada.
    inside = with_coordinates["lat"].between(*LAT_BOUNDS) & with_coordinates["lon"].between(
        *LON_BOUNDS
    )
    located = with_coordinates[inside]
    points = gpd.GeoSeries(gpd.points_from_xy(located["lon"], located["lat"]), crs=4326).to_crs(
        METRIC_CRS
    )
    located = located.assign(
        cx=(np.floor(points.x.to_numpy() / CELL_METRES) * CELL_METRES + CELL_METRES / 2),
        cy=(np.floor(points.y.to_numpy() / CELL_METRES) * CELL_METRES + CELL_METRES / 2),
    )
    centres = gpd.GeoSeries(
        gpd.points_from_xy(located["cx"], located["cy"]), crs=METRIC_CRS
    ).to_crs(4326)
    located = located.assign(clon=centres.x.round(5).to_numpy(), clat=centres.y.round(5).to_numpy())
    cells: list[dict[str, Any]] = []
    for key, group in located.groupby(["clon", "clat"]):
        lon, lat = (float(v) for v in cast(tuple[float, float], key))
        by_year = group.groupby("year").agg(
            total=("year", "size"), injury=("injury", "sum"), severe=("severe", "sum")
        )
        cells.append(
            {
                "lon": lon,
                "lat": lat,
                "years": {
                    str(y): [int(r.total), int(r.injury), int(r.severe)]
                    for y, r in by_year.iterrows()
                },
            }
        )
    summary = {
        "records": len(frame),
        "without_coordinates": int(len(frame) - len(with_coordinates)),
        "outside_city_bounds": int((~inside).sum()),
        "by_year": {
            str(y): [len(g), int(g["injury"].sum()), int(g["severe"].sum())]
            for y, g in frame.groupby("year")
        },
        "by_hour": [int(v) for v in frame["hour"].value_counts().reindex(range(24), fill_value=0)],
    }
    return cells, summary
