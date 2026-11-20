"""Montagem das saídas do atlas a partir de data/raw/."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from sim_poa.atlas import bus_gps, cameras, counts_build, crashes, edom, speeds, supply, transit
from sim_poa.atlas.export import write_geojson, write_json
from sim_poa.atlas.geocode import Location, StreetIndex

EDOM_DIR = Path("edom-2023") / "EDOM 2023"
EDOM_WORKBOOK = "EDOM-2023_BANCO_DE_DADOS_ATUALIZADO_ANONIMIZADO.xlsx"
EDOM_ZONES = "ZONAS_OD.zip"

ATTRIBUTION_EPTC = {
    "name": "EPTC, Prefeitura de Porto Alegre (ObservaMOB)",
    "href": "https://prefeitura.poa.br/eptc/projetos/observamob",
}


@dataclass
class BuildReport:
    reports_dir: Path
    files: dict[str, int] = field(default_factory=dict)
    checks_failed: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Pontos de pesquisa perto dos corredores de foco (decisão 4), de todos os módulos.
    corridor_sites: list[dict[str, object]] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(self.files.values())


def build_edom(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    source = raw_dir / EDOM_DIR
    trips = edom.read_trips(source / EDOM_WORKBOOK)
    checks = edom.validate(trips)
    report.checks_failed += [c.name for c in checks if not c.ok]

    survey_zones = set(trips["zone_o"].dropna().astype(int)) | set(
        trips["zone_d"].dropna().astype(int)
    )
    zones = edom.read_zones(source / EDOM_ZONES, survey_zones)
    points = zones.geometry.representative_point()
    centroids = {
        int(z): (round(p.x, 5), round(p.y, 5)) for z, p in zip(zones["zone"], points, strict=True)
    }

    summary = edom.zone_summary(trips)
    lines = edom.desire_lines(trips, centroids)
    profile = edom.departure_profile(trips)
    out = out_dir / "edom"

    report.files["edom/zones.geojson"] = write_geojson(
        out / "zones.geojson", zones.rename(columns={"POP_2022": "population"})
    )
    report.files["edom/zones.json"] = write_json(
        out / "zones.json",
        {
            "centroids": {str(k): v for k, v in centroids.items()},
            "zones": summary.to_dict(orient="records"),
        },
    )
    report.files["edom/desire_lines.json"] = write_json(
        out / "desire_lines.json",
        {
            "min_records": edom.MIN_RECORDS_PER_PAIR,
            "pairs": [
                {
                    "o": int(r["zone_o"]),
                    "d": int(r["zone_d"]),
                    "records": int(r["records"]),
                    "trips": round(float(r["trips"])),
                    "by_group": {
                        g: round(float(r[g]))
                        for g in ("coletivo", "individual", "ativo")
                        if g in r and r[g] > 0
                    },
                }
                for _, r in lines.iterrows()
            ],
        },
    )
    report.files["edom/profile.json"] = write_json(
        out / "profile.json",
        {
            "slot_minutes": 15,
            "window_minutes": 60,
            "slots": [int(s) for s in profile.index],
            "series": {str(c): [int(v) for v in profile[c]] for c in profile.columns},
        },
    )
    report.files["edom/validation.json"] = write_json(
        out / "validation.json",
        {
            "checks": [
                {"name": c.name, "ours": c.ours, "report": c.report, "ok": c.ok, "note": c.note}
                for c in checks
            ],
            "modes": {str(k): {"name": v[0], "group": v[1]} for k, v in edom.MODES.items()},
            "source": {
                **ATTRIBUTION_EPTC,
                "dataset": "Pesquisa de Origem e Destino Domiciliar 2023 (EDOM 2023)",
            },
        },
    )


def build_counts(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    cache = raw_dir.parent / "derived" / "counts"
    surveys = counts_build.collect(raw_dir, cache)
    index = StreetIndex.from_zip(counts_build.centrelines_path(raw_dir))
    buffers = counts_build.corridor_buffers(index)
    for survey in surveys:
        if survey.info.status == "ok":
            survey.location = counts_build.locate(index, survey)
            survey.corridors = counts_build.tag_corridors(survey.location, buffers, index.crs)
    counts_build.write_report(report.reports_dir / "counts.csv", surveys)
    summary = counts_build.summary(surveys)
    report.notes.append(
        f"contagens: {summary['files']} planilhas, {summary['by_status']}, "
        f"{summary['read_and_located']} lidas e localizadas"
    )
    for survey in surveys:
        for corridor in survey.corridors:
            report.corridor_sites.append(
                {
                    "corridor": corridor,
                    "kind": f"contagem de {survey.info.subject}",
                    "name": survey.info.site or counts_build.name_from_file(survey.info.path),
                    "year": survey.info.year,
                    "source_file": f"{survey.info.source}/{survey.info.path}",
                }
            )
    payload, profiles = counts_build.site_payload(surveys)
    out = out_dir / "counts"
    report.files["counts/surveys.json"] = write_json(
        out / "surveys.json", {**payload, "summary": summary, "source": ATTRIBUTION_EPTC}
    )
    for year, by_id in sorted(profiles.items()):
        report.files[f"counts/profiles/{year}.json"] = write_json(
            out / "profiles" / f"{year}.json", by_id
        )
    report.files["counts/corridors.geojson"] = write_geojson(
        out / "corridors.geojson", counts_build.corridor_lines(index)
    )


SPEED_FOLDER = Path("pesquisas-fluxo") / "Velocidade"
# Faixas do histograma de velocidades publicado no site, em km/h.
SPEED_BINS = list(range(0, 125, 5))


def build_speeds(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    base = raw_dir / SPEED_FOLDER
    files = sorted(p for p in base.rglob("*") if p.suffix.lower() in (".xls", ".xlsx"))
    index = StreetIndex.from_zip(counts_build.centrelines_path(raw_dir))
    buffers = counts_build.corridor_buffers(index)
    rows, published = [], []
    for path in files:
        relative = str(path.relative_to(raw_dir / "pesquisas-fluxo"))
        info, data = speeds.parse_workbook(path, "pesquisas-fluxo", relative)
        location = index.locate(info.address) if info.status == "ok" else None
        corridors = counts_build.tag_corridors(location, buffers, index.crs)
        survey_id = hashlib.sha256(f"{info.source}/{info.path}".encode()).hexdigest()[:12]
        rows.append(
            {
                **{k: v for k, v in info.__dict__.items() if k != "flags"},
                "flags": ",".join(info.flags),
                "id": survey_id,
                "lat": location.lat if location else None,
                "lon": location.lon if location else None,
                "location_method": location.method if location else "",
                "location_streets": location.streets if location else "",
                "location_reason": location.reason if location else "",
                "corridors": "; ".join(corridors),
            }
        )
        for corridor in corridors:
            report.corridor_sites.append(
                {
                    "corridor": corridor,
                    "kind": "velocidade pontual",
                    "name": f"{info.address} ({info.direction})"
                    if info.direction
                    else info.address,
                    "year": info.year,
                    "source_file": f"{info.source}/{info.path}",
                }
            )
        if data is None or location is None or not location.ok:
            continue
        histogram = (
            pd.cut(data["kmh"], bins=[*SPEED_BINS, 1000], right=False)
            .value_counts(sort=False)
            .tolist()
        )
        published.append(
            {
                "id": survey_id,
                "address": info.address,
                "direction": info.direction,
                "date": info.date,
                "year": info.year,
                "limit_kmh": info.limit_kmh,
                "flags": info.flags,
                "lon": location.lon,
                "lat": location.lat,
                "located_by": location.method,
                "corridors": list(corridors),
                "histogram": [int(v) for v in histogram],
                **speeds.summarise(data, info.limit_kmh),
            }
        )
    write_csv(report.reports_dir / "speeds.csv", rows)
    status: dict[str, int] = {}
    for row in rows:
        status[row["status"]] = status.get(row["status"], 0) + 1
    report.notes.append(
        f"velocidades: {len(rows)} planilhas, {status}, {len(published)} lidas e localizadas"
    )
    published.sort(key=lambda r: (r["year"] or 0, r["address"]))
    report.files["speeds/surveys.json"] = write_json(
        out_dir / "speeds" / "surveys.json",
        {
            "bins_kmh": SPEED_BINS,
            "summary": {
                "files": len(rows),
                "by_status": status,
                "read_and_located": len(published),
            },
            "surveys": published,
            "source": ATTRIBUTION_EPTC,
        },
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: str(r.get("path", ""))))


def build_cameras(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    pdfs = sorted((raw_dir / "relatorios-mensais").rglob("*.pdf"))
    registry_files = sorted((raw_dir / "controladores-velocidade").glob("_MEV_*.zip"))
    if not registry_files:
        raise FileNotFoundError("cadastro de equipamentos (_MEV_*.zip) ausente")
    registry = cameras.read_registry(registry_files[-1])
    index = StreetIndex.from_zip(counts_build.centrelines_path(raw_dir))
    buffers = counts_build.corridor_buffers(index)
    sites: dict[str, dict[str, Any]] = {}
    pdf_rows: list[dict[str, object]] = []
    for path in pdfs:
        relative = str(path.relative_to(raw_dir / "relatorios-mensais"))
        if cameras.kind_of(path.name) is None:
            # Outros relatórios da pasta (frota, BikePOA, congestionamento) ficam
            # registrados como ignorados, para um PDF de fluxo renomeado não sumir.
            pdf_rows.append(
                {
                    "path": relative,
                    "kind": "ignorado",
                    "year": None,
                    "rows": 0,
                    "skipped_lines": 0,
                    "first_skipped": "",
                }
            )
            continue
        parsed = cameras.parse_pdf(path, relative)
        pdf_rows.append(
            {
                "path": relative,
                "kind": parsed.kind,
                "year": parsed.year,
                "rows": len(parsed.rows),
                "skipped_lines": len(parsed.skipped_lines),
                "first_skipped": parsed.skipped_lines[0] if parsed.skipped_lines else "",
            }
        )
        for row in parsed.rows:
            key = f"{row.kind}:{cameras.label_key(row.label)}"
            site = sites.get(key)
            if site is None:
                site = {
                    "label": row.label,
                    "kind": row.kind,
                    "direction": row.direction,
                    "series": {},
                }
                registered = registry.get(cameras.label_key(row.label))
                if registered is not None:
                    site.update(registered, located_by="cadastro")
                else:
                    loc = index.locate(cameras.street_address(row.label))
                    site.update(lat=loc.lat, lon=loc.lon, located_by=loc.method, reason=loc.reason)
                sites[key] = site
            site["series"][str(row.year)] = row.values
    published = []
    for key, site in sorted(sites.items()):
        if site.get("lat") is None:
            continue
        loc = Location(float(site["lon"]), float(site["lat"]), str(site["located_by"]), "")
        site["corridors"] = list(counts_build.tag_corridors(loc, buffers, index.crs))
        for corridor in site["corridors"]:
            report.corridor_sites.append(
                {
                    "corridor": corridor,
                    "kind": f"{site['kind']} eletrônico",
                    "name": site["label"],
                    "year": ",".join(sorted(site["series"])),
                    "source_file": "relatorios-mensais",
                }
            )
        site["id"] = hashlib.sha256(key.encode()).hexdigest()[:12]
        published.append(site)
    write_csv(report.reports_dir / "cameras_pdfs.csv", pdf_rows)
    write_csv(
        report.reports_dir / "cameras_sites.csv",
        [
            {
                "label": s["label"],
                "kind": s["kind"],
                "located_by": s.get("located_by", ""),
                "reason": s.get("reason", ""),
                "years": ",".join(sorted(s["series"])),
            }
            for s in sites.values()
        ],
    )
    read_pdfs = [r for r in pdf_rows if r["kind"] != "ignorado"]
    skipped = sum(int(r["rows"] == 0) for r in read_pdfs)
    report.notes.append(
        f"controladores: {len(read_pdfs)} relatórios de fluxo em PDF ({skipped} sem linhas lidas, "
        f"{len(pdf_rows) - len(read_pdfs)} outros PDFs ignorados), "
        f"{len(sites)} equipamentos, {len(published)} localizados"
    )
    report.files["cameras/sites.json"] = write_json(
        out_dir / "cameras" / "sites.json",
        {
            "unit": "UVP (unidade veicular padrão), média dos dias típicos (terça a quinta)",
            "sites": published,
            "source": ATTRIBUTION_EPTC,
        },
    )


ATTRIBUTION_PORTAL = {
    "name": "Portal de dados abertos de Porto Alegre (GTFS)",
    "href": "https://dadosabertos.poa.br/dataset/gtfs",
}


def build_transit(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    feeds = sorted((raw_dir / "gtfs").glob("*.zip"))
    if not feeds:
        raise FileNotFoundError("GTFS ausente em data/raw/gtfs")
    table, day = transit.stops_by_hour(feeds[-1])
    stops = [
        {
            "id": str(row["stop_id"]),
            "name": str(row["stop_name"]),
            "lon": round(float(row["stop_lon"]), 5),
            "lat": round(float(row["stop_lat"]), 5),
            "routes": int(row["routes"]),
            "total": int(row["total"]),
            "hourly": [int(row[h]) for h in range(24)],
        }
        for row in table.to_dict(orient="records")
    ]
    report.notes.append(f"ônibus: {len(stops)} paradas com serviço em {day.isoformat()}")
    report.files["transit/stops.json"] = write_json(
        out_dir / "transit" / "stops.json",
        {"day": day.isoformat(), "stops": stops, "source": ATTRIBUTION_PORTAL},
    )


def _latest(folder: Path, pattern: str) -> Path:
    found = sorted(folder.glob(pattern))
    if not found:
        raise FileNotFoundError(f"{pattern} ausente em {folder}; rode pnpm data:fetch")
    return found[-1]


def build_supply(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    layers = raw_dir / "camadas-eptc"
    out = out_dir / "supply"
    blue = supply.blue_zone(_latest(layers, "AAE_ZONAAZUL_*.zip"))
    report.files["supply/blue_zone.geojson"] = write_geojson(out / "blue_zone.geojson", blue)
    report.files["supply/signals.geojson"] = write_geojson(
        out / "signals.geojson", supply.signals(_latest(layers, "_EPS_CadastroSemaforico_*.zip"))
    )
    report.files["supply/bus_corridors.geojson"] = write_geojson(
        out / "bus_corridors.geojson",
        supply.bus_corridors(_latest(layers, "_CorredoresFaixasExclusivas_*.zip")),
    )
    report.notes.append(
        f"Área Azul: {int(blue['spaces'].sum())} vagas em {len(blue)} faces de quadra"
    )


def build_crashes(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    frame = crashes.read(_latest(raw_dir / "acidentes", "ACIDENTES_TRANSITO_*.zip"))
    cells, summary = crashes.grid(frame)
    report.notes.append(
        f"sinistros: {summary['records']} desde {crashes.FIRST_YEAR}, {len(cells)} células, "
        f"{summary['without_coordinates']} sem coordenadas, "
        f"{summary['outside_city_bounds']} com coordenadas fora da cidade"
    )
    report.files["crashes/grid.json"] = write_json(
        out_dir / "crashes" / "grid.json",
        {
            "cell_metres": crashes.CELL_METRES,
            "fields": ["total", "com feridos", "com vítima grave ou fatal"],
            "cells": cells,
            "summary": summary,
            "source": ATTRIBUTION_EPTC,
        },
    )


def build_bus_gps(raw_dir: Path, out_dir: Path, report: BuildReport) -> None:
    points = bus_gps.read_points(_latest(raw_dir / "centro-bus-gps", "**/BusGPSCentro.zip"))
    centrelines = gpd.read_file(f"zip://{counts_build.centrelines_path(raw_dir)}")
    segments, summary = bus_gps.speeds_by_segment(points, centrelines)
    report.notes.append(
        f"GPS dos ônibus: {summary['points']} pontos, {summary['snapped']} associados a "
        f"{summary['segments']} eixos"
    )
    report.files["bus_gps/segments.geojson"] = write_geojson(
        out_dir / "bus_gps" / "segments.geojson", segments
    )
    report.files["bus_gps/summary.json"] = write_json(
        out_dir / "bus_gps" / "summary.json",
        {
            **summary,
            "moving_kmh": bus_gps.MOVING_KMH,
            "min_points": bus_gps.MIN_POINTS,
            "source": {**ATTRIBUTION_EPTC, "dataset": "Estudo de Mobilidade do Centro Histórico"},
        },
    )


BUILDERS: dict[str, Callable[[Path, Path, BuildReport], None]] = {
    "edom": build_edom,
    "counts": build_counts,
    "speeds": build_speeds,
    "cameras": build_cameras,
    "transit": build_transit,
    "supply": build_supply,
    "crashes": build_crashes,
    "bus_gps": build_bus_gps,
}


def build(raw_dir: Path, out_dir: Path, reports_dir: Path, modules: list[str]) -> BuildReport:
    report = BuildReport(reports_dir)
    for name in modules:
        print(f"── atlas: {name}")
        BUILDERS[name](raw_dir, out_dir, report)
    if report.corridor_sites:
        write_csv(
            report.reports_dir / "focus_corridors.csv",
            sorted(
                report.corridor_sites,
                key=lambda r: (str(r["corridor"]), str(r["kind"]), str(r["year"])),
            ),
        )
        by_corridor: dict[str, int] = {}
        for row in report.corridor_sites:
            by_corridor[str(row["corridor"])] = by_corridor.get(str(row["corridor"]), 0) + 1
        report.notes.append(f"corredores de foco: {by_corridor}")
    report.files["meta.json"] = write_json(
        out_dir / "meta.json",
        {"modules": sorted(modules)},
    )
    return report
