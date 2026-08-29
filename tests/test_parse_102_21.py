"""102.21 governs textiles, and its rules are shaped differently from 102.20's."""

import pytest


@pytest.fixture(scope="session")
def rules_21():
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from originshift import parse_102_21

    xml = root / "data" / "cache" / "cfr-19-102-2026-08-26.xml"
    if not xml.exists():
        pytest.skip("corpus source not cached")
    return parse_102_21.parse(
        xml.read_text(encoding="utf-8"), vintage="HTSUS-2026", source_url="u"
    )


@pytest.fixture(scope="session")
def by_key(rules_21):
    return {r.htsus: r for r in rules_21}


def test_corpus_size_is_stable(rules_21):
    assert len(rules_21) == 101
    assert sum(len(r.alternatives) for r in rules_21) == 176


def test_a_numbered_fallback_is_reached_not_chosen(by_key):
    """5007(2) opens "If the country of origin cannot be determined under (1)
    above" — it applies only where the one before it did not."""
    first, second = by_key["5007"].alternatives
    assert (first.sequence, first.is_fallback) == (1, False)
    assert (second.sequence, second.is_fallback) == (2, True)


def test_conditioned_sub_rules_are_selected_by_a_fact_not_ordered(by_key):
    """5004-5006 offers staple fibers or filaments. Neither is a fallback."""
    staple, filament = by_key["5004-5006"].alternatives
    assert staple.condition == "the good is of staple fibers"
    assert filament.condition == "the good is of filaments"
    assert not staple.is_fallback and not filament.is_fallback


def test_a_condition_on_the_good_cannot_be_settled_from_a_code(by_key):
    """Whether a good is of staple fibers is not in its classification."""
    staple = by_key["5004-5006"].alternatives[0]
    assert not staple.structured
    assert staple.unparsed_reason == "conditional_on_the_good"


def test_process_rules_are_recognised_as_such(by_key):
    """"A change from greige fabric ... by both dyeing and printing" turns on
    where an operation happened, not on a movement between codes."""
    first = by_key["5007"].alternatives[0]
    assert first.kind == "process"
    assert first.unparsed_reason == "process_rule"


def test_statistical_reporting_numbers_are_understood(by_key):
    """The HTSUS goes below the six digits the HS defines."""
    rule = by_key["3921.90.2550"]
    (scope,) = rule.scope
    assert scope.level == "statistical_suffix"
    assert scope.contains("3921.90.2550")


def test_most_textile_rules_need_a_fact_beyond_the_codes(rules_21):
    """An honest headline: only about a third of 102.21 is answerable from
    classifications, because textile origin turns on fabric-making, knitting
    and assembly."""
    alts = [a for r in rules_21 for a in r.alternatives]
    structured = sum(a.structured for a in alts)
    assert 0.25 < structured / len(alts) < 0.40


def test_the_missing_apparel_headings_are_reported(rules_21):
    """The eCFR has no 6201-6208 entry, and the corpus must say so rather than
    look complete."""
    from originshift.build_corpus import UNINCORPORATED

    (gap,) = UNINCORPORATED["102.21(e)(1)"]
    assert gap["kind"] == "missing_from_source"
    assert "6201" in gap["detail"] and "87 FR 68356" in gap["detail"]
    assert not any(r.htsus == "6201-6208" for r in rules_21)
