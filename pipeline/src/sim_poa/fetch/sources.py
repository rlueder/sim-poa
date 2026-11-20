"""Leitura e validação de `data/sources.toml`."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Kind = Literal["webdav", "ckan", "url"]
KINDS: tuple[Kind, ...] = ("webdav", "ckan", "url")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class SourceError(ValueError):
    """`sources.toml` inválido."""


@dataclass(frozen=True)
class Source:
    id: str
    group: str
    kind: Kind
    publisher: str
    description: str
    share: str | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    dataset: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Config:
    webdav_base: str
    ckan_base: str
    exclude: tuple[str, ...]
    pause_seconds: float
    sources: tuple[Source, ...] = field(default_factory=tuple)

    @property
    def groups(self) -> list[str]:
        return sorted({s.group for s in self.sources})

    def select(self, groups: list[str], ids: list[str] | None = None) -> list[Source]:
        unknown_groups = set(groups) - set(self.groups)
        if unknown_groups:
            raise SourceError(f"grupo desconhecido: {', '.join(sorted(unknown_groups))}")
        known_ids = {s.id for s in self.sources}
        unknown_ids = set(ids or []) - known_ids
        if unknown_ids:
            raise SourceError(f"fonte desconhecida: {', '.join(sorted(unknown_ids))}")
        if ids:
            return [s for s in self.sources if s.id in ids]
        return [s for s in self.sources if s.group in groups]


def _str(table: dict[str, Any], key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise SourceError(f"{where}: `{key}` precisa ser um texto não vazio")
    return value


def _patterns(table: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise SourceError(f"{where}: `{key}` precisa ser uma lista de textos")
    return tuple(value)


def _source(table: dict[str, Any], index: int) -> Source:
    where = f"source[{index}]"
    source_id = _str(table, "id", where)
    if not _ID_PATTERN.match(source_id):
        raise SourceError(f"{where}: id `{source_id}` deve usar minúsculas, dígitos e hífens")
    where = f"fonte `{source_id}`"
    kind = _str(table, "kind", where)
    if kind not in KINDS:
        raise SourceError(f"{where}: tipo `{kind}` desconhecido")
    source = Source(
        id=source_id,
        group=_str(table, "group", where),
        kind=kind,
        publisher=_str(table, "publisher", where),
        description=_str(table, "description", where),
        share=table.get("share"),
        include=_patterns(table, "include", where),
        exclude=_patterns(table, "exclude", where),
        dataset=table.get("dataset"),
        url=table.get("url"),
    )
    if source.kind == "webdav" and (not source.share or not source.include):
        raise SourceError(f"{where}: fonte webdav precisa de `share` e `include`")
    if source.kind == "ckan" and not source.dataset:
        raise SourceError(f"{where}: fonte ckan precisa de `dataset`")
    if source.kind == "url" and not (source.url and source.url.startswith("https://")):
        raise SourceError(f"{where}: fonte url precisa de `url` https")
    return source


def load(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SourceError(f"{path}: {exc}") from exc
    defaults = data.get("defaults", {})
    tables = data.get("source", [])
    if not isinstance(tables, list) or not tables:
        raise SourceError(f"{path}: nenhuma fonte declarada")
    sources = tuple(_source(t, i) for i, t in enumerate(tables))
    ids = [s.id for s in sources]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise SourceError(f"{path}: ids repetidos: {', '.join(duplicated)}")
    pause = defaults.get("pause_seconds", 1.0)
    if not isinstance(pause, int | float) or pause < 0:
        raise SourceError(f"{path}: `pause_seconds` inválido")
    return Config(
        webdav_base=_str(defaults, "webdav_base", "defaults"),
        ckan_base=_str(defaults, "ckan_base", "defaults"),
        exclude=_patterns(defaults, "exclude", "defaults"),
        pause_seconds=float(pause),
        sources=sources,
    )
