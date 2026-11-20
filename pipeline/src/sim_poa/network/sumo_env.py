"""Acesso às ferramentas do SUMO instalado pelo pacote eclipse-sumo."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import sumo


def sumo_home() -> Path:
    return Path(sumo.SUMO_HOME)


def tools_dir() -> Path:
    return sumo_home() / "tools"


def use_sumolib() -> None:
    """Põe `tools/` no caminho de importação, onde o pacote guarda o sumolib."""
    tools = str(tools_dir())
    if tools not in sys.path:
        sys.path.append(tools)
    os.environ.setdefault("SUMO_HOME", str(sumo_home()))


def binary(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise FileNotFoundError(f"`{name}` não está no PATH; rode com `uv run`")
    return found


def typemap(name: str) -> Path:
    return sumo_home() / "data" / "typemap" / name
