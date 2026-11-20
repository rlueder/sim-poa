"""Acesso às ferramentas do SUMO instalado pelo pacote eclipse-sumo."""

from __future__ import annotations

import os
import shutil
import subprocess
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


class ToolError(RuntimeError):
    """Uma ferramenta do SUMO terminou com erro; a mensagem traz o fim da saída dela."""


def run_tool(
    command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Roda uma ferramenta do SUMO e, se falhar, mostra o que ela escreveu.

    Com `capture_output`, um `check=True` simples esconderia a mensagem do SUMO
    atrás de um "returned non-zero exit status".
    """
    result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=cwd, env=env)
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip().splitlines()[-20:]
        name = Path(command[1] if command[0] == sys.executable else command[0]).name
        raise ToolError(f"{name} falhou (código {result.returncode}):\n" + "\n".join(output))
    return result
