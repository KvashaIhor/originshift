"""Where the package reads and writes.

Anchoring on ``Path(__file__).parents[2]`` works from a checkout and resolves
into the virtualenv's ``lib`` directory from an installed wheel — so the
documented commands raised FileNotFoundError, and anything that wrote would have
written into site-packages.

Read-only data that ships with the package is addressed inside it. Anything
written at runtime goes to a user cache directory, unless the package is being
run from a checkout, where the repository's own ``data/`` is used so the
development workflow is unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Data that travels with the package: the built corpora, reviewed overlays and
#: the curated validation cases.
PACKAGE_DATA = Path(__file__).resolve().parent / "data"

#: The repository, when the package is running from a checkout rather than an
#: install. `pyproject.toml` is the marker: a wheel does not carry one.
_REPO = Path(__file__).resolve().parents[2]
_IN_CHECKOUT = (_REPO / "pyproject.toml").exists() and (_REPO / "src").is_dir()


def _user_cache() -> Path:
    """A writable directory of the user's, per the XDG convention."""
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "originshift"
    if os.name == "nt":  # pragma: no cover - not exercised here
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "originshift"
    return Path.home() / ".cache" / "originshift"


def writable(name: str) -> Path:
    """A directory to write `name` into: the repo's when in a checkout, the
    user's cache otherwise. Never inside the installed package."""
    root = _REPO / "data" if _IN_CHECKOUT else _user_cache()
    return root / name


#: A corpus the user has rebuilt. Takes precedence over the shipped one, and is
#: written here rather than into PACKAGE_DATA: an installed package is not the
#: user's to modify, may not be writable at all, and is replaced on upgrade.
CORPUS_OUT = writable("corpus")

#: Source documents fetched from eCFR and CROSS.
CACHE = writable("cache")
#: Extractions awaiting review, from originshift.ingest.
STAGING = writable("staging")
#: Curated validation cases. These ship with the package.
VALIDATION = PACKAGE_DATA / "validation"


def write_if_changed(path, corpus: dict, ignore: str = "built_on") -> bool:
    """Write a corpus only when something other than the build date differs.

    `built_on` records the day the artifact was generated, which makes every
    rebuild dirty the tree even when the source, the parser and every record are
    identical. Comparing without that field keeps it honest and keeps a rebuild
    from producing a diff nobody made.
    """
    import json

    body = json.dumps(corpus, indent=1, ensure_ascii=False)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != ignore} == {
            k: v for k, v in corpus.items() if k != ignore
        }:
            return False
    path.write_text(body, encoding="utf-8")
    return True
