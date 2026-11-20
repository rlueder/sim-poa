"""Execução do download: compara o remoto com o manifesto e baixa o que mudou."""

from __future__ import annotations

import functools
import hashlib
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from sim_poa.fetch import manifest
from sim_poa.fetch.remote import RemoteError, RemoteFile, list_source, request
from sim_poa.fetch.sources import Config, Source

CHUNK = 1 << 20
RETRY_DELAYS = (5.0, 15.0)
SAVE_EVERY = 25


class Action(Enum):
    SKIP = "skip"
    NEW = "new"
    CHANGED = "changed"
    MISSING_LOCAL = "missing-local"
    ADOPT = "adopt"


@dataclass
class Summary:
    downloaded: int = 0
    skipped: int = 0
    adopted: int = 0
    changed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    not_in_manifest: list[str] = field(default_factory=list)
    gone_remote: list[str] = field(default_factory=list)
    bytes: int = 0

    @property
    def ok(self) -> bool:
        return not self.failed


def _same_version(remote: RemoteFile, entry: manifest.Entry) -> bool:
    if remote.etag and entry.etag:
        return remote.etag == entry.etag
    return remote.last_modified == entry.last_modified and remote.size == entry.size


def decide(remote: RemoteFile, entry: manifest.Entry | None, local: Path) -> Action:
    if entry is None:
        # Arquivo já presente sem registro (baixado de outra worktree): basta
        # calcular o hash, desde que o tamanho bata com o do servidor.
        if remote.size is not None and local.is_file() and local.stat().st_size == remote.size:
            return Action.ADOPT
        return Action.NEW
    if not _same_version(remote, entry):
        return Action.CHANGED
    if not local.is_file() or local.stat().st_size != entry.size:
        return Action.MISSING_LOCAL
    return Action.SKIP


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _download(remote: RemoteFile, target: Path) -> tuple[str, int]:
    headers = {"Authorization": remote.auth_header} if remote.auth_header else {}
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with (
            urllib.request.urlopen(request(remote.url, headers=headers), timeout=120) as resp,
            part.open("wb") as out,
        ):
            while chunk := resp.read(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        part.unlink(missing_ok=True)
        raise RemoteError(f"GET {remote.url}: {exc}") from exc
    if remote.size is not None and size != remote.size:
        part.unlink(missing_ok=True)
        raise RemoteError(f"{remote.path}: recebidos {size} bytes, esperados {remote.size}")
    part.replace(target)
    return digest.hexdigest(), size


def _with_retries[T](action: Callable[[], T], sleep: Callable[[float], None]) -> T:
    for delay in RETRY_DELAYS:
        try:
            return action()
        except RemoteError as exc:
            print(f"  tentativa falhou ({exc}); nova tentativa em {delay:.0f} s")
            sleep(delay)
    return action()


def _entry(remote: RemoteFile, sha256: str, size: int) -> manifest.Entry:
    return manifest.Entry(
        source=remote.source_id,
        path=remote.path,
        url=remote.url,
        size=size,
        sha256=sha256,
        etag=remote.etag or "",
        last_modified=remote.last_modified or "",
        downloaded_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def local_path(raw_dir: Path, remote: RemoteFile) -> Path:
    target = (raw_dir / remote.source_id / remote.path).resolve()
    if not target.is_relative_to(raw_dir.resolve()):
        raise RemoteError(f"caminho fora do diretório de dados: {remote.path!r}")
    return target


def run(
    config: Config,
    sources: list[Source],
    raw_dir: Path,
    manifest_path: Path,
    *,
    frozen: bool = False,
    dry_run: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> Summary:
    entries = manifest.read(manifest_path)
    summary = Summary()
    pending_saves = 0

    def save() -> None:
        nonlocal pending_saves
        if not dry_run:
            manifest.write(manifest_path, entries)
        pending_saves = 0

    try:
        for source in sources:
            print(f"── {source.id}: {source.description}")
            try:
                remotes = _with_retries(functools.partial(list_source, config, source), sleep)
            except RemoteError as exc:
                summary.failed.append(f"{source.id}: {exc}")
                print(f"  falhou a listagem: {exc}")
                continue
            listed = {r.path for r in remotes}
            summary.gone_remote += [
                f"{source.id}/{path}"
                for (sid, path) in entries
                if sid == source.id and path not in listed
            ]
            size_total = sum(r.size or 0 for r in remotes)
            print(f"  {len(remotes)} arquivos, {size_total / 1e6:,.1f} MB no servidor")

            for remote in remotes:
                label = f"{source.id}/{remote.path}"
                try:
                    target = local_path(raw_dir, remote)
                except RemoteError as exc:
                    summary.failed.append(str(exc))
                    continue
                entry = entries.get((source.id, remote.path))
                action = decide(remote, entry, target)

                if action is Action.SKIP:
                    summary.skipped += 1
                    continue
                if frozen and action in (Action.NEW, Action.ADOPT):
                    summary.not_in_manifest.append(label)
                    continue
                if action is Action.CHANGED:
                    summary.changed.append(label)
                    if frozen:
                        summary.failed.append(f"{label}: mudou no servidor desde o manifesto")
                        continue
                if dry_run:
                    print(f"  [simulação] {action.value}: {remote.path}")
                    continue
                if action is Action.ADOPT:
                    entries[(source.id, remote.path)] = _entry(
                        remote, _hash_file(target), target.stat().st_size
                    )
                    summary.adopted += 1
                else:
                    try:
                        sha, size = _with_retries(
                            functools.partial(_download, remote, target), sleep
                        )
                    except RemoteError as exc:
                        summary.failed.append(str(exc))
                        print(f"  falhou: {exc}")
                        continue
                    if frozen and entry is not None and sha != entry.sha256:
                        summary.failed.append(f"{label}: SHA-256 diferente do manifesto")
                        continue
                    entries[(source.id, remote.path)] = _entry(remote, sha, size)
                    summary.downloaded += 1
                    summary.bytes += size
                    print(f"  ↓ {remote.path} ({size / 1e6:,.1f} MB)")
                    sleep(config.pause_seconds)
                pending_saves += 1
                if pending_saves >= SAVE_EVERY:
                    save()
    finally:
        save()
    return summary
