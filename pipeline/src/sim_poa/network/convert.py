"""Conversão do recorte OSM em rede do SUMO com o `netconvert`."""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from sim_poa.network.sumo_env import binary, typemap

# Opções recomendadas pela documentação do SUMO para importar OSM urbano
# (Networks/Import/OpenStreetMap), mais nomes de rua e faixas de conversão.
# Fica de fora `--tls.discard-simple`: ele descarta os semáforos fora de
# cruzamentos, e metade do cadastro da EPTC são semáforos só de pedestres no
# meio da quadra (tipo EXCLUSIVO), que param os carros do mesmo jeito.
NETCONVERT_OPTIONS = [
    "--geometry.remove",
    "--ramps.guess",
    "--junctions.join",
    "--tls.guess-signals",
    "--tls.join",
    "--tls.default-type",
    "actuated",
    "--osm.turn-lanes",
    "--output.street-names",
    "--output.original-names",
    "--osm.sidewalks",
    "false",
    "--remove-edges.isolated",
    "--keep-edges.by-vclass",
    "passenger,bus,truck",
    "--proj.utm",
]


@dataclass
class ConvertResult:
    net: Path
    warnings: list[str] = field(default_factory=list)

    def warning_kinds(self) -> dict[str, int]:
        """Avisos agrupados pelo texto, sem os identificadores de aresta e nó."""
        kinds: dict[str, int] = {}
        for line in self.warnings:
            kind = re.sub(r"'[^']*'", "'…'", line)
            kind = re.sub(r"-?\d+(?:#\d+)?(?:\.\d+)?", "N", kind)
            # Listas de nós ("12,34,56") viram uma só forma, de qualquer tamanho.
            kind = re.sub(r"N(?:,N)+", "N,…", kind)
            kinds[kind] = kinds.get(kind, 0) + 1
        return dict(sorted(kinds.items(), key=lambda kv: -kv[1]))


def write_typemap(path: Path, speeds_kmh: dict[str, float]) -> Path:
    """Cópia do typemap padrão do SUMO para OSM, com as velocidades padrão brasileiras.

    As velocidades só valem quando a via não tem `maxspeed` no OSM.
    """
    tree = ET.parse(typemap("osmNetconvert.typ.xml"))
    for element in tree.getroot().iter("type"):
        highway = element.get("id", "").removeprefix("highway.")
        if highway in speeds_kmh:
            element.set("speed", f"{speeds_kmh[highway] / 3.6:.2f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def netconvert(osm_xml: Path, typemap_file: Path, output: Path) -> ConvertResult:
    output.parent.mkdir(parents=True, exist_ok=True)
    log = output.with_suffix(".warnings.log")
    subprocess.run(
        [
            binary("netconvert"),
            "--osm-files",
            str(osm_xml),
            "--type-files",
            str(typemap_file),
            *NETCONVERT_OPTIONS,
            "--output-file",
            str(output),
            "--error-log",
            str(log),
            # Sem isto o SUMO lista só os cinco primeiros avisos de cada tipo.
            "--aggregate-warnings",
            "-1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    warnings = [
        line.removeprefix("Warning: ").strip()
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("Warning:")
    ]
    return ConvertResult(output, warnings)


def set_signals(net: Path, output: Path, add: list[str], remove: list[str]) -> Path:
    """Segunda passada sobre a rede pronta: liga e desliga semáforos por id de nó."""
    command = [binary("netconvert"), "--sumo-net-file", str(net), "--output-file", str(output)]
    if add:
        command += ["--tls.set", ",".join(add), "--tls.default-type", "actuated"]
    if remove:
        command += ["--tls.unset", ",".join(remove)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output
