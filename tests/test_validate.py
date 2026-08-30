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

    if not validate.rulings_available("102.20"):
        pytest.skip("CROSS rulings not fetched; run validate --fetch")
    # The cache holds both parts' rulings; score them apart.
    return validate.run(corpus, only=validate.ruling_set("102.20"))


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


# ---- 102.21 ----------------------------------------------------------------


@pytest.fixture(scope="module")
def report_21(corpus_102_21):
    from originshift import parse_102_21, sources

    if not validate.rulings_available("102.21"):
        pytest.skip("CROSS rulings not fetched; run validate --fetch")
    return validate.run(
        corpus_102_21,
        attribution=validate.ATTRIBUTION_21,
        only=validate.ruling_set("102.21"),
        grammar=parse_102_21,
    )


def test_the_textile_set_is_the_expected_size(report_21):
    assert report_21.rulings_examined == 554
    assert 80 <= len(report_21.cases) <= 130


def test_textile_fidelity_holds(report_21):
    assert report_21.coverage > 0.85
    assert report_21.fidelity > 0.60


def test_the_hierarchy_restatements_are_not_scored_as_e1_rules(corpus_102_21):
    """102.21(c)(1) to (c)(5) are quoted constantly in these rulings. They are
    not entries in the (e)(1) table, and scoring them there measured the wrong
    thing — it put fidelity 30 points low."""
    hierarchy = (
        "If the good was knit to shape, the country of origin of the good is "
        "the single country, territory, or insular possession in which the good "
        "was knit."
    )
    assert validate.quoted_rules(
        "Under 19 CFR 102.21, " + hierarchy, validate.ATTRIBUTION_21
    ) == []


def test_where_cbp_reached_c2_this_corpus_can_too(corpus_102_21):
    """The failure that matters: a requirement CBP satisfied that this corpus
    offers no route to. Before the (c)(2) process fix this was 2 of 26."""
    if not validate.rulings_available("102.21"):
        pytest.skip("CROSS rulings not fetched; run validate --fetch")
    cases = validate.steps(corpus_102_21)
    two = [c for c in cases if c.step == "2" and c.reachable is not None]
    assert len(two) >= 20
    reachable = [c for c in two if c.reachable]
    assert len(reachable) / len(two) > 0.90


def test_a_ruling_covering_several_scenarios_is_not_scored(corpus_102_21):
    """It has no single answer to compare against."""
    assert validate.applied_step(
        "In Scenario 1 the country of origin is China pursuant to 19 CFR "
        "102.21(c)(4)."
    ) is None


def test_a_recited_step_is_not_read_as_an_applied_one(corpus_102_21):
    assert validate.applied_step(
        "Section 102.21(c)(2) states that where the country of origin cannot "
        "be determined under paragraph (c)(1), the country of origin is ..."
    ) is None


def test_e2_falls_through_when_it_does_not_determine(corpus_102_21):
    """102.21(c) is sequential. Where (e)(2) has not settled origin, (c)(3) to
    (c)(5) still apply — returning at (c)(2) strands the good.

    HQ 959435 is the case: CBP reached (c)(5) for a silk scarf; we stopped dead.
    """
    from originshift.resolve import resolve
    from originshift.textile import TextileFacts

    r = resolve(
        good="6214.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False,
            c2_does_not_determine=True,
            last_important_process_in="Hong Kong",
        ),
        corpus=corpus_102_21,
    )
    assert r.status == "resolved"
    assert (r.origin, r.rule_id) == ("Hong Kong", "102.21(c)(5)")


@pytest.fixture(scope="module")
def textile_cases(corpus_102_21):
    if not validate.rulings_available("102.21"):
        pytest.skip("CROSS rulings not fetched; run validate --fetch")
    return validate.textiles(corpus_102_21)


def test_the_textile_set_is_intact(textile_cases):
    assert len(textile_cases) == 13
    steps = {c.cbp_step for c in textile_cases}
    # every paragraph of the hierarchy is represented
    assert steps == {"1", "2", "3i", "3ii", "4", "5"}


def test_the_resolver_reaches_cbps_country_for_textiles(textile_cases):
    wrong = [c for c in textile_cases if not c.country_agrees]
    assert wrong == [], [(c.ruling, c.cbp_country, c.our_country) for c in wrong]


def test_it_gets_there_by_the_paragraph_cbp_used(textile_cases):
    """The country alone is not enough — a broker has to cite the step."""
    wrong = [c for c in textile_cases if not c.step_agrees]
    assert wrong == [], [(c.ruling, c.cbp_step, c.our_step) for c in wrong]
