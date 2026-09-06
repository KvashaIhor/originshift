"""The fetch path is the claim that the corpus can be re-derived.

SECURITY.md tells a reader the corpus can be rebuilt from the eCFR by anyone
running build_corpus. That sentence is only true while the fetch works, and it
stopped working silently when eCFR began answering 406 to requests that do not
offer to take a compressed response. These tests hold the header, offline.
"""

import gzip
import io
import urllib.request

from originshift import sources


class _Resp(io.BytesIO):
    def __init__(self, body: bytes, headers: dict[str, str]):
        super().__init__(body)
        self.headers = headers
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_the_request_offers_to_take_a_compressed_response(monkeypatch):
    """eCFR answers 406 without it, so it is a requirement, not an optimisation."""
    seen = {}

    def fake(req, *a, **kw):
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _Resp(b"<xml/>", {})

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    sources._get("https://example.invalid/x.xml")
    assert seen["headers"].get("Accept-encoding".lower()) == "gzip"


def test_a_compressed_response_is_decompressed(monkeypatch):
    """urllib does not decompress on its own; a caller would get gzip bytes."""
    body = gzip.compress(b"<DIV5 N='134'/>")

    def fake(req, *a, **kw):
        return _Resp(body, {"Content-Encoding": "gzip"})

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert sources._get("https://example.invalid/x.xml") == b"<DIV5 N='134'/>"


def test_an_uncompressed_response_is_passed_through(monkeypatch):
    """Not every endpoint compresses; the JSON ones did not change."""

    def fake(req, *a, **kw):
        return _Resp(b'{"titles": []}', {})

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert sources._get("https://example.invalid/titles.json") == b'{"titles": []}'
