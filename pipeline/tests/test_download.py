from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from sim_poa.fetch import manifest
from sim_poa.fetch.download import run
from sim_poa.fetch.sources import Config, Source

from .conftest import WEBDAV_ROOT, FakeServer


def _config(server: FakeServer, *sources: Source) -> Config:
    return Config(
        webdav_base=server.base + WEBDAV_ROOT,
        ckan_base=server.base + "/api/3/action/",
        exclude=("*Thumbs.db",),
        pause_seconds=0,
        sources=sources,
    )


def _webdav() -> Source:
    return Source(
        id="compartilhamento",
        group="default",
        kind="webdav",
        publisher="EPTC",
        description="teste",
        share="token",
        include=("Veículos/*",),
    )


def _url(server: FakeServer) -> Source:
    return Source(
        id="arquivo",
        group="default",
        kind="url",
        publisher="OSM",
        description="teste",
        url=server.base + "/osm/PortoAlegre.osm.pbf",
    )


def _no_sleep(_: float) -> None:
    return


@pytest.fixture
def populated(fake_server: FakeServer) -> FakeServer:
    fake_server.put(f"{WEBDAV_ROOT}Veículos/contagem 1.xlsx", b"um", "e1")
    fake_server.put(f"{WEBDAV_ROOT}Veículos/sub/contagem 2.xls", b"dois", "e2")
    fake_server.put(f"{WEBDAV_ROOT}Veículos/Thumbs.db", b"lixo", "e3")
    fake_server.put(f"{WEBDAV_ROOT}Velocidade/fora.xlsx", b"fora", "e4")
    fake_server.put("/osm/PortoAlegre.osm.pbf", b"pbf", "e5")
    return fake_server


def test_first_run_downloads_and_second_run_downloads_nothing(
    populated: FakeServer, tmp_path: Path
) -> None:
    config = _config(populated, _webdav(), _url(populated))
    raw, man = tmp_path / "raw", tmp_path / "manifest.csv"

    first = run(config, list(config.sources), raw, man, sleep=_no_sleep)
    assert first.ok
    assert first.downloaded == 3
    assert (
        raw / "compartilhamento" / "Veículos" / "sub" / "contagem 2.xls"
    ).read_bytes() == b"dois"
    assert not (raw / "compartilhamento" / "Veículos" / "Thumbs.db").exists()

    rows = manifest.read(man)
    assert len(rows) == 3
    row = rows[("arquivo", "PortoAlegre.osm.pbf")]
    assert row.sha256 == hashlib.sha256(b"pbf").hexdigest()
    assert row.size == 3
    assert row.etag == '"e5"'

    downloads_before = populated.downloads()
    manifest_before = man.read_text(encoding="utf-8")
    second = run(config, list(config.sources), raw, man, sleep=_no_sleep)
    assert second.ok
    assert (second.downloaded, second.skipped) == (0, 3)
    assert populated.downloads() == downloads_before
    assert man.read_text(encoding="utf-8") == manifest_before


def test_changed_file_is_downloaded_again_and_reported(
    populated: FakeServer, tmp_path: Path
) -> None:
    config = _config(populated, _webdav())
    raw, man = tmp_path / "raw", tmp_path / "manifest.csv"
    run(config, list(config.sources), raw, man, sleep=_no_sleep)

    populated.put(f"{WEBDAV_ROOT}Veículos/contagem 1.xlsx", b"um, revisado", "e1b")
    summary = run(config, list(config.sources), raw, man, sleep=_no_sleep)

    assert summary.changed == ["compartilhamento/Veículos/contagem 1.xlsx"]
    assert summary.downloaded == 1
    assert (
        raw / "compartilhamento" / "Veículos" / "contagem 1.xlsx"
    ).read_bytes() == b"um, revisado"


def test_frozen_fails_on_change_and_ignores_new_files(
    populated: FakeServer, tmp_path: Path
) -> None:
    config = _config(populated, _webdav())
    raw, man = tmp_path / "raw", tmp_path / "manifest.csv"
    run(config, list(config.sources), raw, man, sleep=_no_sleep)
    before = man.read_text(encoding="utf-8")

    populated.put(f"{WEBDAV_ROOT}Veículos/contagem 1.xlsx", b"outro", "novo")
    populated.put(f"{WEBDAV_ROOT}Veículos/contagem 3.xlsx", b"tres", "e9")
    summary = run(config, list(config.sources), raw, man, frozen=True, sleep=_no_sleep)

    assert not summary.ok
    assert summary.not_in_manifest == ["compartilhamento/Veículos/contagem 3.xlsx"]
    assert summary.downloaded == 0
    assert man.read_text(encoding="utf-8") == before


def test_deleted_local_file_is_restored(populated: FakeServer, tmp_path: Path) -> None:
    config = _config(populated, _url(populated))
    raw, man = tmp_path / "raw", tmp_path / "manifest.csv"
    run(config, list(config.sources), raw, man, sleep=_no_sleep)
    (raw / "arquivo" / "PortoAlegre.osm.pbf").unlink()

    summary = run(config, list(config.sources), raw, man, sleep=_no_sleep)
    assert summary.downloaded == 1
    assert (raw / "arquivo" / "PortoAlegre.osm.pbf").read_bytes() == b"pbf"


def test_file_present_without_manifest_row_is_adopted(
    populated: FakeServer, tmp_path: Path
) -> None:
    # Situação de duas worktrees: os dados brutos são compartilhados, mas o
    # manifesto desta worktree ainda não registra o arquivo.
    config = _config(populated, _url(populated))
    raw, man = tmp_path / "raw", tmp_path / "manifest.csv"
    target = raw / "arquivo" / "PortoAlegre.osm.pbf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"pbf")

    summary = run(config, list(config.sources), raw, man, sleep=_no_sleep)
    assert (summary.adopted, summary.downloaded) == (1, 0)
    assert (
        manifest.read(man)[("arquivo", "PortoAlegre.osm.pbf")].sha256
        == hashlib.sha256(b"pbf").hexdigest()
    )


def test_listing_failure_is_reported_not_skipped(fake_server: FakeServer, tmp_path: Path) -> None:
    missing = Source(
        id="sumiu",
        group="default",
        kind="url",
        publisher="x",
        description="teste",
        url=fake_server.base + "/nao/existe.zip",
    )
    config = _config(fake_server, missing)
    summary = run(config, [missing], tmp_path / "raw", tmp_path / "m.csv", sleep=_no_sleep)
    assert not summary.ok
    assert summary.failed and summary.failed[0].startswith("sumiu:")


def test_dry_run_writes_nothing(populated: FakeServer, tmp_path: Path) -> None:
    config = _config(populated, _webdav())
    raw, man = tmp_path / "raw", tmp_path / "manifest.csv"
    summary = run(config, list(config.sources), raw, man, dry_run=True, sleep=_no_sleep)
    assert summary.ok
    assert summary.downloaded == 0
    assert not man.exists()
    assert not raw.exists()
