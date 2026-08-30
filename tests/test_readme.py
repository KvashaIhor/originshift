"""The README documents a data format other people will code against.

It drifted once already: it described a `shift.from_level` field for several
commits after the disjunction fix replaced it with `shift.sources`. Anyone
following it would have written code against a field that was not there.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def documented_record():
    blocks = re.findall(r"```json\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    if not blocks:
        pytest.fail("the README no longer shows a corpus record")
    return json.loads(blocks[0])


def test_the_documented_record_matches_a_real_one(documented_record, corpus):
    """Every field shown must exist, with the shape shown, in the built corpus."""
    rule = next(r for r in corpus.rules if r.rule_id == documented_record["rule_id"])
    actual = rule.to_dict()

    def compare(shown, real, path="") -> None:
        if isinstance(shown, dict):
            assert isinstance(real, dict), f"{path}: shape differs"
            for key, value in shown.items():
                assert key in real, f"{path}.{key} is documented but not in the corpus"
                compare(value, real[key], f"{path}.{key}")
        elif isinstance(shown, list):
            assert isinstance(real, list), f"{path}: shape differs"
            for i, value in enumerate(shown):
                compare(value, real[i], f"{path}[{i}]")
        else:
            assert shown == real, f"{path}: README says {shown!r}, corpus has {real!r}"

    compare(documented_record, actual)


def test_the_headline_counts_are_current(corpus, corpus_102_21):
    """The tables at the top state rule counts. Stale numbers mislead."""
    text = README.read_text(encoding="utf-8")
    assert f"{len(corpus.rules):,}" in text, f"102.20 now has {len(corpus.rules)} rules"
    base = [r for r in corpus_102_21.rules if not corpus_102_21.provenance_of(r.rule_id)]
    assert str(len(base)) in text, f"102.21 now has {len(base)} rules"


def test_every_module_listed_exists(corpus):
    """The 'What is here' table names files."""
    text = README.read_text(encoding="utf-8")
    for name in re.findall(r"`(\w+\.py)`", text):
        assert (ROOT / "src" / "originshift" / name).exists(), f"{name} is gone"


def test_the_scope_limit_is_stated_before_the_usage(corpus):
    """Part 102 is not the general origin test for US imports, and someone
    skimming must not miss that."""
    text = README.read_text(encoding="utf-8")
    assert "102.0" in text
    assert text.index("102.0") < text.index("## Resolving")


def test_the_corpus_round_trips_through_its_own_loader(corpus, corpus_102_21):
    """A field added to the grammar but not to the loader is silently dropped on
    load — it has happened twice (condition/sequence, then excluded_when), and
    both times the corpus on disk was right while the object in memory was not.
    """
    import json

    from originshift.corpus import CORPUS_DIR, Corpus

    for which in ("102.20", "102.21"):
        path = sorted(CORPUS_DIR.glob(f"{which}-*.json"))[-1]
        raw = json.loads(path.read_text(encoding="utf-8"))
        out = [r.to_dict() for r in Corpus.from_dict(raw).rules]
        assert out == raw["rules"], f"{which} loses fields on load"
