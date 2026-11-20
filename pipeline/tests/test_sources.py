from __future__ import annotations

from pathlib import Path

import pytest

from sim_poa.fetch.sources import SourceError, load

SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources.toml"


def test_repository_sources_are_valid() -> None:
    config = load(SOURCES)
    assert "default" in config.groups
    assert {s.kind for s in config.sources} == {"webdav", "ckan", "url"}
    default_ids = {s.id for s in config.select(["default"])}
    assert {"edom-2023", "pesquisas-fluxo", "centro-bus-gps", "osm-geofabrik-sul"} <= default_ids
    assert "centro-historico" not in default_ids
    assert "edom-2003" not in default_ids


def test_select_rejects_unknown_group_and_source() -> None:
    config = load(SOURCES)
    with pytest.raises(SourceError, match="grupo desconhecido"):
        config.select(["nao-existe"])
    with pytest.raises(SourceError, match="fonte desconhecida"):
        config.select(["default"], ["nao-existe"])


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sources.toml"
    defaults = '[defaults]\nwebdav_base = "https://x/"\nckan_base = "https://y/"\nexclude = []\n\n'
    path.write_text(defaults + body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("", "nenhuma fonte"),
        (
            '[[source]]\nid = "a"\ngroup = "g"\nkind = "ftp"\npublisher = "p"\ndescription = "d"\n',
            "tipo `ftp` desconhecido",
        ),
        (
            '[[source]]\nid = "A b"\ngroup = "g"\nkind = "url"\npublisher = "p"\n'
            'description = "d"\nurl = "https://z"\n',
            "minúsculas",
        ),
        (
            '[[source]]\nid = "a"\ngroup = "g"\nkind = "webdav"\npublisher = "p"\n'
            'description = "d"\nshare = "t"\n',
            "precisa de `share` e `include`",
        ),
        (
            '[[source]]\nid = "a"\ngroup = "g"\nkind = "url"\npublisher = "p"\n'
            'description = "d"\nurl = "http://z"\n',
            "precisa de `url` https",
        ),
        (
            '[[source]]\nid = "a"\ngroup = "g"\nkind = "ckan"\npublisher = "p"\ndescription = "d"\n'
            'dataset = "x"\n\n[[source]]\nid = "a"\ngroup = "g"\nkind = "ckan"\n'
            'publisher = "p"\ndescription = "d"\ndataset = "y"\n',
            "ids repetidos",
        ),
    ],
)
def test_invalid_sources_fail_loudly(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(SourceError, match=message):
        load(_write(tmp_path, body))
