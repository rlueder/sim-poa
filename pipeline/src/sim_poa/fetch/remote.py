"""Listagem dos arquivos remotos de cada fonte.

Cada fonte vira uma lista de `RemoteFile` com os validadores HTTP (tamanho,
ETag, Last-Modified) que o servidor informa. É com eles que um segundo
download do mesmo arquivo é evitado.
"""

from __future__ import annotations

import base64
import fnmatch
import json
import posixpath
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from sim_poa import __version__
from sim_poa.fetch.sources import Config, Source

USER_AGENT = f"sim-poa/{__version__} (+https://github.com/rlueder/sim-poa)"
TIMEOUT_SECONDS = 120
_DAV = {"d": "DAV:"}
_WEBDAV_ROOT = "/public.php/webdav/"


class RemoteError(RuntimeError):
    """Falha ao listar ou consultar uma fonte."""


@dataclass(frozen=True)
class RemoteFile:
    source_id: str
    path: str
    url: str
    size: int | None
    etag: str | None
    last_modified: str | None
    auth_header: str | None = None


@dataclass(frozen=True)
class DavEntry:
    path: str
    size: int | None
    etag: str | None
    last_modified: str | None


def request(
    url: str, method: str = "GET", headers: dict[str, str] | None = None
) -> urllib.request.Request:
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    return urllib.request.Request(url, method=method, headers=merged)


def basic_auth(share: str) -> str:
    # Compartilhamentos públicos do Nextcloud usam o token como usuário e senha vazia.
    token = base64.b64encode(f"{share}:".encode()).decode()
    return f"Basic {token}"


def safe_relative_path(path: str) -> str:
    """Normaliza um caminho vindo do servidor e recusa os que escapam da pasta."""
    normalized = unicodedata.normalize("NFC", path).strip("/")
    parts = normalized.split("/")
    if not normalized or any(p in ("", ".", "..") for p in parts) or "\\" in normalized:
        raise RemoteError(f"caminho remoto inválido: {path!r}")
    return normalized


def matches(path: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in include) and not any(
        fnmatch.fnmatchcase(path, p) for p in exclude
    )


def parse_propfind(body: bytes) -> list[DavEntry]:
    """Arquivos (não pastas) de uma resposta PROPFIND, com caminho relativo à raiz."""
    root = ET.fromstring(body)
    entries: list[DavEntry] = []
    for response in root.findall("d:response", _DAV):
        if response.find(".//d:resourcetype/d:collection", _DAV) is not None:
            continue
        href = urllib.parse.unquote(response.findtext("d:href", "", _DAV))
        if _WEBDAV_ROOT not in href:
            raise RemoteError(f"href inesperado na listagem: {href!r}")
        size_text = response.findtext(".//d:getcontentlength", "", _DAV)
        entries.append(
            DavEntry(
                path=safe_relative_path(href.split(_WEBDAV_ROOT, 1)[1]),
                size=int(size_text) if size_text else None,
                etag=response.findtext(".//d:getetag", None, _DAV),
                last_modified=response.findtext(".//d:getlastmodified", None, _DAV),
            )
        )
    return entries


def _read(req: urllib.request.Request) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body: bytes = resp.read()
            return body
    except OSError as exc:
        raise RemoteError(f"{req.get_method()} {req.full_url}: {exc}") from exc


def list_webdav(config: Config, source: Source) -> list[RemoteFile]:
    assert source.share is not None
    auth = basic_auth(source.share)
    body = _read(
        request(config.webdav_base, "PROPFIND", {"Depth": "infinity", "Authorization": auth})
    )
    exclude = source.exclude + config.exclude
    return [
        RemoteFile(
            source_id=source.id,
            path=entry.path,
            url=config.webdav_base + urllib.parse.quote(entry.path),
            size=entry.size,
            etag=entry.etag,
            last_modified=entry.last_modified,
            auth_header=auth,
        )
        for entry in parse_propfind(body)
        if matches(entry.path, source.include, exclude)
    ]


def head(source_id: str, path: str, url: str) -> RemoteFile:
    try:
        with urllib.request.urlopen(request(url, "HEAD"), timeout=TIMEOUT_SECONDS) as resp:
            length = resp.headers.get("Content-Length")
            return RemoteFile(
                source_id=source_id,
                path=path,
                url=url,
                size=int(length) if length else None,
                etag=resp.headers.get("ETag"),
                last_modified=resp.headers.get("Last-Modified"),
            )
    except OSError as exc:
        raise RemoteError(f"HEAD {url}: {exc}") from exc


def _filename(url: str) -> str:
    return posixpath.basename(urllib.parse.unquote(urllib.parse.urlparse(url).path))


def list_url(source: Source) -> list[RemoteFile]:
    assert source.url is not None
    return [head(source.id, safe_relative_path(_filename(source.url)), source.url)]


def list_ckan(config: Config, source: Source) -> list[RemoteFile]:
    assert source.dataset is not None
    query = urllib.parse.urlencode({"id": source.dataset})
    payload: dict[str, Any] = json.loads(_read(request(f"{config.ckan_base}package_show?{query}")))
    if not payload.get("success"):
        raise RemoteError(f"CKAN recusou o conjunto `{source.dataset}`")
    files: list[RemoteFile] = []
    seen: set[str] = set()
    for resource in payload["result"]["resources"]:
        url = resource["url"]
        name = _filename(url)
        if name in seen:
            name = f"{resource['id']}-{name}"
        seen.add(name)
        files.append(head(source.id, safe_relative_path(name), url))
    return files


def list_source(config: Config, source: Source) -> list[RemoteFile]:
    if source.kind == "webdav":
        return list_webdav(config, source)
    if source.kind == "ckan":
        return list_ckan(config, source)
    return list_url(source)
