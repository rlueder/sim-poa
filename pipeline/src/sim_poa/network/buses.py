"""Ônibus do GTFS na rede: paradas, linhas e viagens de um dia, com o `gtfs2pt.py` do SUMO."""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from sim_poa.atlas import transit
from sim_poa.network.checks import parse_statistics
from sim_poa.network.sumo_env import binary, run_tool, sumo_home, tools_dir


def _clock(seconds: pd.Series) -> pd.Series:
    """Segundos como HH:MM:SS; o GTFS admite horas acima de 24 para depois da meia-noite."""
    total = seconds.round().astype(int)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return (
        hours.astype(str).str.zfill(2)
        + ":"
        + minutes.astype(str).str.zfill(2)
        + ":"
        + secs.astype(str).str.zfill(2)
    )


def complete_feed(source: Path, target: Path, day: dt.date) -> int:
    """Copia o GTFS com os horários de todas as paradas das viagens do dia.

    O GTFS de Porto Alegre só dá horário nos pontos de controle; as paradas do
    meio ficam em branco, e o `gtfs2pt.py` não aceita horário vazio. O horário
    que falta é interpolado pela ordem da parada, como no atlas (fase 1). As
    viagens que não rodam no dia ficam de fora, o que encolhe o arquivo.
    Devolve o número de viagens gravadas.
    """
    with zipfile.ZipFile(source) as feed:
        services = transit.active_services(feed, day)
        trips = pd.read_csv(feed.open("trips.txt"), dtype=str)
        trips = trips[trips["service_id"].isin(services)]
        times = pd.read_csv(feed.open("stop_times.txt"), dtype=str, keep_default_na=False)
        times = times[times["trip_id"].isin(trips["trip_id"])].copy()
        times["seq"] = times["stop_sequence"].astype(int)
        times = times.sort_values(["trip_id", "seq"])
        seconds = transit._seconds(times["departure_time"].replace("", None))
        seconds = seconds.groupby(times["trip_id"]).transform(
            lambda s: s.interpolate(limit_area="inside")
        )
        times = times[seconds.notna()].copy()
        clock = _clock(seconds[seconds.notna()])
        times["arrival_time"] = times["arrival_time"].where(times["arrival_time"] != "", clock)
        times["departure_time"] = times["departure_time"].where(
            times["departure_time"] != "", clock
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
            for name in feed.namelist():
                if name == "stop_times.txt":
                    data = times.drop(columns="seq").to_csv(index=False).encode("utf-8")
                elif name == "trips.txt":
                    data = trips.to_csv(index=False).encode("utf-8")
                else:
                    data = feed.read(name)
                # Data fixa: o mesmo GTFS dá o mesmo zip, e o hash dele serve de chave do cache.
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                out.writestr(entry, data)
    return int(times["trip_id"].nunique())


@dataclass
class BusImport:
    routes: Path
    stops: Path
    vtypes: Path
    vehicles: int
    lines: int
    bus_stops: int
    warnings: list[str]
    detours: list[str]
    holds_removed: int

    def summary(self) -> dict[str, object]:
        return {
            "vehicles": self.vehicles,
            "lines": self.lines,
            "bus_stops": self.bus_stops,
            "warnings": len(self.warnings),
            "detours": len(self.detours),
            "holds_removed": self.holds_removed,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _network_digest(net: Path) -> str:
    """Hash do conteúdo da rede, sem o comentário de cabeçalho.

    O `netconvert` grava a hora da geração e os caminhos no comentário inicial,
    e o gzip guarda a hora também; com eles, cada build teria um hash novo e o
    cache dos ônibus nunca seria usado.
    """
    with gzip.open(net, "rt", encoding="utf-8") as handle:
        text = handle.read()
    start = text.find("<!--")
    end = text.find("-->", start)
    if start != -1 and end != -1:
        text = text[:start] + text[end + 3 :]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lines(path: Path) -> list[str]:
    return (
        [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        if path.exists()
        else []
    )


def _read_result(folder: Path) -> BusImport:
    routes, stops = folder / "onibus.rou.xml", folder / "paradas.add.xml"
    vehicles = ET.parse(routes).getroot().findall("vehicle")
    holds = _lines(folder / "prazos-removidos.txt")
    return BusImport(
        routes=routes,
        stops=stops,
        vtypes=folder / "tipos.add.xml",
        vehicles=len(vehicles),
        lines=len({v.get("line", "") for v in vehicles}),
        bus_stops=len(ET.parse(stops).getroot().findall("busStop")),
        warnings=_lines(folder / "avisos.txt"),
        detours=_lines(folder / "desvios.txt"),
        holds_removed=int(holds[0]) if holds else 0,
    )


def drop_holds(routes: Path) -> int:
    """Tira os `until` das paradas: o ônibus sai no horário e depois segue o trânsito.

    O `gtfs2pt.py` grava em cada rota os horários de uma única viagem, como
    prazo mínimo de saída de cada parada, e a rota é compartilhada por todas as
    viagens com a mesma sequência de paradas. No GTFS de Porto Alegre esses
    horários só existem nos pontos de controle; os outros foram interpolados
    (`complete_feed`). Um ônibus adiantado ficava parado esperando um horário
    que ninguém publicou e, no modo mesoscópico, travava os de trás. Devolve o
    número de prazos removidos.
    """
    text = routes.read_text(encoding="utf-8")
    cleaned, removed = re.subn(r' until="[0-9.]+"', "", text)
    routes.write_text(cleaned, encoding="utf-8")
    return removed


def import_buses(net: Path, feed: Path, day: dt.date, folder: Path) -> BusImport:
    """Roda o `gtfs2pt.py` sobre a rede, no diretório `folder`, onde ele grava os rastros.

    O `gtfs2pt.py` casa cada sequência de paradas com a rede rota a rota, em
    Python: na quarta-feira de 29/10/2025 foram 524 sequências distintas e uns
    50 minutos.
    O resultado fica numa subpasta com o hash da rede e do GTFS do dia, e uma
    build seguinte com os mesmos dois arquivos o reaproveita.
    """
    key = f"{_network_digest(net)[:12]}-{_sha256(feed)[:12]}"
    target = folder / key
    if (target / "concluido").exists():
        return _read_result(target)
    target.mkdir(parents=True, exist_ok=True)
    script = tools_dir() / "import" / "gtfs" / "gtfs2pt.py"
    result = run_tool(
        [
            sys.executable,
            str(script),
            "--network",
            str(net),
            "--gtfs",
            str(feed),
            "--date",
            day.strftime("%Y%m%d"),
            "--modes",
            "bus",
            "--route-output",
            str(target / "onibus.rou.xml"),
            "--additional-output",
            str(target / "paradas.add.xml"),
            "--vtype-output",
            str(target / "tipos.add.xml"),
            "--warn-unmapped",
            "--fcd",
            str(target / "fcd"),
            "--map-output",
            str(target / "map"),
        ],
        cwd=target,
        env={**os.environ, "SUMO_HOME": str(sumo_home())},
    )
    # Desvios ("detour (factor N)") saem só no stderr: uma parada casada numa
    # aresta que obriga o ônibus a dar a volta para chegar à seguinte.
    log = result.stdout.splitlines() + result.stderr.splitlines()
    detours = [line for line in log if "detour (factor" in line]
    (target / "desvios.txt").write_text("\n".join(detours), encoding="utf-8")
    # Paradas que não couberam na rota, linhas sem rota e afins: "Warning! ...".
    warnings = [line for line in log if line.startswith("Warning!")]
    (target / "avisos.txt").write_text("\n".join(warnings), encoding="utf-8")
    holds = drop_holds(target / "onibus.rou.xml")
    (target / "prazos-removidos.txt").write_text(str(holds), encoding="utf-8")
    (target / "concluido").touch()
    return _read_result(target)


def run_day(net: Path, buses: BusImport) -> dict[str, Any]:
    """Só os ônibus, o dia inteiro, em modo mesoscópico; conta teletransportes.

    Sem carros, um teletransporte aponta defeito de rede ou de parada, não
    congestionamento. A simulação vai até as 30h para as viagens da madrugada.
    """
    result = run_tool(
        [
            binary("sumo"),
            "--net-file",
            str(net),
            "--route-files",
            str(buses.routes),
            "--additional-files",
            f"{buses.vtypes},{buses.stops}",
            "--mesosim",
            "--end",
            str(30 * 3600),
            "--no-step-log",
            "--no-warnings",
            "--duration-log.statistics",
            "--seed",
            "42",
        ]
    )
    return parse_statistics(result.stdout + result.stderr)
