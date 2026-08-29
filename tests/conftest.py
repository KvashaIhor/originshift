import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from originshift import parse_102  # noqa: E402

XML = ROOT / "data" / "cache" / "cfr-19-102-2026-08-26.xml"


@pytest.fixture(scope="session")
def rules():
    if not XML.exists():
        pytest.skip(f"corpus source not cached at {XML}")
    return parse_102.parse(
        XML.read_text(encoding="utf-8"),
        vintage="HTSUS-2026",
        source_url="https://www.ecfr.gov/api/versioner/v1/full/2026-08-26/title-19.xml?part=102",
    )


@pytest.fixture(scope="session")
def by_htsus(rules):
    return {r.htsus: r for r in rules}


@pytest.fixture(scope="session")
def corpus():
    from originshift.corpus import Corpus, CORPUS_DIR

    if not list(CORPUS_DIR.glob("102.20-*.json")):
        pytest.skip("no corpus built; run python -m originshift.build_corpus")
    return Corpus.load()
