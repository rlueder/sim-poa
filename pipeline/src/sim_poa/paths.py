"""Localização do repositório e do diretório de dados brutos."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

DATA_DIR_ENV = "SIM_POA_DATA_DIR"


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def repo_root(start: Path | None = None) -> Path:
    """Raiz da worktree atual, onde ficam `data/sources.toml` e o manifesto."""
    here = start or Path(__file__).resolve().parent
    return Path(_git("rev-parse", "--show-toplevel", cwd=here))


def main_worktree_root(start: Path | None = None) -> Path:
    """Raiz da worktree principal.

    Os dados brutos ficam nela para que todas as worktrees compartilhem uma
    cópia só, em vez de baixar alguns GB por branch.
    """
    here = start or Path(__file__).resolve().parent
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=here)
    return Path(common).parent


def raw_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return main_worktree_root() / "data" / "raw"
