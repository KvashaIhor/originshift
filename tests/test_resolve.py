"""The resolver returns one of three outcomes, and never guesses (spec 5)."""

from originshift.resolve import resolve


def test_the_worked_example_from_the_spec(corpus):
    r = resolve(good="8708.29", inputs=["7208.10", "8708.99"], country="VN", corpus=corpus)
    assert r.status == "resolved"
    assert r.origin == "VN"
    assert r.basis == "tariff_shift"
    assert r.rule_id == "102.20/8708.29"
    assert r.rule_text.startswith("A change to subheading 8708.29 from any other")
    assert r.satisfied is True
    assert r.vintage == "HTSUS-2026"
    assert bool(r) is True


def test_every_answer_carries_its_derivation(corpus):
    """The trace is the product: an answer a broker can justify."""
    r = resolve(good="8708.29", inputs=["7208.10"], country="VN", corpus=corpus)
    (finding,) = r.trace
    (check,) = finding.checks
    assert check.material == "7208.10"
    assert check.outcome == "shifted"
    assert "different subheading" in check.detail


def test_an_excluded_material_defeats_the_shift(corpus):
    """8708.95 is carved out of the 8708.29 rule by name."""
    r = resolve(good="8708.29", inputs=["8708.95"], country="VN", corpus=corpus)
    assert r.status == "unresolved"
    assert r.satisfied is False
    assert r.reason == "shift_not_satisfied"
    assert r.origin is None
    assert r.trace[0].checks[0].outcome == "excluded"


def test_a_material_in_the_goods_own_subheading_does_not_shift(corpus):
    r = resolve(good="8708.29", inputs=["8708.29"], country="VN", corpus=corpus)
    assert r.status == "unresolved" and r.satisfied is False
    assert r.trace[0].checks[0].outcome == "not_shifted"


def test_an_unverifiable_proviso_abstains_and_names_it(corpus):
    """The spec's second example: say what is missing rather than guess."""
    r = resolve(good="2008.11", inputs=["1202.41"], country="CN", corpus=corpus)
    assert r.status == "unresolved"
    assert r.reason == "insufficient_information"
    assert r.satisfied is None
    assert "mere blanching of peanuts" in r.needed
    assert r.rule_id == "102.20/2008.11"  # still cites the rule it got stuck on


def test_a_same_position_source_needs_a_fact_codes_do_not_carry(corpus):
    """'from any other good of subheading 8486.90' turns on which good it is."""
    r = resolve(good="8486.90", inputs=["8486.90"], country="TW", corpus=corpus)
    assert r.status == "unresolved"
    assert r.reason == "insufficient_information"
    assert "different good" in r.needed
    assert not any(f.satisfied for f in r.trace)


def test_two_satisfied_rules_are_reported_not_chosen_between(corpus):
    """3822.11 is reached by two rules; picking one silently would be worse."""
    r = resolve(good="3822.11", inputs=["2934.10"], country="IE", corpus=corpus)
    assert r.status == "ambiguous"
    assert r.origin is None
    assert "102.20/3002.12-3002.90" in r.needed and "102.20/3822" in r.needed


def test_a_disjunction_is_satisfied_by_any_one_alternative(corpus):
    """1602.90's first alternative fires even though a later one is excluded."""
    r = resolve(good="1602.90", inputs=["0403.10"], country="TH", corpus=corpus)
    assert r.status == "resolved" and r.origin == "TH"
    assert any(f.satisfied is False for f in r.trace)  # another alternative failed


def test_a_textile_good_is_referred_to_102_21(corpus):
    r = resolve(good="6203.42", inputs=["5208.11"], country="VN", corpus=corpus)
    assert r.status == "unresolved"
    assert r.reason == "no_rule_for_this_classification"
    assert "102.21" in r.needed


def test_no_materials_is_referred_to_102_11(corpus):
    r = resolve(good="8708.29", inputs=[], country="VN", corpus=corpus)
    assert r.status == "unresolved"
    assert r.reason == "no_input_materials_given"
    assert "102.11(a)(1)-(2)" in r.needed


def test_the_regime_must_match_the_corpus(corpus):
    import pytest

    with pytest.raises(ValueError, match="regime"):
        resolve(good="8708.29", inputs=["7208.10"], country="VN", regime="EU", corpus=corpus)


def test_a_result_is_only_truthy_when_resolved(corpus):
    ok = resolve(good="8708.29", inputs=["7208.10"], country="VN", corpus=corpus)
    no = resolve(good="8708.29", inputs=["8708.95"], country="VN", corpus=corpus)
    assert bool(ok) and not bool(no)
