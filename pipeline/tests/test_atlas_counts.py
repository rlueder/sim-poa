from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from sim_poa.atlas import counts, counts_build


def _blocks_workbook(path: Path, *, classes: list[str], header: str = "INTERVALOS") -> Path:
    """Planilha no formato de blocos da EPTC: duas folhas, dois fluxos por folha."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "DADOS"
    width = len(classes)
    for block, first_flow in ((0, 1), (1, 3)):
        top = block * 12
        ws.cell(top + 1, 1, "LOCAL:")
        ws.cell(top + 1, 2, "Av. Teste x Rua Exemplo")
        ws.cell(top + 2, 1, "DATA:")
        ws.cell(top + 2, 2, dt.datetime(2019, 3, 26))
        ws.cell(top + 4, 1, header)
        for g in range(2):
            ws.cell(top + 4, 2 + g * width, "FLUXO :" if header == "INTERVALOS" else "Movimento:")
            # O segundo fluxo do primeiro bloco vem sem número, como em várias planilhas reais.
            if not (block == 0 and g == 1):
                ws.cell(top + 4, 3 + g * width, first_flow + g)
            for k, klass in enumerate(classes):
                ws.cell(top + 5, 2 + g * width + k, klass)
        for i, (start, end) in enumerate((("07:00", "07:15"), ("07:15", "07:30"))):
            ws.cell(top + 6 + i, 1, f"{start} - {end}")
            for g in range(2):
                for k in range(width):
                    ws.cell(top + 6 + i, 2 + g * width + k, (g + 1) * 10 + k + i)
        ws.cell(top + 8, 1, "TOTAL")
    wb.save(path)
    return path


def test_blocks_template_reads_flows_classes_and_intervals(tmp_path: Path) -> None:
    path = _blocks_workbook(
        tmp_path / "(VEÍCULOS) 2019-03 Teste.xlsx", classes=["VL", "VM", "VP", "MT"]
    )
    info, data = counts.parse_workbook(path, "pesquisas-fluxo", "Veículos/" + path.name)
    assert info.status == "ok"
    assert info.subject == "veiculos"
    assert info.site == "Av. Teste x Rua Exemplo"
    assert (info.date, info.date_from) == ("2019-03-26", "planilha")
    assert info.classes == "MT VL VM VP"
    assert data is not None
    # O fluxo sem número no cabeçalho recebe o número da posição (2).
    assert sorted(data["movement"].unique()) == ["1", "2", "3", "4"]
    assert sorted(data["start"].unique()) == [420, 435]
    assert set(data["minutes"]) == {15}
    first = data[(data["movement"] == "1") & (data["start"] == 420) & (data["class"] == "VL")]
    assert first["count"].tolist() == [10.0]


def test_pedestrian_header_variant(tmp_path: Path) -> None:
    path = _blocks_workbook(
        tmp_path / "(PEDESTRES) 2017-10 Teste.xls.xlsx",
        classes=["Na Faixa", "Fora Faixa"],
        header="Horários",
    )
    info, data = counts.parse_workbook(path, "pesquisas-fluxo", "Pedestres/x.xlsx")
    assert info.status == "ok"
    assert info.classes == "FORA FAIXA NA FAIXA"
    assert data is not None and len(data) == 2 * 2 * 2 * 2


def test_hourly_cyclist_rows_split_across_cells(tmp_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Tabulação"
    ws.cell(1, 6, "LOCAL:")
    ws.cell(1, 11, "R. A x R. B")
    ws.cell(2, 6, "DATA:")
    ws.cell(2, 11, dt.datetime(2023, 7, 3))
    ws.cell(4, 1, "Horário")
    ws.cell(4, 6, "Origem:")
    ws.cell(4, 12, "A")
    for k, code in enumerate(["E", "F", "P", "P"]):
        ws.cell(5, 6 + k, code)
    for i, (h1, h2) in enumerate(((7, 8), (8, 9))):
        for c, v in enumerate([h1, "h", "-", h2, "h"]):
            ws.cell(6 + i, 1 + c, v)
        for k in range(4):
            ws.cell(6 + i, 6 + k, k + i)
    path = tmp_path / "(CICLISTAS) 2023-07 A x B.xlsx"
    wb.save(path)
    info, data = counts.parse_workbook(path, "pesquisas-fluxo", "Ciclistas/" + path.name)
    assert info.status == "ok"
    assert info.template == "blocos-horarios"
    assert data is not None
    assert set(data["minutes"]) == {60}
    assert sorted(data["class"].unique()) == ["E", "F", "P", "P#2"]
    assert sorted(data["movement"].unique()) == ["A"]


def test_unsupported_and_broken_files_are_reported(tmp_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "MOV."
    other = tmp_path / "antigo.xlsx"
    wb.save(other)
    info, data = counts.parse_workbook(other, "x", "antigo.xlsx")
    assert (info.status, data) == ("unsupported", None)
    assert "MOV." in info.reason

    broken = tmp_path / "quebrado.xls"
    broken.write_bytes(b"isto nao e uma planilha")
    info, data = counts.parse_workbook(broken, "x", "quebrado.xls")
    assert (info.status, data) == ("error", None)

    empty = _blocks_workbook(tmp_path / "vazio.xlsx", classes=["VL"])
    wb = openpyxl.load_workbook(empty)
    sheet = wb["DADOS"]
    for row in sheet.iter_rows(min_col=2):
        for cell in row:
            if isinstance(cell.value, int) and cell.row not in (4, 16):
                cell.value = None
    wb.save(empty)
    info, _ = counts.parse_workbook(empty, "x", "vazio.xlsx")
    assert info.status == "empty"


@pytest.mark.parametrize(
    ("name", "subject", "flags", "year_month"),
    [
        ("(VEICULOS) 2024-06 A x B_Incompleta.xls", "veiculos", ["incompleta"], (2024, 6)),
        (
            "(VEÍCULOS) 08-2014 A x B - Sábado (24h).xls",
            "veiculos",
            ["fim-de-semana", "24h"],
            (2014, 8),
        ),
        ("(PEDESTRES) 2018-05 A x B (ped+TME).xlsx", "pedestres", [], (2018, 5)),
        ("(CICLISTAS) 2023-07 A x B.xlsx", "ciclistas", [], (2023, 7)),
        ("(VEICULOS) 2026-08 A x B_PICOS.xlsx", "veiculos", ["so-picos"], (2026, 8)),
    ],
)
def test_file_name_metadata(
    name: str, subject: str, flags: list[str], year_month: tuple[int, int]
) -> None:
    assert counts.subject_of(Path(name)) == subject
    assert counts.flags_of(Path(name)) == flags
    assert counts.year_month_from_name(name) == year_month


def test_folder_decides_subject_when_name_has_no_prefix() -> None:
    assert (
        counts.subject_of(Path("Contagens/2003/Pedestres/Farrapos X Sertório.xls")) == "pedestres"
    )
    assert counts.subject_of(Path("Contagens Matricial/x/02 - Av. A & B.xls")) == "veiculos"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (dt.datetime(2018, 5, 3), dt.date(2018, 5, 3)),
        (39960.0, dt.date(2009, 5, 27)),
        ("19 e 20/08/2026", dt.date(2026, 8, 19)),
        (" 19/11/98", dt.date(1998, 11, 19)),
        ("Sábados", None),
        ("31/02/2020", None),
    ],
)
def test_parse_date(value: object, expected: dt.date | None) -> None:
    assert counts.parse_date(value) == expected


def test_hourly_totals_need_a_full_hour() -> None:
    data = pd.DataFrame(
        {
            "movement": ["1"] * 5,
            "start": [420, 435, 450, 465, 480],
            "minutes": [15] * 5,
            "class": ["VL"] * 5,
            "count": [1.0, 2.0, 3.0, 4.0, 9.0],
        }
    )
    hourly = counts_build.hourly_totals(data)
    assert hourly[7] == 10.0
    assert hourly[8] is None  # só um quarto de hora contado


def test_quarter_profile_keeps_gaps() -> None:
    data = pd.DataFrame(
        {
            "movement": ["1", "1"],
            "start": [420, 450],
            "minutes": [15, 15],
            "class": ["VL", "VL"],
            "count": [5.0, 7.0],
        }
    )
    assert counts_build.quarter_profile(data) == {"first": 420, "step": 15, "values": [5, None, 7]}


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("Veículos/(VEÍCULOS) 2018-05 Azenha x Botafogo.xlsx", "Azenha x Botafogo"),
        (
            "Contagens Matricial/x/02 - Av. Padre Cacique & Rua C.xls",
            "Av. Padre Cacique & Rua C",
        ),
        (
            "Contagens/1998/BGO-PAZ - Bento Gonçalves com Paulino Azurenha.xls",
            "BGO-PAZ - Bento Gonçalves com Paulino Azurenha",
        ),
    ],
)
def test_name_from_file(relative: str, expected: str) -> None:
    assert counts_build.name_from_file(relative) == expected


def test_parse_cached_reuses_previous_result(tmp_path: Path) -> None:
    path = _blocks_workbook(tmp_path / "(VEÍCULOS) 2019-03 T.xlsx", classes=["VL"])
    cache = tmp_path / "cache"
    first_info, first = counts_build.parse_cached(path, "s", "a.xlsx", cache)
    assert len(list(cache.glob("*.json"))) == 1
    again_info, again = counts_build.parse_cached(path, "s", "b.xlsx", cache)
    assert again_info.path == "b.xlsx"
    assert again_info.site == first_info.site
    assert first is not None and again is not None
    pd.testing.assert_frame_equal(first, again)
