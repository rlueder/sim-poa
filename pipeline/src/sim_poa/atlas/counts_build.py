"""Montagem das contagens: leitura com cache, localização, corredores e saídas."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from sim_poa.atlas import counts
from sim_poa.atlas.geocode import Location, StreetIndex

# Pastas de cada fonte com planilhas de contagem (padrões glob relativos a data/raw/<fonte>).
COUNT_SOURCES: dict[str, list[str]] = {
    "pesquisas-fluxo": ["Veículos/**/*", "Pedestres/**/*", "Ciclistas/**/*"],
    "levantamentos-cit": ["Levantamentos CIT (Até 2019)/**/*"],
    "contagens-matricial": ["Contagens Matricial/**/*"],
}

# Corredores de foco (decisão 4 do guia) e a distância usada para associar pontos a eles.
FOCUS_CORRIDORS: dict[str, list[str]] = {
    "Av. Carlos Gomes": ["CARLOS GOMES"],
    "Av. Protásio Alves": ["PROTASIO ALVES"],
    "Av. Ipiranga": ["IPIRANGA"],
    "Av. Nilo Peçanha / Av. Nilópolis": ["NILO PECANHA", "NILOPOLIS"],
}
CORRIDOR_METRES = 150.0
CACHE_VERSION = 4


@dataclass
class Survey:
    info: counts.CountFile
    data: pd.DataFrame | None
    location: Location | None = None
    corridors: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.info.source}/{self.info.path}".encode()).hexdigest()[:12]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def parse_cached(
    path: Path, source: str, relative: str, cache: Path
) -> tuple[counts.CountFile, pd.DataFrame | None]:
    """Lê uma planilha, reaproveitando o resultado anterior se o arquivo não mudou."""
    key = f"v{CACHE_VERSION}-{_sha256(path)}"
    meta_file, data_file = cache / f"{key}.json", cache / f"{key}.parquet"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        info = counts.CountFile(**{**meta, "source": source, "path": relative})
        data = pd.read_parquet(data_file) if data_file.exists() else None
        return info, data
    info, data = counts.parse_workbook(path, source, relative)
    cache.mkdir(parents=True, exist_ok=True)
    if data is not None:
        data.to_parquet(data_file, index=False)
    meta_file.write_text(json.dumps(info.__dict__, ensure_ascii=False), encoding="utf-8")
    return info, data


def name_from_file(relative: str) -> str:
    """Nome do cruzamento no nome do arquivo, sem prefixo, data e sufixos."""
    stem = Path(relative).stem.strip()
    if stem.startswith("(") and ")" in stem:
        # "(VEÍCULOS) 2018-05 Azenha x Botafogo": sai o prefixo e a data.
        stem = stem.split(")", 1)[1].strip()
        parts = stem.split(" ", 1)
        if len(parts) > 1 and any(ch.isdigit() for ch in parts[0]):
            stem = parts[1]
    # Numeração de ponto ("02 - Av. Padre Cacique & Rua C").
    return re.sub(r"^\d+\s*[-\u2013]\s*", "", stem).strip()


def locate(index: StreetIndex, survey: Survey) -> Location:
    attempts = [survey.info.site, name_from_file(survey.info.path)]
    first: Location | None = None
    for name in (a for a in attempts if a):
        found = index.locate(name)
        if found.ok:
            return found
        first = first or found
    return first or Location(None, None, "", "", "sem nome de local")


def corridor_buffers(index: StreetIndex) -> dict[str, Any]:
    buffers: dict[str, Any] = {}
    for label, names in FOCUS_CORRIDORS.items():
        parts = [
            index.geometry[k]
            for k in index.names
            if any(n == k or k.endswith(" " + n) for n in names)
        ]
        if not parts:
            raise ValueError(f"corredor sem eixos correspondentes: {label}")
        buffers[label] = gpd.GeoSeries(parts, crs=index.crs).union_all().buffer(CORRIDOR_METRES)
    return buffers


def tag_corridors(location: Location | None, buffers: dict[str, Any], crs: Any) -> tuple[str, ...]:
    if location is None or not location.ok:
        return ()
    point = gpd.GeoSeries([Point(location.lon, location.lat)], crs=4326).to_crs(crs).iloc[0]
    return tuple(label for label, area in buffers.items() if area.contains(point))


def hourly_totals(data: pd.DataFrame) -> list[float | None]:
    """Total de todos os movimentos e classes por hora; hora incompleta vira `None`."""
    totals: list[float | None] = [None] * 24
    per_interval = data.groupby(["start", "minutes"], as_index=False)["count"].sum()
    per_interval["hour"] = per_interval["start"] // 60
    for key, group in per_interval.groupby("hour"):
        hour = int(cast(int, key))
        covered = int(group["minutes"].sum())
        if 0 <= hour < 24 and covered >= 60:
            totals[hour] = float(group["count"].sum())
    return totals


def quarter_profile(data: pd.DataFrame) -> dict[str, Any] | None:
    quarter = data[data["minutes"].eq(15)]
    if quarter.empty:
        return None
    per = quarter.groupby("start")["count"].sum()
    starts = per.index.to_numpy(dtype=int)
    first, last = int(starts.min()), int(starts.max())
    values = [per.get(s) for s in range(first, last + 15, 15)]
    return {
        "first": first,
        "step": 15,
        "values": [None if v is None else round(float(v)) for v in values],
    }


def collect(raw_dir: Path, cache: Path) -> list[Survey]:
    surveys: list[Survey] = []
    for source, path in counts.discover(raw_dir, COUNT_SOURCES):
        relative = str(path.relative_to(raw_dir / source))
        info, data = parse_cached(path, source, relative, cache)
        surveys.append(Survey(info, data))
    return surveys


def write_report(path: Path, surveys: list[Survey]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in sorted(surveys, key=lambda s: (s.info.source, s.info.path)):
        row = s.info.as_row()
        loc = s.location
        row.update(
            id=s.id,
            lat=loc.lat if loc else None,
            lon=loc.lon if loc else None,
            location_method=loc.method if loc else "",
            location_streets=loc.streets if loc else "",
            location_reason=loc.reason if loc else "",
            corridors="; ".join(s.corridors),
        )
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summary(surveys: list[Survey]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    located = 0
    for s in surveys:
        by_status[s.info.status] = by_status.get(s.info.status, 0) + 1
        if s.info.status != "ok":
            reason = s.info.reason.split(";")[0]
            by_reason[reason] = by_reason.get(reason, 0) + 1
        elif s.location is not None and s.location.ok:
            located += 1
    return {
        "files": len(surveys),
        "by_status": by_status,
        "unread_reasons": dict(sorted(by_reason.items(), key=lambda kv: -kv[1])),
        "read_and_located": located,
    }


def site_payload(surveys: list[Survey]) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    profiles: dict[int, dict[str, Any]] = {}
    for s in surveys:
        if s.info.status != "ok" or s.data is None or s.location is None or not s.location.ok:
            continue
        hourly = hourly_totals(s.data)
        full = [h for h in hourly if h is not None]
        peak = max(range(24), key=lambda h: hourly[h] or -1) if full else None
        rows.append(
            {
                "id": s.id,
                "subject": s.info.subject,
                "name": s.info.site or name_from_file(s.info.path),
                "date": s.info.date,
                "year": s.info.year,
                "month": s.info.month,
                "flags": s.info.flags,
                "classes": s.info.classes,
                "source": s.info.source,
                "lon": s.location.lon,
                "lat": s.location.lat,
                "located_by": s.location.method,
                "corridors": list(s.corridors),
                "hourly": [None if h is None else round(h) for h in hourly],
                "peak_hour": peak,
            }
        )
        profile = quarter_profile(s.data)
        if profile is not None and s.info.year is not None:
            profiles.setdefault(s.info.year, {})[s.id] = profile
    rows.sort(key=lambda r: (r["year"] or 0, r["month"] or 0, r["name"]))
    return {"surveys": rows}, profiles


def corridor_lines(index: StreetIndex) -> gpd.GeoDataFrame:
    rows = []
    for label, names in FOCUS_CORRIDORS.items():
        parts = [
            index.geometry[k]
            for k in index.names
            if any(n == k or k.endswith(" " + n) for n in names)
        ]
        rows.append({"name": label, "geometry": gpd.GeoSeries(parts, crs=index.crs).union_all()})
    frame = gpd.GeoDataFrame(rows, crs=index.crs)
    frame["geometry"] = frame.geometry.simplify(5)
    return frame.to_crs(4326)


def centrelines_path(raw_dir: Path) -> Path:
    found = sorted((raw_dir / "camadas-eptc").glob("EixosLogradouros*.zip"))
    if not found:
        raise FileNotFoundError("eixos de logradouros ausentes; rode pnpm data:fetch")
    return found[-1]
