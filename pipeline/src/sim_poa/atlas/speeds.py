"""Pesquisas de velocidade pontual da EPTC.

O formato é o mesmo de 2003 a 2021: uma aba por sessão de medição
("Dados_Pesquisa Velocidade 1", "Pesquisa Veloc."), com uma linha por veículo
medido (número, classe, velocidade em km/h) abaixo do cabeçalho
`Veículo | Classe | Velocidade`. O endereço, a data e o sentido ficam no
topo da aba; a velocidade regulamentar do trecho fica nas abas `FRVT`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from sim_poa.atlas.counts import parse_date, year_month_from_name
from sim_poa.atlas.geocode import fold
from sim_poa.atlas.workbook import Grid, WorkbookError, read_sheet, sheet_names, text

# Velocidades fora desta faixa são erro de digitação ou de radar, não medições.
PLAUSIBLE_KMH = (3.0, 200.0)
MIN_VEHICLES = 20
_DIRECTION = re.compile(
    r"\s+(BC|CB|NS|SN|LO|OL|LS|SL|NL|LN|AMBOS|AMBOS OS SENTIDOS)\s*$", re.IGNORECASE
)
_PREFIX = re.compile(
    r"^(?:\d{4}-\d{2}\s+)?(?:Vel\.?\s*Pt\.?|MV|Pesq\.?\s*Vel\.?)\s*-\s*", re.IGNORECASE
)


@dataclass
class SpeedSurvey:
    source: str
    path: str
    status: str = "error"
    reason: str = ""
    address: str = ""
    direction: str = ""
    date: str = ""
    year: int | None = None
    month: int | None = None
    limit_kmh: float | None = None
    vehicles: int = 0
    sessions: int = 0
    flags: list[str] = field(default_factory=list)


def _is_data_sheet(name: str) -> bool:
    folded = fold(name).strip()
    return folded.startswith(("DADOS_PESQUISA VELOC", "DADOS PESQUISA VELOC", "PESQUISA VELOC"))


def _header_row(grid: Grid) -> int | None:
    for r, row in enumerate(grid[:20]):
        cells = [fold(text(v)) for v in row[:4]]
        if len(cells) >= 3 and cells[0].startswith("VEICULO") and cells[2].startswith("VELOCIDADE"):
            return r
    return None


def _label(grid: Grid, header: int, label: str) -> str:
    for row in grid[:header]:
        for c, cell in enumerate(row):
            if fold(text(cell)).startswith(label):
                for later in row[c + 1 :]:
                    if text(later):
                        return text(later)
    return ""


def read_session(grid: Grid) -> tuple[pd.DataFrame, dict[str, str]] | None:
    header = _header_row(grid)
    if header is None:
        return None
    records: list[tuple[str, float]] = []
    for row in grid[header + 1 :]:
        if len(row) < 3 or text(row[0]) == "" or not text(row[0]).replace(".0", "").isdigit():
            continue
        klass, speed = text(row[1]).upper(), row[2]
        if isinstance(speed, int | float) and PLAUSIBLE_KMH[0] <= float(speed) <= PLAUSIBLE_KMH[1]:
            records.append((klass, float(speed)))
    meta = {
        "address": _label(grid, header, "ENDERECO"),
        "date": _label(grid, header, "DATA"),
        "direction": _label(grid, header, "SENTIDO"),
    }
    if not meta["address"] and header >= 2:
        # Planilhas de 2003: o endereço vem sozinho na segunda linha, sem rótulo.
        meta["address"] = next((text(v) for v in grid[1][1:] if text(v)), "")
    return pd.DataFrame.from_records(records, columns=["class", "kmh"]), meta


def posted_limit(path: Path, names: list[str]) -> float | None:
    for name in names:
        if not fold(name).startswith("FRVT"):
            continue
        for row in read_sheet(path, name, 40):
            for c, cell in enumerate(row):
                if "REGULAMENTAR" in fold(text(cell)):
                    for later in row[c + 1 :]:
                        if isinstance(later, int | float) and 10 <= later <= 120:
                            return float(later)
    return None


def address_from_name(name: str) -> tuple[str, str]:
    """Endereço e sentido a partir do nome do arquivo."""
    stem = Path(name).stem
    stem = re.sub(r"\(.*?\)", " ", stem)
    stem = _PREFIX.sub("", stem).strip()
    direction = ""
    match = _DIRECTION.search(stem)
    if match:
        direction = match.group(1).upper()
        stem = stem[: match.start()]
    stem = re.sub(r"\b(?:n[º°o]\.?)\s*|\bSN\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\s+", " ", stem).strip(" ,-")
    return stem, direction


_TIME_ONLY = re.compile(r"^\s*(?:[àa]s|das)?\s*\d{1,2}[:h]\d{2}", re.IGNORECASE)


def clean_address(address: str) -> str:
    """Endereço da planilha, ou vazio quando a célula traz outra coisa (um horário)."""
    if _TIME_ONLY.match(address) or not re.search(r"[A-Za-zÀ-ú]{3}", address):
        return ""
    cleaned = re.sub(r"\b(?:n[º°o]\.?)\s*|,\s*SN\b", " ", address, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" ,-")


def parse_workbook(
    path: Path, source: str, relative: str
) -> tuple[SpeedSurvey, pd.DataFrame | None]:
    info = SpeedSurvey(source=source, path=relative)
    try:
        names = sheet_names(path)
        data_sheets = [n for n in names if _is_data_sheet(n)]
        if not data_sheets:
            info.status, info.reason = (
                "unsupported",
                "sem aba de dados; abas: " + ", ".join(names[:6]),
            )
            return info, None
        frames: list[pd.DataFrame] = []
        meta: dict[str, str] = {}
        for sheet in data_sheets:
            session = read_session(read_sheet(path, sheet))
            if session is None:
                continue
            frame, sheet_meta = session
            if not frame.empty:
                frames.append(frame.assign(session=len(frames) + 1))
            meta = {k: v or meta.get(k, "") for k, v in sheet_meta.items()}
        if not frames:
            info.status, info.reason = "empty", "nenhuma velocidade válida nas abas de dados"
            return info, None
        data = pd.concat(frames, ignore_index=True)
        name_address, name_direction = address_from_name(Path(relative).name)
        info.address = clean_address(meta.get("address", "")) or name_address
        info.direction = (meta.get("direction") or name_direction).upper()
        date = parse_date(meta.get("date", "").replace(".", "/"))
        if date is not None:
            info.date, info.year, info.month = date.isoformat(), date.year, date.month
        else:
            from_name = year_month_from_name(Path(relative).name)
            year_folder = next(
                (int(p) for p in Path(relative).parts if p.isdigit() and len(p) == 4), None
            )
            if from_name:
                info.year, info.month = from_name
            elif year_folder:
                info.year = year_folder
        info.limit_kmh = posted_limit(path, names)
        info.vehicles = len(data)
        info.sessions = int(data["session"].nunique())
        if info.vehicles < MIN_VEHICLES:
            info.flags.append("amostra-pequena")
        info.status = "ok"
        return info, data
    except WorkbookError as exc:
        info.status, info.reason = "error", str(exc)
        return info, None


def summarise(data: pd.DataFrame, limit: float | None) -> dict[str, Any]:
    speeds = data["kmh"]
    summary: dict[str, Any] = {
        "vehicles": len(speeds),
        "median": round(float(speeds.median()), 1),
        "p85": round(float(speeds.quantile(0.85)), 1),
        "by_class": {k: int(v) for k, v in data["class"].value_counts().items()},
    }
    summary["above_limit"] = None if limit is None else round(float((speeds > limit).mean()), 3)
    return summary
