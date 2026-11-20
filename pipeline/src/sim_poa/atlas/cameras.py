"""Fluxo de dia típico dos controladores e redutores eletrônicos de velocidade.

A EPTC publica só em PDF: um relatório por ano e por tipo de equipamento, com
uma linha por equipamento ("Av. Assis Brasil 4908 - BC") e doze médias
mensais, em unidade veicular padrão. Segundo as notas dos relatórios, cada
média é dos dias típicos (terça, quarta e quinta) do mês, sem dias zerados e
sem dias em que o equipamento não operou o dia inteiro; "-" é mês sem dado.

A localização vem do cadastro de equipamentos (`_MEV_*.zip`), que usa o mesmo
rótulo do relatório no campo LOCAL; o que não casa é localizado pelo endereço.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pdfplumber

MONTHS = 12
_VALUE = re.compile(r"^(?:\d{1,3}(?:\.\d{3})*|-)$")
_DIRECTION = re.compile(r"\s+-\s+([A-Z]{2}(?:/[A-Z]{2})?)\b")
_YEAR = re.compile(r"(?<!\d)(20\d{2})FluxoDiaTipico", re.IGNORECASE)


@dataclass
class CameraRow:
    label: str
    direction: str
    kind: str
    year: int
    values: list[int | None]


@dataclass
class CameraReport:
    path: str
    kind: str
    year: int | None
    rows: list[CameraRow] = field(default_factory=list)
    skipped_lines: list[str] = field(default_factory=list)


def kind_of(name: str) -> str | None:
    folded = name.upper()
    if "FLUXODIATIPICO" not in folded.replace(" ", ""):
        return None
    if "REDUTOR" in folded:
        return "redutor"
    if "CONTROL" in folded:
        return "controlador"
    return None


def parse_line(line: str, kind: str, year: int) -> CameraRow | None:
    tokens = line.split()
    if len(tokens) <= MONTHS or not all(_VALUE.match(t) for t in tokens[-MONTHS:]):
        return None
    location = " ".join(tokens[:-MONTHS])
    found = list(_DIRECTION.finditer(location))
    direction = found[-1].group(1) if found else ""
    values = [None if t == "-" else int(t.replace(".", "")) for t in tokens[-MONTHS:]]
    return CameraRow(location.strip(), direction, kind, year, values)


def parse_pdf(path: Path, relative: str) -> CameraReport:
    kind = kind_of(path.name)
    year_match = _YEAR.search(path.name)
    report = CameraReport(relative, kind or "", int(year_match.group(1)) if year_match else None)
    if kind is None or report.year is None:
        return report
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                row = parse_line(line, kind, report.year)
                if row is not None:
                    report.rows.append(row)
                elif re.search(r"\d{1,3}\.\d{3}", line):
                    # Linha com cara de dado que não fechou em doze valores: fica registrada.
                    report.skipped_lines.append(line)
    return report


def label_key(label: str) -> str:
    """Rótulo normalizado para casar relatório e cadastro."""
    decomposed = unicodedata.normalize("NFKD", label)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).upper()
    plain = re.sub(r"\(.*?\)", " ", plain)
    plain = re.sub(r"\bDF\b|\bN[ºO°]?\b\.?", " ", plain)
    return re.sub(r"[^A-Z0-9]+", "", plain)


def read_registry(path: Path) -> dict[str, dict[str, object]]:
    """Cadastro de equipamentos por rótulo normalizado, com coordenadas e limite."""
    registry = gpd.read_file(f"zip://{path}")
    found: dict[str, dict[str, object]] = {}
    for row in registry.itertuples():
        try:
            lat, lon = float(row.LATITUD), float(row.LONGITU)
        except (TypeError, ValueError):
            continue
        limit_match = re.search(r"\d+", str(row.LIMITEK or ""))
        found[label_key(str(row.LOCAL))] = {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "lanes": int(row.NFAIXAS) if str(row.NFAIXAS).isdigit() else None,
            "limit_kmh": int(limit_match.group()) if limit_match else None,
            "status": str(row.SITUACA or ""),
        }
    return found


def street_address(label: str) -> str:
    """Endereço sem o sentido e sem observações, para localizar pelo eixo."""
    without_direction = _DIRECTION.split(label)[0]
    return re.sub(r"\(.*?\)", " ", without_direction).strip()
