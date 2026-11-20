from __future__ import annotations

import pytest

from sim_poa.fetch.remote import RemoteError, matches, parse_propfind, safe_relative_path

PROPFIND = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response><d:href>/public.php/webdav/</d:href><d:propstat><d:prop>
    <d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
  <d:response><d:href>/public.php/webdav/Ve%C3%ADculos/</d:href><d:propstat><d:prop>
    <d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
  <d:response><d:href>/public.php/webdav/Ve%C3%ADculos/(VE%C3%8DCULOS)%202018-03%20A.xlsx</d:href>
    <d:propstat><d:prop>
      <d:getlastmodified>Thu, 19 Nov 2026 16:51:23 GMT</d:getlastmodified>
      <d:getcontentlength>11665</d:getcontentlength>
      <d:resourcetype/><d:getetag>"abc"</d:getetag>
    </d:prop></d:propstat></d:response>
</d:multistatus>"""


def test_parse_propfind_returns_files_only_with_validators() -> None:
    [entry] = parse_propfind(PROPFIND)
    assert entry.path == "Veículos/(VEÍCULOS) 2018-03 A.xlsx"
    assert entry.size == 11665
    assert entry.etag == '"abc"'
    assert entry.last_modified == "Thu, 19 Nov 2026 16:51:23 GMT"


def test_parse_propfind_rejects_foreign_href() -> None:
    body = PROPFIND.replace(b"/public.php/webdav/Ve%C3%ADculos/(", b"/outro/(")
    with pytest.raises(RemoteError, match="href inesperado"):
        parse_propfind(body)


@pytest.mark.parametrize("path", ["../segredo", "a/../../b", "a//b", "", "a\\b", "./a"])
def test_safe_relative_path_rejects_escapes(path: str) -> None:
    with pytest.raises(RemoteError):
        safe_relative_path(path)


def test_safe_relative_path_normalises_to_nfc() -> None:
    decomposed = "Véiculos"  # "é" decomposto, como o macOS às vezes grava
    assert safe_relative_path(decomposed) == "Véiculos"


def test_matches_uses_include_then_exclude() -> None:
    include = ("EDOM 2023/*", "raiz.zip")
    exclude = ("*Thumbs.db",)
    assert matches("EDOM 2023/sub/arquivo.xlsx", include, exclude)
    assert matches("raiz.zip", include, exclude)
    assert not matches("EDOM 2023/Thumbs.db", include, exclude)
    assert not matches("EDOM_2003/arquivo.xls", include, exclude)
