import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from originshift import parse_102  # noqa: E402

XML = ROOT / "data" / "cache" / "cfr-19-102-2026-08-26.xml"
XML_134 = ROOT / "data" / "cache" / "cfr-19-134-2026-08-26.xml"
XML_323 = ROOT / "data" / "cache" / "cfr-16-323-2026-08-26.xml"


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


@pytest.fixture(scope="session")
def corpus_102_21():
    from originshift.corpus import Corpus, CORPUS_DIR

    if not list(CORPUS_DIR.glob("102.21-*.json")):
        pytest.skip("no 102.21 corpus built")
    return Corpus.load(which="102.21")


@pytest.fixture(scope="session")
def corpus_102_21_base():
    from originshift.corpus import Corpus, CORPUS_DIR

    if not list(CORPUS_DIR.glob("102.21-*.json")):
        pytest.skip("no 102.21 corpus built")
    return Corpus.load(which="102.21", overlays=False)


@pytest.fixture(scope="session")
def xml_134():
    """19 CFR Part 134, pinned to the issue date the corpus is built from."""
    if not XML_134.exists():
        pytest.skip(f"Part 134 source not cached at {XML_134}")
    return XML_134.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def xml_323():
    """16 CFR Part 323, the FTC Made in USA rule, same issue date."""
    if not XML_323.exists():
        pytest.skip(f"Part 323 source not cached at {XML_323}")
    return XML_323.read_text(encoding="utf-8")
