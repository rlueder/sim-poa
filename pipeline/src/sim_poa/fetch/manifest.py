"""`data/manifest.csv`: um registro por arquivo baixado.

O manifesto é versionado. Ele diz exatamente quais versões dos arquivos
alimentaram uma execução, já que as pastas da EPTC continuam recebendo
arquivos novos e substituindo antigos.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from pathlib import Path

Key = tuple[str, str]


@dataclass(frozen=True)
class Entry:
    source: str
    path: str
    url: str
    size: int
    sha256: str
    etag: str
    last_modified: str
    downloaded_at: str

    @property
    def key(self) -> Key:
        return (self.source, self.path)


COLUMNS = [f.name for f in fields(Entry)]


def read(path: Path) -> dict[Key, Entry]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{path}: colunas inesperadas {reader.fieldnames}")
        entries = [Entry(**{**row, "size": int(row["size"])}) for row in reader]  # type: ignore[arg-type]
    return {e.key: e for e in entries}


def write(path: Path, entries: dict[Key, Entry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for key in sorted(entries):
            writer.writerow(asdict(entries[key]))
    tmp.replace(path)
