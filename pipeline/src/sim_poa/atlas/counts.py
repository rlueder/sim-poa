"""Contagens classificadas da EPTC em planilhas.

O formato de blocos (aba `DADOS`) é o mesmo desde pelo menos 1998: um bloco
por "folha", cada um com até quatro movimentos (`FLUXO`), uma coluna por
classe de veículo e uma linha por intervalo de 15 minutos. Muda o conjunto de
classes: `VL VM VP MT` nas contagens da EPTC, `CA LT O CM` nas contagens de
estudos de impacto e `CA TX LT O CM` no estudo do Centro Histórico.

As contagens de pedestres usam o mesmo arranjo com `Horários` e `Movimento:`
no cabeçalho e classes `Na Faixa` / `Fora Faixa`. As de ciclistas (aba
`Tabulação`) são horárias, com a hora repartida em células (`7 | h | - | 8 | h`)
e um grupo de colunas por aproximação (`Origem: A`). Os códigos de classe são
mantidos como a planilha os grava; o significado deles não está nas planilhas.

Toda planilha encontrada entra no relatório, lida ou não, com o motivo.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from sim_poa.atlas.excel import excel_serial
from sim_poa.atlas.workbook import Grid, WorkbookError, read_sheet, sheet_names, text

Status = Literal["ok", "unsupported", "empty", "error"]
Subject = Literal["veiculos", "pedestres", "ciclistas", "desconhecido"]

_INTERVAL = re.compile(
    r"^\s*(\d{1,2})\s*[:hH]\s*(\d{2})\s*(?:-|\u2013|às|a)\s*(\d{1,2})\s*[:hH]\s*(\d{2})"
)
_HOURLY = re.compile(r"^\s*(\d{1,2})\s*h?\s*-\s*(\d{1,2})\s*h\b", re.IGNORECASE)
_HEADER_FIRST = ("INTERVALO", "HORARIO")
_GROUP_LABELS = ("FLUXO", "MOVIMENTO", "ORIGEM")
_DATE_TEXT = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
# Pesquisas de dois dias ("19 e 20/08/2026"): vale o primeiro.
_DATE_RANGE = re.compile(r"(\d{1,2})\s*(?:e|a|,|-)\s*\d{1,2}/(\d{1,2})/(\d{2,4})")
_FILE_YEAR_MONTH = re.compile(r"(?<!\d)(\d{4})-(\d{2})(?!\d)|(?<!\d)(\d{2})-(\d{4})(?!\d)")
MAX_HEADER_GAP = 8


@dataclass
class CountFile:
    source: str
    path: str
    subject: Subject
    status: Status = "error"
    reason: str = ""
    template: str = ""
    site: str = ""
    date: str = ""
    date_from: str = ""
    year: int | None = None
    month: int | None = None
    classes: str = ""
    movements: int = 0
    intervals: int = 0
    flags: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        row = self.__dict__.copy()
        row["flags"] = ",".join(self.flags)
        return row


def _fold(value: str) -> str:
    """Maiúsculas sem acento, para comparar rótulos e nomes de arquivo."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def subject_of(path: Path) -> Subject:
    """Pelo prefixo do nome do arquivo e, na falta dele, pela pasta."""
    name = _fold(path.name)
    for prefix, subject in (
        ("(VEIC", "veiculos"),
        ("(PEDES", "pedestres"),
        ("(CICLIS", "ciclistas"),
    ):
        if name.startswith(prefix):
            return subject  # type: ignore[return-value]
    folders = _fold("/".join(path.parts[:-1]))
    if "PEDEST" in folders:
        return "pedestres"
    if "CICLIS" in folders:
        return "ciclistas"
    if "VEIC" in folders or "CONTAGENS MATRICIAL" in folders or "CONTAGENS" in folders:
        return "veiculos"
    return "desconhecido"


def flags_of(path: Path) -> list[str]:
    name = _fold(path.stem)
    flags = []
    if "INCOMPLET" in name:
        flags.append("incompleta")
    if "PICO" in name:
        flags.append("so-picos")
    if "SABADO" in name or "DOMINGO" in name or "FERIADO" in name:
        flags.append("fim-de-semana")
    if "24H" in name:
        flags.append("24h")
    return flags


def year_month_from_name(name: str) -> tuple[int, int] | None:
    match = _FILE_YEAR_MONTH.search(name)
    if not match:
        return None
    if match.group(1):
        year, month = int(match.group(1)), int(match.group(2))
    else:
        month, year = int(match.group(3)), int(match.group(4))
    if 1990 <= year <= 2100 and 1 <= month <= 12:
        return year, month
    return None


def parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, int | float) and 20000 < value < 80000:
        return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(value))).date()
    if isinstance(value, str):
        match = _DATE_RANGE.search(value) or _DATE_TEXT.search(value)
        if match:
            day, month, year = (int(g) for g in match.groups())
            year += 2000 if year < 50 else (1900 if year < 100 else 0)
            try:
                return dt.date(year, month, day)
            except ValueError:
                return None
    return None


def interval_start(row: list[Any]) -> tuple[int, int] | None:
    """Início do intervalo em minutos e sua duração, a partir do começo da linha."""
    if not row:
        return None
    first = text(row[0])
    match = _INTERVAL.match(first)
    if not match:
        # Planilhas horárias de ciclistas: "7 | h | - | 8 | h" em células separadas.
        hourly = _HOURLY.match(" ".join(text(v) for v in row[:5]))
        if hourly:
            start, end = int(hourly.group(1)), int(hourly.group(2))
            if end == start + 1 and start < 24:
                return start * 60, 60
        return None
    h1, m1, h2, m2 = (int(g) for g in match.groups())
    start, end = h1 * 60 + m1, h2 * 60 + m2
    if end <= start:
        end += 24 * 60
    if end - start in (15, 30, 60) and start < 24 * 60:
        return start, end - start
    return None


def _first_text(row: list[Any]) -> str:
    return next((text(v) for v in row if text(v)), "")


def _label_value(grid: Grid, top: int, label: str) -> Any:
    """Valor à direita de um rótulo (`LOCAL:`, `DATA:`) nas linhas acima de `top`."""
    for r in range(max(0, top - MAX_HEADER_GAP), top):
        row = grid[r]
        for c, cell in enumerate(row):
            if _fold(text(cell)).startswith(label):
                for later in row[c + 1 :]:
                    if text(later) and not _fold(text(later)).startswith(("DATA", "FOLHA")):
                        return later
    return None


@dataclass
class Block:
    header_row: int
    movements: list[tuple[str, list[tuple[int, str]]]]  # (movimento, [(coluna, classe)])


def find_blocks(grid: Grid) -> list[Block]:
    blocks: list[Block] = []
    for r, row in enumerate(grid):
        if not _fold(_first_text(row)).startswith(_HEADER_FIRST) or r + 1 >= len(grid):
            continue
        labels = [c for c, v in enumerate(row) if _fold(text(v)).startswith(_GROUP_LABELS)]
        if not labels:
            continue
        classes_row = grid[r + 1]
        movements: list[tuple[str, list[tuple[int, str]]]] = []
        for i, start in enumerate(labels):
            end = labels[i + 1] if i + 1 < len(labels) else len(classes_row)
            name = next((text(v) for v in row[start + 1 : end] if text(v)), "")
            columns: list[tuple[int, str]] = []
            seen: dict[str, int] = {}
            for c in range(start, min(end, len(classes_row))):
                klass = _fold(text(classes_row[c]))
                if not klass or klass.startswith("TOTAL"):
                    continue
                seen[klass] = seen.get(klass, 0) + 1
                columns.append((c, klass if seen[klass] == 1 else f"{klass}#{seen[klass]}"))
            if columns:
                # Fluxo sem número no cabeçalho: vale a posição na sequência da planilha.
                movements.append((name or str(len(blocks) * len(labels) + i + 1), columns))
        if movements:
            blocks.append(Block(r, movements))
    return blocks


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dt.datetime):
        return excel_serial(value)
    raw = text(value).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def read_blocks(grid: Grid, blocks: list[Block]) -> pd.DataFrame:
    """Contagens em formato longo: movimento, início, duração, classe, contagem."""
    records: list[tuple[str, int, int, str, float]] = []
    for index, block in enumerate(blocks):
        stop = blocks[index + 1].header_row if index + 1 < len(blocks) else len(grid)
        for row in grid[block.header_row + 2 : stop]:
            interval = interval_start(row)
            if interval is None:
                continue
            start, minutes = interval
            for movement, columns in block.movements:
                for column, klass in columns:
                    count = _number(row[column]) if column < len(row) else None
                    if count is not None:
                        records.append((movement, start, minutes, klass, count))
    return pd.DataFrame.from_records(
        records, columns=["movement", "start", "minutes", "class", "count"]
    )


def parse_blocks_workbook(path: Path, info: CountFile, sheet: str) -> pd.DataFrame | None:
    grid = read_sheet(path, sheet)
    blocks = find_blocks(grid)
    if not blocks:
        info.status, info.reason = "unsupported", "aba DADOS sem cabeçalho INTERVALOS/FLUXO"
        return None
    info.template = "blocos-horarios" if grid and _is_hourly(grid, blocks) else "blocos"
    info.site = text(_label_value(grid, blocks[0].header_row, "LOCAL"))
    raw_date = _label_value(grid, blocks[0].header_row, "DATA")
    date = parse_date(raw_date)
    from_name = year_month_from_name(path.name)
    if date is not None:
        info.date, info.date_from, info.year, info.month = (
            date.isoformat(),
            "planilha",
            date.year,
            date.month,
        )
    elif from_name is not None:
        info.year, info.month = from_name
        info.date_from = "nome do arquivo"
    if date is not None and from_name is not None and (date.year, date.month) != from_name:
        info.flags.append("data-diverge-do-nome")
    counts = read_blocks(grid, blocks)
    if counts.empty:
        info.status, info.reason = "empty", "blocos sem nenhuma contagem preenchida"
        return None
    info.classes = " ".join(sorted(counts["class"].unique()))
    info.movements = int(counts["movement"].nunique())
    info.intervals = int(counts["start"].nunique())
    info.status = "ok"
    return counts


def _is_hourly(grid: Grid, blocks: list[Block]) -> bool:
    for row in grid[blocks[0].header_row + 2 :]:
        interval = interval_start(row)
        if interval is not None:
            return interval[1] == 60
    return False


def parse_workbook(path: Path, source: str, relative: str) -> tuple[CountFile, pd.DataFrame | None]:
    info = CountFile(source=source, path=relative, subject=subject_of(Path(relative)))
    info.flags = flags_of(path)
    try:
        names = sheet_names(path)
        for wanted in ("DADOS", "TABULACAO"):
            sheet = next((n for n in names if _fold(n.strip()) == wanted), None)
            if sheet is not None:
                return info, parse_blocks_workbook(path, info, sheet)
        info.status = "unsupported"
        info.reason = "sem aba DADOS ou Tabulação; abas: " + ", ".join(names[:6])
        return info, None
    except WorkbookError as exc:
        info.status, info.reason = "error", str(exc)
        return info, None


def discover(raw_dir: Path, sources: dict[str, list[str]]) -> list[tuple[str, Path]]:
    """Planilhas de contagem por fonte, seguindo os padrões de pasta de cada uma."""
    found: list[tuple[str, Path]] = []
    for source, patterns in sources.items():
        base = raw_dir / source
        for pattern in patterns:
            for path in sorted(base.glob(pattern)):
                if path.is_file() and path.suffix.lower() in (".xls", ".xlsx"):
                    found.append((source, path))
    return found
