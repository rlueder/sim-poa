"""Pesquisa domiciliar de origem e destino de Porto Alegre, 2023 (EDOM 2023).

Lê a planilha anonimizada publicada pela EPTC, confere a expansão contra os
números do relatório final e produz agregados por zona para o site. Nada
abaixo do nível de zona sai deste módulo para o site (decisão 5 do guia).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import openpyxl
import pandas as pd

from sim_poa.atlas.excel import as_code, as_number, minutes_of_day

SHEET_TRIPS = "DESLOCAMENTO"
PORTO_ALEGRE_IBGE = "4314902"

# Códigos de modo principal, da aba "DicionárioDes_Prioridades modos".
MODES: dict[int, tuple[str, str]] = {
    1: ("Trensurb", "coletivo"),
    2: ("Ônibus", "coletivo"),
    3: ("Lotação", "coletivo"),
    4: ("Van", "coletivo"),
    5: ("Catamarã", "coletivo"),
    6: ("Transporte escolar", "coletivo"),
    7: ("Táxi", "individual"),
    8: ("Aplicativo", "individual"),
    9: ("Passageiro de automóvel", "individual"),
    10: ("Dirigindo automóvel", "individual"),
    11: ("Mototáxi", "individual"),
    12: ("Carona de moto", "individual"),
    13: ("Pilotando moto", "individual"),
    14: ("Caminhão", "individual"),
    15: ("Bicicleta", "ativo"),
    16: ("A pé", "ativo"),
}
MOTORIZED_MAX_CODE = 14

# Número mínimo de registros da amostra por par de zonas publicado no site.
# Pares com menos registros são ruído de expansão e, somados, ficam em "outros".
MIN_RECORDS_PER_PAIR = 5


@dataclass(frozen=True)
class ReportFigure:
    name: str
    report: float
    tolerance: float
    unit: str


# Relatório final da EDOM 2023 (P15, rev. 02), seção 2.7.3.
REPORT_TOTAL = ReportFigure("Viagens por dia útil", 1_732_140, 0.01, "relativa")
REPORT_MODE_SHARES: dict[int, float] = {
    10: 0.251,
    16: 0.240,
    2: 0.214,
    9: 0.129,
    8: 0.096,
    6: 0.020,
    13: 0.016,
    15: 0.014,
}
REPORT_PEAK_ALL_AM = (7 * 60 + 15, 220_815)
REPORT_PEAK_MOTOR_AM = (7 * 60, 164_368)
REPORT_PEAK_MOTOR_PM_START = 17 * 60 + 30


@dataclass(frozen=True)
class Check:
    name: str
    ours: float
    report: float
    ok: bool
    note: str


def read_trips(workbook: Path) -> pd.DataFrame:
    """Uma linha por deslocamento, com códigos e horários já normalizados."""
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    try:
        rows = wb[SHEET_TRIPS].iter_rows(values_only=True)
        header = [str(h) if h is not None else "" for h in next(rows)]
        index = {name: i for i, name in enumerate(header) if name}
        missing = {
            "ID_DESL",
            "ID_MOR",
            "ZONA_O",
            "ZONA_D",
            "HOR_O",
            "HOR_D",
            "MODO_PRINC",
            "MOTIVO.DA.VIAGEM",
            "FE_IDADE_AJ",
        } - index.keys()
        if missing:
            raise ValueError(f"colunas ausentes na aba {SHEET_TRIPS}: {sorted(missing)}")
        records: list[dict[str, Any]] = []
        for row in rows:
            if row[index["ID_DESL"]] is None:
                continue
            depart = minutes_of_day(row[index["HOR_O"]])
            arrive = minutes_of_day(row[index["HOR_D"]])
            if depart is not None and arrive is not None and arrive < depart:
                arrive += 24 * 60  # chegou depois da meia-noite
            records.append(
                {
                    "trip_id": str(row[index["ID_DESL"]]),
                    "person_id": str(row[index["ID_MOR"]]),
                    "zone_o": as_code(row[index["ZONA_O"]]),
                    "zone_d": as_code(row[index["ZONA_D"]]),
                    "depart_min": depart,
                    "arrive_min": arrive,
                    "mode": as_code(row[index["MODO_PRINC"]]),
                    "purpose": str(row[index["MOTIVO.DA.VIAGEM"]] or "").strip().upper(),
                    "weight": as_number(row[index["FE_IDADE_AJ"]]),
                }
            )
    finally:
        wb.close()
    trips = pd.DataFrame.from_records(records)
    unknown = set(trips["mode"].dropna().astype(int)) - MODES.keys()
    if unknown:
        raise ValueError(f"códigos de modo fora do dicionário: {sorted(unknown)}")
    if trips["weight"].isna().any():
        raise ValueError(f"{int(trips['weight'].isna().sum())} viagens sem fator de expansão")
    return trips


def peak_by_arrival(
    trips: pd.DataFrame, *, motorized: bool, first_start: int, last_start: int
) -> tuple[int, float]:
    """Hora pico como o relatório a calcula.

    O relatório chama de "viagens ocorrendo ao mesmo tempo" o total expandido
    de viagens que chegam ao destino na janela de uma hora, com janelas em
    passos de 15 minutos. A definição foi encontrada reproduzindo os números
    publicados; ver docs/development/PLAN.md, fase 1.
    """
    selected = trips
    if motorized:
        selected = trips[trips["mode"].le(MOTORIZED_MAX_CODE)]
    arrivals = selected.dropna(subset=["arrive_min"])
    best_start, best_total = first_start, -1.0
    for start in range(first_start, last_start + 1, 15):
        window = arrivals["arrive_min"].gt(start) & arrivals["arrive_min"].le(start + 60)
        total = float(arrivals.loc[window, "weight"].sum())
        if total > best_total:
            best_start, best_total = start, total
    return best_start, best_total


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def validate(trips: pd.DataFrame) -> list[Check]:
    total = float(trips["weight"].sum())
    checks = [
        Check(
            REPORT_TOTAL.name,
            round(total),
            REPORT_TOTAL.report,
            abs(total / REPORT_TOTAL.report - 1) <= REPORT_TOTAL.tolerance,
            "tolerância de 1%",
        )
    ]
    shares = trips.groupby("mode")["weight"].sum() / total
    for code, report_share in REPORT_MODE_SHARES.items():
        ours = float(shares.get(code, 0.0))
        checks.append(
            Check(
                f"Participação: {MODES[code][0]}",
                round(ours, 4),
                report_share,
                abs(ours - report_share) <= 0.01,
                "tolerância de 1 ponto percentual",
            )
        )
    for name, motorized, (start, figure) in (
        ("Hora pico da manhã, todos os modos", False, REPORT_PEAK_ALL_AM),
        ("Hora pico da manhã, motorizadas", True, REPORT_PEAK_MOTOR_AM),
    ):
        ours_start, ours_total = peak_by_arrival(
            trips, motorized=motorized, first_start=5 * 60, last_start=11 * 60
        )
        checks.append(
            Check(
                f"{name} ({_clock(ours_start)})",
                round(ours_total),
                figure,
                ours_start == start and abs(ours_total / figure - 1) <= 0.01,
                f"relatório: {_clock(start)}, tolerância de 1%",
            )
        )
    unzoned = trips["zone_o"].isna() | trips["zone_d"].isna()
    checks.append(
        Check(
            "Viagens sem zona de origem ou destino",
            int(unzoned.sum()),
            float("nan"),
            True,
            "entram no total do dia, mas não nos mapas por zona nem nas linhas de desejo",
        )
    )
    untimed = trips["depart_min"].isna() | trips["arrive_min"].isna()
    checks.append(
        Check(
            "Viagens sem horário legível",
            int(untimed.sum()),
            float("nan"),
            True,
            "entram no total do dia, mas não nas horas pico nem no perfil horário",
        )
    )
    pm_start, pm_total = peak_by_arrival(
        trips, motorized=True, first_start=12 * 60, last_start=21 * 60
    )
    checks.append(
        Check(
            f"Hora pico da tarde, motorizadas ({_clock(pm_start)})",
            round(pm_total),
            float("nan"),
            pm_start == REPORT_PEAK_MOTOR_PM_START,
            f"relatório: {_clock(REPORT_PEAK_MOTOR_PM_START)}, sem total publicado",
        )
    )
    return checks


def read_zones(zones_zip: Path, survey_zones: set[int]) -> gpd.GeoDataFrame:
    """Zonas usadas na pesquisa, em WGS 84 e simplificadas para o navegador."""
    zones = gpd.read_file(f"zip://{zones_zip}")
    zones["zone"] = pd.to_numeric(zones["ZT"], errors="coerce").astype("Int64")
    in_city = zones["CD_MUN"].eq(PORTO_ALEGRE_IBGE)
    keep = zones[in_city | zones["zone"].isin(survey_zones)].copy()
    keep["in_city"] = keep["CD_MUN"].eq(PORTO_ALEGRE_IBGE)
    keep["name"] = keep["NM_MUN"].where(~keep["in_city"], other=None)
    keep["geometry"] = keep.geometry.simplify(15, preserve_topology=True)
    keep["area_km2"] = (keep.geometry.area / 1e6).round(3)
    return keep[["zone", "in_city", "name", "POP_2022", "area_km2", "geometry"]].to_crs(4326)


def mode_group(code: float) -> str:
    if pd.isna(code):
        return "outros"
    return MODES[int(code)][1]


def zone_summary(trips: pd.DataFrame) -> pd.DataFrame:
    """Viagens produzidas e atraídas por zona, por hora e por grupo de modo."""
    trips = trips.assign(
        group=trips["mode"].map(mode_group),
        depart_hour=(trips["depart_min"] // 60).clip(upper=23),
        arrive_hour=((trips["arrive_min"] % (24 * 60)) // 60),
    )
    rows: list[dict[str, Any]] = []
    for zone in sorted(set(trips["zone_o"].dropna()) | set(trips["zone_d"].dropna())):
        origin = trips[trips["zone_o"].eq(zone)]
        destination = trips[trips["zone_d"].eq(zone)]
        rows.append(
            {
                "zone": int(zone),
                "records": len(origin),
                "produced": round(float(origin["weight"].sum())),
                "attracted": round(float(destination["weight"].sum())),
                "produced_by_hour": [
                    round(float(origin.loc[origin["depart_hour"].eq(h), "weight"].sum()))
                    for h in range(24)
                ],
                "attracted_by_hour": [
                    round(float(destination.loc[destination["arrive_hour"].eq(h), "weight"].sum()))
                    for h in range(24)
                ],
                "mode_share": {
                    group: round(float(share), 3)
                    for group, share in (
                        origin.groupby("group")["weight"].sum() / max(origin["weight"].sum(), 1)
                    ).items()
                },
            }
        )
    return pd.DataFrame.from_records(rows)


def desire_lines(trips: pd.DataFrame, centroids: dict[int, tuple[float, float]]) -> pd.DataFrame:
    """Fluxos entre pares de zonas com amostra suficiente, por grupo de modo."""
    pairs = (
        trips.dropna(subset=["zone_o", "zone_d"])
        .assign(group=trips["mode"].map(mode_group))
        .query("zone_o != zone_d")
    )
    grouped = pairs.groupby(["zone_o", "zone_d"])
    records = grouped.size().rename("records")
    totals = grouped["weight"].sum().rename("trips")
    by_group = pairs.pivot_table(
        index=["zone_o", "zone_d"], columns="group", values="weight", aggfunc="sum", fill_value=0
    )
    table = pd.concat([records, totals, by_group], axis=1).reset_index()
    table = table[table["records"].ge(MIN_RECORDS_PER_PAIR)]
    table = table[
        table["zone_o"].astype(int).isin(centroids.keys())
        & table["zone_d"].astype(int).isin(centroids.keys())
    ]
    return table.sort_values("trips", ascending=False)


def departure_profile(trips: pd.DataFrame, window: int = 60, step: int = 15) -> pd.DataFrame:
    """Partidas expandidas na hora seguinte a cada início de 15 em 15 minutos, por motivo.

    Os entrevistados arredondam horários para a hora cheia ou a meia hora, e em
    intervalos de 15 minutos isso vira um pente de picos e vales. A janela móvel
    de uma hora é a mesma forma de apresentação do relatório.
    """
    departed = trips.dropna(subset=["depart_min"])
    starts = range(0, 24 * 60, step)
    columns: dict[str, list[float]] = {}
    for purpose, group in departed.groupby("purpose"):
        minutes = group["depart_min"].to_numpy()
        weights = group["weight"].to_numpy()
        columns[str(purpose)] = [
            float(weights[(minutes >= s) & (minutes < s + window)].sum()) for s in starts
        ]
    return pd.DataFrame(columns, index=list(starts)).round()
