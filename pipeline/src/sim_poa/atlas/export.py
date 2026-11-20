"""Gravação das saídas do atlas para o site, em arquivos pequenos e estáveis."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd

# Cinco casas decimais em graus dão cerca de 1 m, mais do que o site precisa.
COORD_DECIMALS = 5


def _clean(value: Any) -> Any:
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if hasattr(value, "item"):  # escalares do numpy e do pandas
        return _clean(value.item())
    return value


def write_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_clean(payload), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    return len(text.encode("utf-8")) + 1


def write_geojson(path: Path, frame: gpd.GeoDataFrame) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rounded = frame.copy()
    rounded["geometry"] = rounded.geometry.set_precision(10**-COORD_DECIMALS)
    payload = json.loads(rounded.to_json(drop_id=True))
    return write_json(path, payload)
