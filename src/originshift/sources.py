"""Fetch primary legal sources. Every fetch is pinned to a dated snapshot.

The whole point of the versioning discipline (spec 7) is that a corpus record can
name the exact source document it was derived from, so a rule can be re-derived
later even after the source has been amended.
"""

from __future__ import annotations

import ssl
import urllib.request
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ECFR = "https://www.ecfr.gov/api/versioner/v1"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"

USER_AGENT = "originshift/0.0.1 (+https://github.com/originshift/originshift)"


@dataclass(frozen=True)
class Snapshot:
    """A retrieved source document, identified by the date it was issued."""

    url: str
    issue_date: str
    path: Path

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8")


@cache
def _ssl_context() -> ssl.SSLContext:
    """Trust store for the fetch.

    Python installed from python.org does not wire up the system trust store, so
    a default context fails to verify eCFR. Prefer certifi's bundle where it is
    installed; never fall back to an unverified context, because the whole point
    of the corpus is that its provenance can be trusted.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180, context=_ssl_context()) as resp:
        return resp.read()


def latest_issue_date(title: int = 19) -> str:
    """Ask eCFR which issue date is current for a CFR title."""
    import json

    data = json.loads(_get(f"{ECFR}/titles.json"))
    for t in data["titles"]:
        if t["number"] == title:
            return t["latest_issue_date"]
    raise LookupError(f"title {title} not found")


def cfr_part(title: int, part: int, issue_date: str | None = None) -> Snapshot:
    """Fetch one CFR part as eCFR's structured XML, caching by issue date."""
    issue_date = issue_date or latest_issue_date(title)
    url = f"{ECFR}/full/{issue_date}/title-{title}.xml?part={part}"
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"cfr-{title}-{part}-{issue_date}.xml"
    if not path.exists():
        path.write_bytes(_get(url))
    return Snapshot(url=url, issue_date=issue_date, path=path)
