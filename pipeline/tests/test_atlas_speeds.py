from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from sim_poa.atlas import speeds


def _workbook(path: Path, *, address: str, speeds_kmh: list[object], limit: object = 40) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Dados_Pesquisa Velocidade 1"
    ws.cell(1, 6, "Endereço:")
    ws.cell(1, 8, address)
    ws.cell(2, 6, "Data:")
    ws.cell(2, 8, "12.09.2011")
    ws.cell(3, 6, "Sentido:")
    ws.cell(3, 8, "bc")
    for c, label in enumerate(["Veículo", "Classe", "Velocidade", "<30"], start=1):
        ws.cell(5, c, label)
    for i, kmh in enumerate(speeds_kmh, start=1):
        ws.cell(5 + i, 1, i)
        ws.cell(5 + i, 2, "VL" if i % 5 else "VP")
        ws.cell(5 + i, 3, kmh)
    frvt = wb.create_sheet("FRVT 1")
    frvt.cell(23, 5, "Velocidade Regulamentar do trecho")
    frvt.cell(23, 11, limit)
    wb.save(path)
    return path


def test_reads_vehicles_metadata_and_posted_limit(tmp_path: Path) -> None:
    values: list[object] = [30, 45, 50, 55, 60, 2, 250, "x", None, *[42] * 20]
    path = _workbook(
        tmp_path / "Vel Pt - Dr Nilo Peçanha, 3410 BC.xlsx",
        address="Av Dr Nilo Peçanha, nº 3410",
        speeds_kmh=values,
    )
    info, data = speeds.parse_workbook(path, "pesquisas-fluxo", "Velocidade/2011/" + path.name)
    assert info.status == "ok"
    assert info.address == "Av Dr Nilo Peçanha, 3410"
    assert (info.direction, info.date, info.limit_kmh) == ("BC", "2011-09-12", 40.0)
    assert data is not None
    # 2 km/h e 250 km/h são descartados como implausíveis; "x" e vazio não são velocidades.
    assert info.vehicles == 25 and len(data) == 25
    assert info.flags == []


def test_small_sample_is_flagged_and_time_cell_falls_back_to_file_name(tmp_path: Path) -> None:
    path = _workbook(
        tmp_path / "MV - Atilio Superti, df 571 BC.xlsx", address="Às 15:00", speeds_kmh=[40, 50]
    )
    info, _ = speeds.parse_workbook(path, "x", "Velocidade/2012/" + path.name)
    assert info.address == "Atilio Superti, df 571"
    assert info.flags == ["amostra-pequena"]


def test_workbook_without_data_sheet_is_unsupported(tmp_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Plan1"
    path = tmp_path / "outro.xlsx"
    wb.save(path)
    info, data = speeds.parse_workbook(path, "x", "outro.xlsx")
    assert (info.status, data) == ("unsupported", None)


@pytest.mark.parametrize(
    ("name", "address", "direction"),
    [
        ("Vel Pt - Dr Nilo Peçanha, 3410 BC.xls", "Dr Nilo Peçanha, 3410", "BC"),
        ("2021-04 MV - Dr Hermes Pacheco, 130 SN.xls", "Dr Hermes Pacheco, 130", "SN"),
        ("Manoel Elias, n° 1510 SN.xls", "Manoel Elias, 1510", "SN"),
        ("Gastão Haslocher Mazeron  65 CB.xls", "Gastão Haslocher Mazeron 65", "CB"),
        (
            "Cavalhada 3884 BC (Entre Estr. Vila Maria e Estr. João Vedana).xls",
            "Cavalhada 3884",
            "BC",
        ),
    ],
)
def test_address_from_name(name: str, address: str, direction: str) -> None:
    assert speeds.address_from_name(name) == (address, direction)


def test_summary_reports_percentiles_and_share_above_limit() -> None:
    data = pd.DataFrame({"class": ["VL"] * 10, "kmh": [float(v) for v in range(31, 41)]})
    summary = speeds.summarise(data, 38.0)
    assert summary["median"] == 35.5
    assert summary["p85"] == pytest.approx(38.65, abs=0.06)
    assert summary["above_limit"] == 0.2
    assert speeds.summarise(data, None)["above_limit"] is None
