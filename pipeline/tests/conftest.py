"""Servidor HTTP local que imita o WebDAV do Nextcloud e um servidor de arquivos."""

from __future__ import annotations

import threading
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

import pytest

WEBDAV_ROOT = "/public.php/webdav/"


@dataclass
class FakeFile:
    body: bytes
    etag: str
    last_modified: str = field(default_factory=lambda: formatdate(0, usegmt=True))


@dataclass
class FakeServer:
    base: str
    files: dict[str, FakeFile]
    requests: list[str]

    def put(self, path: str, body: bytes, etag: str) -> None:
        self.files[path] = FakeFile(body, etag)

    def downloads(self) -> int:
        return sum(1 for r in self.requests if r.startswith("GET "))


def _propfind_body(files: dict[str, FakeFile]) -> bytes:
    rows = [
        "<d:response><d:href>/public.php/webdav/</d:href><d:propstat><d:prop>"
        "<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
    ]
    for path, f in sorted(files.items()):
        if not path.startswith(WEBDAV_ROOT):
            continue
        href = escape(urllib.parse.quote(path))
        rows.append(
            f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>"
            f"<d:getlastmodified>{f.last_modified}</d:getlastmodified>"
            f"<d:getcontentlength>{len(f.body)}</d:getcontentlength>"
            f'<d:resourcetype/><d:getetag>"{f.etag}"</d:getetag>'
            "</d:prop></d:propstat></d:response>"
        )
    xml = '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">' + "".join(rows)
    return (xml + "</d:multistatus>").encode()


@pytest.fixture
def fake_server() -> Iterator[FakeServer]:
    files: dict[str, FakeFile] = {}
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _file(self) -> FakeFile | None:
            return files.get(urllib.parse.unquote(urllib.parse.urlparse(self.path).path))

        def _headers(self, f: FakeFile) -> None:
            self.send_header("Content-Length", str(len(f.body)))
            self.send_header("ETag", f'"{f.etag}"')
            self.send_header("Last-Modified", f.last_modified)
            self.end_headers()

        def do_HEAD(self) -> None:
            requests.append(f"HEAD {self.path}")
            f = self._file()
            if f is None:
                self.send_error(404)
                return
            self.send_response(200)
            self._headers(f)

        def do_GET(self) -> None:
            requests.append(f"GET {self.path}")
            f = self._file()
            if f is None:
                self.send_error(404)
                return
            self.send_response(200)
            self._headers(f)
            self.wfile.write(f.body)

        def do_PROPFIND(self) -> None:
            requests.append(f"PROPFIND {self.path}")
            body = _propfind_body(files)
            self.send_response(207)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield FakeServer(f"http://127.0.0.1:{server.server_port}", files, requests)
    finally:
        server.shutdown()
        server.server_close()
