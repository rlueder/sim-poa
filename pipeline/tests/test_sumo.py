"""Confirma que o SUMO instalado pelo uv é a versão fixada e que converte OSM."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SUMO_VERSION = "1.28.0"
FIXTURE = Path(__file__).parent / "fixtures" / "cruzamento.osm.xml"

pytestmark = pytest.mark.sumo


def _binary(name: str) -> str:
    path = shutil.which(name)
    assert path, f"`{name}` não está no PATH; rode os testes com `uv run`"
    return path


def test_sumo_version_is_pinned() -> None:
    result = subprocess.run(
        [_binary("sumo"), "--version"], capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines()[0] == f"Eclipse SUMO sumo {SUMO_VERSION}"


def test_netconvert_builds_a_network_from_osm(tmp_path: Path) -> None:
    net = tmp_path / "cruzamento.net.xml"
    subprocess.run(
        [
            _binary("netconvert"),
            "--osm-files",
            str(FIXTURE),
            "--output-file",
            str(net),
            "--geometry.remove",
            "--junctions.join",
            "--output.street-names",
            "--no-warnings",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    edges = [e for e in ET.parse(net).getroot().iter("edge") if e.get("function") != "internal"]
    names = {e.get("name") for e in edges}
    assert names == {"Rua de Teste", "Travessa de Teste"}
    # A rua de mão dupla gera arestas nos dois sentidos; a de mão única, só em um.
    one_way = [e for e in edges if e.get("name") == "Travessa de Teste"]
    two_way = [e for e in edges if e.get("name") == "Rua de Teste"]
    assert all(e.get("id", "").startswith("102") for e in one_way)
    assert not any(e.get("id", "").startswith("-102") for e in one_way)
    assert any(e.get("id", "").startswith("-101") for e in two_way)
