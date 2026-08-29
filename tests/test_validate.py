"""The validator must measure the right thing, or its numbers mean nothing."""

import pytest

from originshift import validate


def test_a_quote_is_only_counted_when_attributed_to_102_20():
    """Rulings that cite 102.20 also quote USMCA and NAFTA rules, which are
    worded almost identically and are a different legal test entirely."""
    attributed = (
        "Section 102.20 provides: A change to subheading 8708.29 from any "
        "other subheading, except from subheading 8708.95."
    )
    preferential = (
        "General Note 11, HTSUS, provides: A change to subheading 8708.29 "
        "from any other subheading, except from subheading 8708.95."
    )
    assert len(validate.quoted_rules(attributed)) == 1
    assert validate.quoted_rules(preferential) == []


def test_a_quote_stops_where_the_rule_stops():
    """A quotation that runs into CBP's prose picks up codes that are not
    part of the rule, and the comparison then fails for the wrong reason."""
    text = (
        "Under 19 CFR 102.20, A change to subheading 8607.11 from any other "
        "subheading, except from subheading 8607.12, since the only materials "
        "of subheading 8714 that may be considered."
    )
    (quote,) = validate.quoted_rules(text)
    assert quote.endswith("8607.12")
    assert "8714" not in quote


def test_cbps_quoting_habits_do_not_change_the_rule():
    """CBP pluralises the level word and writes headings in HS dotted form."""
    assert validate.normalise("A change to headings 48.17 through 48.22") == (
        "A change to heading 4817 through 4822"
    )
    assert "subheading 8708.29" in validate.normalise("subheadings 8708.29")


def test_the_spec_example_matches_the_corpus_structurally(corpus):
    verdict, rule_id, _ = validate.check_quote(
        "A change to subheading 8708.29 from any other subheading, except "
        "from subheading 8708.95.",
        corpus,
    )
    assert verdict == "equivalent"
    assert rule_id == "102.20/8708.29"


def test_wording_differences_do_not_count_as_disagreement(corpus):
    """The same rule, quoted CBP's way, must still match."""
    verdict, _, _ = validate.check_quote(
        "A change to subheadings 8708.29 from any other subheadings, except "
        "from subheadings 8708.95.",
        corpus,
    )
    assert verdict == "equivalent"


def test_a_genuinely_different_rule_is_reported_as_differing(corpus):
    verdict, _, detail = validate.check_quote(
        "A change to subheading 8708.29 from any other chapter.", corpus
    )
    assert verdict == "differs"
    assert detail


def test_a_code_outside_the_corpus_is_reported_as_absent(corpus):
    """A superseded code is drift, not a defect, and is scored apart."""
    verdict, _, _ = validate.check_quote(
        "A change to subheading 6203.42 from any other chapter.", corpus
    )
    assert verdict == "target_absent"


@pytest.fixture(scope="module")
def report(corpus):
    from originshift import sources

    if not (sources.CACHE / "cross").exists():
        pytest.skip("CROSS rulings not cached")
    return validate.run(corpus)


def test_the_validation_set_is_the_expected_size(report):
    assert report.rulings_examined == 312
    assert 200 <= len(report.cases) <= 320


def test_agreement_is_strongest_on_rulings_of_the_corpus_own_era(report):
    """The corpus answers under HTSUS 2026. Agreement falling away with age is
    the versioning argument, not a defect: HS renumbering moves the codes."""
    eras = report.stratify()
    _, recent_coverage, recent_fidelity = eras["2020-2026"]
    _, old_coverage, old_fidelity = eras["1994-2002"]
    assert recent_coverage > old_coverage
    assert recent_fidelity > old_fidelity
    assert recent_coverage > 0.90
    assert recent_fidelity > 0.70
