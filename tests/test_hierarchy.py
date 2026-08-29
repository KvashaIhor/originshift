"""102.11 is a hierarchy, and 102.20 is only one step of it."""

import pytest

from originshift.resolve import Material, resolve


def test_a_wholly_obtained_good_needs_no_shift(corpus):
    r = resolve(good="0101.21", inputs=[], country="IE", wholly_obtained=True, corpus=corpus)
    assert r.status == "resolved"
    assert (r.origin, r.basis, r.rule_id) == ("IE", "wholly_obtained", "102.11(a)(1)")


def test_exclusively_domestic_materials_confer_origin(corpus):
    """102.11(a)(2) is reached before 102.20 is consulted at all — these
    materials would fail the shift, and it does not matter."""
    r = resolve(
        good="8708.29",
        inputs=[Material("8708.95", "VN"), Material("7208.10", "VN")],
        country="VN",
        corpus=corpus,
    )
    assert r.status == "resolved"
    assert (r.basis, r.rule_id) == ("exclusively_domestic", "102.11(a)(2)")


def test_a_material_of_unstated_origin_is_not_assumed_domestic(corpus):
    """Assuming domestic would hand out origin on missing information."""
    r = resolve(
        good="8708.29",
        inputs=[Material("8708.95", "VN"), Material("8708.99")],
        country="VN",
        corpus=corpus,
    )
    assert r.basis != "exclusively_domestic"


def test_de_minimis_carries_a_good_whose_shift_failed(corpus):
    r = resolve(
        good="8708.29",
        inputs=[Material("8708.95", value=3.0)],
        country="VN",
        good_value=100.0,
        corpus=corpus,
    )
    assert r.status == "resolved"
    assert r.basis == "tariff_shift_de_minimis"
    assert "3.0%" in r.reason


def test_de_minimis_does_not_carry_a_material_over_the_threshold(corpus):
    r = resolve(
        good="8708.29",
        inputs=[Material("8708.95", value=30.0)],
        country="VN",
        good_value=100.0,
        corpus=corpus,
    )
    assert r.status == "unresolved" and r.satisfied is False
    assert "above the 7%" in r.needed


def test_chapter_22_gets_the_larger_allowance(corpus):
    """102.13(a) allows 10 percent for a good of Chapter 22, not 7."""
    r = resolve(
        good="2208.30",
        inputs=[Material("2208.30", value=9.0)],
        country="IE",
        good_value=100.0,
        corpus=corpus,
    )
    assert r.status == "resolved" and r.basis == "tariff_shift_de_minimis"


def test_some_chapters_get_no_allowance_at_all(corpus):
    """102.13(b) withholds it from goods of chapters 1-4, 7, 8, 11, 12, 15, 17, 20."""
    r = resolve(
        good="0406",
        inputs=[Material("0406", value=1.0)],
        country="CA",
        good_value=100.0,
        corpus=corpus,
    )
    assert r.status == "unresolved" and r.satisfied is False
    assert "102.13(b) withholds" in r.needed


def test_de_minimis_is_named_when_the_values_are_not_known(corpus):
    """The shift finding stands; the allowance is named as an open route rather
    than swallowing the answer into an abstention."""
    r = resolve(good="8708.29", inputs=["8708.95"], country="VN", corpus=corpus)
    assert r.satisfied is False  # the shift itself is settled
    assert "102.13" in r.needed
    assert "102.11(b)" in r.needed


def test_de_minimis_is_not_reached_while_an_alternative_is_open(corpus):
    """102.13 applies to materials that did not undergo the change. Until every
    alternative has failed, that is not yet known."""
    r = resolve(good="2205", inputs=["2204"], country="ES", corpus=corpus)
    assert r.satisfied is None
    assert "vermouth" in r.needed
    assert "102.13" not in r.needed


def test_a_non_qualifying_operation_defeats_a_shift_the_codes_allow(corpus):
    """102.17: repacking is not origin-conferring however the codes fall."""
    ok = resolve(good="8708.29", inputs=["7208.10"], country="VN", corpus=corpus)
    assert ok.status == "resolved"

    packed = resolve(
        good="8708.29",
        inputs=["7208.10"],
        country="VN",
        operation="simple_packing",
        corpus=corpus,
    )
    assert packed.status == "unresolved"
    assert packed.reason == "non_qualifying_operation"
    assert packed.rule_id == "102.17"


def test_an_unrecognised_operation_is_refused_not_ignored(corpus):
    with pytest.raises(ValueError, match="unknown operation"):
        resolve(
            good="8708.29",
            inputs=["7208.10"],
            country="VN",
            operation="welding",
            corpus=corpus,
        )


def test_a_failed_shift_names_the_paragraph_that_applies_next(corpus):
    r = resolve(good="0406", inputs=["0406"], country="CA", corpus=corpus)
    assert "102.11(b)" in r.needed
    assert "essential character" in r.needed
