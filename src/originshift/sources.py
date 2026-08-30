"""Fetch primary legal sources. Every fetch is pinned to a dated snapshot.

The whole point of the versioning discipline (spec 7) is that a corpus record can
name the exact source document it was derived from, so a rule can be re-derived
later even after the source has been amended.
"""

from __future__ import annotations

from . import paths
import ssl
import urllib.request
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ECFR = "https://www.ecfr.gov/api/versioner/v1"
CACHE = paths.CACHE

def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("originshift")
    except PackageNotFoundError:  # running from a checkout without an install
        return "dev"


#: Sent to public government endpoints. No URL until the repository has a home:
#: a user agent pointing somewhere that does not resolve is worse than one that
#: only names the tool.
USER_AGENT = f"originshift/{_version()}"


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


CROSS = "https://rulings.cbp.gov/api"

#: CROSS caps totalHits at 10,000, so a query must stay well inside that to be
#: sure the result set is complete rather than silently truncated.
CROSS_HIT_CAP = 10_000


def cross_search(
    term: str, collection: str = "hq", page_size: int = 100
) -> list[dict]:
    """Every ruling matching a term, following pagination to the end."""
    import json
    import urllib.parse

    out: list[dict] = []
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {
                "term": term,
                "collection": collection,
                "pageSize": page_size,
                "page": page,
            }
        )
        data = json.loads(_get(f"{CROSS}/search?{query}"))
        total = data.get("totalHits", 0)
        if total >= CROSS_HIT_CAP:
            raise RuntimeError(
                f"query {term!r} returned {total} hits, at or above CROSS's "
                f"{CROSS_HIT_CAP} cap; the result set would be truncated"
            )
        batch = data.get("rulings", [])
        out.extend(batch)
        if len(out) >= total or not batch:
            return out
        page += 1


def cross_ruling(number: str) -> dict:
    """One ruling with its full text, cached on disk."""
    import json
    import time

    cache = CACHE / "cross"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{number}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    time.sleep(0.3)  # a public endpoint; do not hammer it
    raw = _get(f"{CROSS}/ruling/{number}")
    path.write_bytes(raw)
    return json.loads(raw)
