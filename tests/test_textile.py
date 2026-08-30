"""102.21(c), the hierarchy for textile and apparel products.

102.11 governs goods "other than textile and apparel products covered by
§ 102.21". Answering a covered good under 102.11 cites a provision that excludes
it, which for a tool whose claim is defensibility is worse than saying nothing.
"""

import pytest

from originshift.resolve import Material, resolve
from originshift.textile import TextileFacts


def test_a_covered_good_is_not_answered_under_102_11(corpus_102_21):
    """The bug this module exists to fix: 102.11(a)(1) was cited for textiles."""
    r = resolve(good="6203.42", inputs=[], country="VN", wholly_obtained=True, corpus=corpus_102_21)
    assert r.rule_id == "102.21(c)(1)"
    assert not (r.rule_id or "").startswith("102.11")


def test_routing_holds_on_the_default_path_not_only_with_the_textile_corpus():
    """Which part governs is a question about 102.21's coverage, not about the
    corpus the caller happened to load.

    Asking a 102.20 corpus returned nothing, so every 102.21 good outside
    chapters 50-63 was answered under 102.20 — 9113.90.40 came back "resolved,
    102.20/9113" under a section that excludes it. The test that was meant to
    catch this passed a 102.21 corpus in, so it only ever exercised the path
    that worked.
    """
    for good, material in (
        ("9113.90.40", "5806.32"),   # watch straps of textile
        ("9612.10.9010", "5407.10"),  # typewriter ribbons
        ("8708.21", "5407.10"),       # seat belts
        ("6505.00", "6001.10"),       # hats
    ):
        r = resolve(good=good, inputs=[Material(material, "CN")], country="MX")
        assert not (r.rule_id or "").startswith("102.20"), f"{good} answered under 102.20"


def test_a_non_textile_good_is_not_swept_into_102_21():
    r = resolve(good="8708.29", inputs=[Material("7208.10", "CN")], country="MX")
    assert r.rule_id == "102.20/8708.29"


def test_coverage_follows_102_21_b_5_not_just_the_chapters(corpus_102_21):
    """102.21 reaches beyond chapters 50-63: seat belts, hats, umbrellas."""
    assert corpus_102_21.reaches("6203.42")     # apparel
    assert corpus_102_21.reaches("8708.21")     # seat belts
    assert corpus_102_21.reaches("6505.00")     # hats
    assert corpus_102_21.reaches("9404.90")
    assert not corpus_102_21.reaches("8708.29")  # a door part is not a textile
    # the list is bounded: 4202.12.40-89 is covered, 4202.12.99 is not
    assert corpus_102_21.reaches("4202.12.60")
    assert not corpus_102_21.reaches("4202.12.99")


def test_wholly_obtained_cites_c_1(corpus_102_21):
    r = resolve(good="6203.42", inputs=[], country="VN", wholly_obtained=True, corpus=corpus_102_21)
    assert (r.status, r.origin, r.basis) == ("resolved", "VN", "wholly_obtained")


def test_knit_to_shape_cites_c_3_i(corpus_102_21):
    r = resolve(
        good="6110.20",
        inputs=[Material("5205.11", "CN")],
        country="VN",
        textile=TextileFacts(c2_does_not_determine=True, knit_to_shape_in="VN"),
        corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id, r.basis) == ("VN", "102.21(c)(3)(i)", "knit_to_shape")


def test_wholly_assembled_cites_c_3_ii(corpus_102_21):
    r = resolve(
        good="6203.42",
        inputs=[Material("5208.11", "CN")],
        country="VN",
        textile=TextileFacts(c2_does_not_determine=True, wholly_assembled_in="VN"),
        corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id) == ("VN", "102.21(c)(3)(ii)")


def test_an_excepted_heading_falls_past_c_3_ii(corpus_102_21):
    """(c)(3)(ii) does not reach heading 6214, so assembly does not settle it."""
    facts = TextileFacts(c2_does_not_determine=True, wholly_assembled_in="VN")
    r = resolve(
        good="6214.10", inputs=[Material("5007.10", "CN")], country="VN",
        textile=facts, corpus=corpus_102_21,
    )
    assert r.status == "unresolved"
    assert r.origin != "VN"

    facts.most_important_process_in = "IT"
    r = resolve(
        good="6214.10", inputs=[Material("5007.10", "CN")], country="VN",
        textile=facts, corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id) == ("IT", "102.21(c)(4)")


def test_the_steps_run_in_order(corpus_102_21):
    """(c)(4) must not be reached while (c)(3)(i) would answer."""
    r = resolve(
        good="6110.20",
        inputs=[Material("5205.11", "CN")],
        country="VN",
        textile=TextileFacts(c2_does_not_determine=True, knit_to_shape_in="BD",
                             most_important_process_in="VN"),
        corpus=corpus_102_21,
    )
    assert r.origin == "BD"
    assert r.rule_id == "102.21(c)(3)(i)"


def test_last_important_process_is_the_final_step(corpus_102_21):
    r = resolve(
        good="6214.10",
        inputs=[Material("5007.10", "CN")],
        country="VN",
        textile=TextileFacts(c2_does_not_determine=True, last_important_process_in="IN"),
        corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id) == ("IN", "102.21(c)(5)")


def test_the_textile_de_minimis_is_by_weight_not_value(corpus_102_21):
    """102.13(c) allows 7 percent of total weight. 102.13(a)'s value test is
    the wrong instrument here."""
    r = resolve(
        good="3921.12.15",
        inputs=[Material("3921.12.15", "CN", weight=3.0)],
        country="VN",
        good_weight=100.0,
        corpus=corpus_102_21,
    )
    assert r.basis == "tariff_shift_de_minimis"
    assert "102.13(c)" in r.reason and "weight" in r.reason

    over = resolve(
        good="3921.12.15",
        inputs=[Material("3921.12.15", "CN", weight=30.0)],
        country="VN",
        good_weight=100.0,
        corpus=corpus_102_21,
    )
    assert over.status == "unresolved"


def test_value_alone_does_not_trigger_the_textile_allowance(corpus_102_21):
    """A material given a value but no weight cannot be disregarded under (c)."""
    r = resolve(
        good="3921.12.15",
        inputs=[Material("3921.12.15", "CN", value=3.0)],
        country="VN",
        good_value=100.0,
        corpus=corpus_102_21,
    )
    assert r.basis != "tariff_shift_de_minimis"


def test_with_no_production_facts_it_names_the_steps_it_needs(corpus_102_21):
    r = resolve(
        good="3921.12.15",
        inputs=[Material("3921.12.15", "CN")],
        country="VN",
        corpus=corpus_102_21,
    )
    assert r.status == "unresolved"
    assert "(c)(3)(i)" in r.needed and "(c)(4)" in r.needed
    assert "knit to shape" in r.needed


def test_a_process_rule_is_findable(corpus_102_21):
    """A rule with no tariff shift still governs its goods. Without a target the
    index cannot see it, and the good reads as having no rule at all."""
    found = corpus_102_21.candidates("6214.10")
    assert found
    assert any(alt.kind == "process" for _, alt in found)


def test_no_covered_good_is_left_without_a_rule(corpus_102_21):
    """Sampled across the coverage, every good should find something."""
    import re

    for rule in corpus_102_21.rules:
        for scope in rule.scope:
            code = scope.start
            if corpus_102_21.reaches(code):
                assert corpus_102_21.candidates(code), f"{code} has no findable rule"


def test_102_17_still_reaches_textiles(corpus_102_21):
    """102.21(c) applies 102.12 through 102.19 where appropriate."""
    r = resolve(
        good="6203.42",
        inputs=[Material("5208.11", "CN")],
        country="VN",
        operation="simple_packing",
        corpus=corpus_102_21,
    )
    assert r.rule_id == "102.17"
    assert r.reason == "non_qualifying_operation"


def test_a_non_textile_good_still_takes_102_11(corpus):
    """Routing must not have captured everything."""
    r = resolve(good="8708.29", inputs=[], country="VN", wholly_obtained=True, corpus=corpus)
    assert r.rule_id == "102.11(a)(1)"


# ---- found by validating against CROSS -------------------------------------


def test_c2_is_met_by_a_process_requirement_not_only_a_shift(corpus_102_21):
    """102.21(c)(2) confers origin where each foreign material "underwent an
    applicable change in tariff classification, and/or met any other
    requirement, specified for the good in paragraph (e)".

    Most of 102.21 states its requirement as a process. Testing only the shift
    made (c)(2) unreachable for those goods however much the user knew — and
    CBP applied (c)(2) in 33 of the 57 rulings that apply one step.
    """
    r = resolve(
        good="6301.30",
        inputs=[Material("5205.11", "CN")],
        country="VN",
        textile=TextileFacts(process_in={"fabric-making process": "IN"}),
        corpus=corpus_102_21,
    )
    assert r.status == "resolved"
    assert (r.origin, r.basis) == ("IN", "process")
    assert r.rule_id == "102.21(e)(1)/6301-6306"
    assert "102.21(c)(2)" in r.reason


def test_a_proviso_naming_a_process_counts_the_same(corpus_102_21):
    """"provided that the change is the result of the good being wholly
    assembled in a single country" is a requirement of (e)(1) like any other."""
    r = resolve(
        good="6203.42",
        inputs=[Material("5208.11", "CN")],
        country="VN",
        textile=TextileFacts(
            conditions={"two or more component parts": True},
            process_in={"wholly assembled": "VN"},
        ),
        corpus=corpus_102_21,
    )
    assert (r.status, r.origin) == ("resolved", "VN")


def test_a_condition_stated_in_codes_is_settled_from_the_code(corpus_102_21):
    """Asking the user whether their good is in heading 6302 through 6304 would
    be asking for what the classification already says."""
    from originshift.textile import _condition_holds

    condition = "the good is not goods of heading 6302 through 6304"
    assert _condition_holds(condition, TextileFacts(), "6301.30") is True
    assert _condition_holds(condition, TextileFacts(), "6303.92") is False


def test_an_e2_carve_out_is_narrower_than_the_headings_it_names(corpus_102_21):
    """102.21(e)(2) reaches those headings *except* goods of cotton, of wool, or
    a blend 16 percent or more cotton. Reading the carve-out as the whole
    heading excluded goods from the rule that reaches them — 6213, 6214, 6303,
    6304 and 9404.90, all common."""
    from originshift.textile import _condition_holds

    condition = (
        "the good is not goods of heading 6213 through 6214 provided for in "
        "paragraph (e)(2) of this section"
    )
    # not settleable from the code alone: it turns on fibre content
    assert _condition_holds(condition, TextileFacts(), "6214.10") is None
    assert _condition_holds(condition, TextileFacts(excepted_fibre=True), "6214.10") is True


def test_a_cotton_scarf_is_reached_by_e_1(corpus_102_21):
    r = resolve(
        good="6214.20",
        inputs=[Material("5208.11", "CN")],
        country="VN",
        textile=TextileFacts(
            conditions={"of cotton": True},
            process_in={"fabric-making process": "IN"},
        ),
        corpus=corpus_102_21,
    )
    assert (r.status, r.origin) == ("resolved", "IN")


def test_a_good_governed_by_e_2_takes_e_2(corpus_102_21):
    """A silk scarf of 6214 is (e)(2)'s; answering it from the (e)(1) table
    would apply the wrong rule."""
    r = resolve(
        good="6214.10",
        inputs=[Material("5007.10", "CN")],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False,
            process_in={"fabric-making process": "IN"},
        ),
        corpus=corpus_102_21,
    )
    assert r.status == "resolved"
    assert (r.origin, r.rule_id) == ("IN", "102.21(e)(2)(ii)")


# ---- 102.21(e)(2), the dyed-and-printed regime -----------------------------


def test_e2_i_needs_two_or_more_finishing_operations(corpus_102_21):
    """"both dyed and printed when accompanied by two or more of the following
    finishing operations" — the count is the whole test."""
    facts = TextileFacts(
        excepted_fibre=False,
        dyed_and_printed_in="IT",
        finishing_operations=("bleaching", "napping"),
    )
    r = resolve(good="6214.10", inputs=[], country="VN", textile=facts, corpus=corpus_102_21)
    assert (r.status, r.origin, r.rule_id) == ("resolved", "IT", "102.21(e)(2)(i)")

    facts.finishing_operations = ("bleaching",)
    one = resolve(good="6214.10", inputs=[], country="VN", textile=facts, corpus=corpus_102_21)
    assert one.status == "unresolved"
    assert "two or more" in one.needed


def test_an_operation_not_on_the_list_does_not_count(corpus_102_21):
    facts = TextileFacts(
        excepted_fibre=False,
        dyed_and_printed_in="IT",
        finishing_operations=("bleaching", "ironing", "folding"),
    )
    r = resolve(good="6214.10", inputs=[], country="VN", textile=facts, corpus=corpus_102_21)
    assert r.status == "unresolved"


def test_e2_ii_does_not_reach_the_6117_10_goods_e2_iii_takes(corpus_102_21):
    """(e)(2)(ii) applies "except for goods of subheading 6117.10 that are knit
    to shape or consist of two or more component parts"."""
    r = resolve(
        good="6117.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False, conditions={"knit to shape": True},
            process_in={"fabric-making process": "CN"},
        ),
        corpus=corpus_102_21,
    )
    assert r.origin != "CN"
    assert r.rule_id != "102.21(e)(2)(ii)"


def test_e2_i_is_reached_before_e2_iii(corpus_102_21):
    """(iii) applies only "if the country of origin cannot be determined under
    paragraph (e)(2)(i)"."""
    r = resolve(
        good="6117.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False, conditions={"knit to shape": True},
            dyed_and_printed_in="IT",
            finishing_operations=("bleaching", "fulling"),
            process_in={"knit": "BD"},
        ),
        corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id) == ("IT", "102.21(e)(2)(i)")


def test_e2_iii_a_follows_where_the_components_were_knit(corpus_102_21):
    r = resolve(
        good="6117.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False, conditions={"knit to shape": True},
            process_in={"knit": "BD"},
        ),
        corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id) == ("BD", "102.21(e)(2)(iii)(A)")


def test_e2_iii_b_follows_where_the_good_was_wholly_assembled(corpus_102_21):
    r = resolve(
        good="6117.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False,
            conditions={
                "knit to shape": False,
                "two or more component parts": True,
            },
            process_in={"wholly assembled": "VN"},
        ),
        corpus=corpus_102_21,
    )
    assert (r.origin, r.rule_id) == ("VN", "102.21(e)(2)(iii)(B)")


def test_the_fibre_decides_which_table_applies(corpus_102_21):
    """Of cotton or of wool keeps the good with (e)(1); anything else is
    (e)(2)'s."""
    from originshift.textile import e2_governs

    assert e2_governs("6214.10", TextileFacts(excepted_fibre=True)) is False
    assert e2_governs("6214.10", TextileFacts(excepted_fibre=False)) is True
    assert e2_governs("6214.10", TextileFacts()) is None      # not stated
    assert e2_governs("6203.42", TextileFacts()) is False     # not a listed good

    # The carve-out is one question with three limbs. Answering only one of
    # them settles nothing: "of cotton: False" for a wool scarf must not put it
    # in (e)(2), and dict order must not decide which limb is read.
    assert e2_governs("6214.10", TextileFacts(conditions={"of cotton": False})) is None
    assert e2_governs(
        "6214.10", TextileFacts(conditions={"of cotton": False, "of wool": True})
    ) is False


def test_with_the_fibre_unstated_neither_table_is_picked(corpus_102_21):
    r = resolve(
        good="6214.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(process_in={"fabric-making process": "CN"}),
        corpus=corpus_102_21,
    )
    assert r.status == "unresolved"
    assert "cotton" in r.needed


def test_c2_is_not_stepped_past_while_it_could_still_be_met(corpus_102_21):
    """(c)(3) is only reached where (c)(2) did not determine origin."""
    r = resolve(
        good="6301.30",
        inputs=[Material("5205.11", "CN")],
        country="VN",
        corpus=corpus_102_21,
    )
    assert r.status == "unresolved"
    assert "fabric-making process" in r.needed


def test_c2_is_never_stepped_past_merely_because_a_later_fact_is_known(corpus_102_21):
    """(c)(3) applies "where the country of origin cannot be determined under
    (c)(1) or (2)". An unanswered question is not a finding.

    Supplying an optional (c)(3) fact used to skip (c)(2) silently, changing
    both the cited authority and the country with no flag that (c)(2) had never
    been settled.
    """
    facts = TextileFacts(wholly_assembled_in="VN")
    asked = resolve(
        good="6203.42", inputs=[Material("5208.11", "CN")], country="VN",
        textile=facts, corpus=corpus_102_21,
    )
    assert asked.status == "unresolved"
    assert "(e)(1)" in asked.needed or "102.21(c)(2)" in asked.needed

    facts.c2_does_not_determine = True
    settled = resolve(
        good="6203.42", inputs=[Material("5208.11", "CN")], country="VN",
        textile=facts, corpus=corpus_102_21,
    )
    assert (settled.origin, settled.rule_id) == ("VN", "102.21(c)(3)(ii)")


def test_e2_ii_is_not_applied_until_the_6117_10_question_is_settled(corpus_102_21):
    """(e)(2)(ii) excepts 6117.10 goods that are knit to shape or of two or more
    parts. It follows the fabric-making country; (e)(2)(iii) follows the
    knitting or the assembly — different countries, so it cannot be guessed."""
    unstated = resolve(
        good="6117.10", inputs=[], country="VN", corpus=corpus_102_21,
        textile=TextileFacts(excepted_fibre=False, process_in={"fabric-making process": "CN"}),
    )
    assert unstated.status == "unresolved"
    assert "knit to shape" in unstated.needed

    settled = resolve(
        good="6117.10", inputs=[], country="VN", corpus=corpus_102_21,
        textile=TextileFacts(
            excepted_fibre=False,
            conditions={"knit to shape": False, "two or more component parts": False},
            process_in={"fabric-making process": "CN"},
        ),
    )
    assert (settled.origin, settled.rule_id) == ("CN", "102.21(e)(2)(ii)")


def test_c3_ii_does_not_reach_a_good_stated_knit_to_shape(corpus_102_21):
    """(c)(3)(ii) applies "if the good was not knit to shape". The gate tested
    whether a knitting country had been given, not the fact itself."""
    r = resolve(
        good="6110.20", inputs=[Material("6006.21", "CN")], country="VN",
        corpus=corpus_102_21,
        textile=TextileFacts(
            c2_does_not_determine=True,
            conditions={"knit to shape": True},
            wholly_assembled_in="VN",
        ),
    )
    assert r.status == "unresolved"
    assert r.rule_id == "102.21(c)(3)(i)"
    assert "where it was knit" in r.needed or "in which it was knit" in r.needed


def test_only_fabrics_of_chapter_59_are_excepted_from_c3_ii(corpus_102_21):
    """102.21(c)(3)(ii) excepts "fabrics of chapter 59" — not the chapter.
    Transmission belting of 5910 and machine clothing of 5911 are goods."""
    from originshift.textile import _excepted_from_assembly

    excepted = _excepted_from_assembly()
    assert any(r.contains("5903.10") for r in excepted)
    for good in ("5910.00", "5911.31", "5911.90"):
        assert not any(r.contains(good) for r in excepted), good


def test_the_hair_net_carve_out_travels_with_the_answer(corpus_102_21):
    """102.21(b)(5) reaches "6505.00 (except for hair-nets)". Hair-nets are
    named, not coded, so no classification settles it — and a hair-net belongs
    to 102.20. Neither guess is safe, so the caveat is reported."""
    from originshift.corpus import covered_by_102_21

    assert covered_by_102_21("6505.00")          # ordinary hats are 102.21's
    r = resolve(good="6505.00", inputs=[Material("6001.10", "CN")], country="VN")
    assert any("hair-nets" in c for c in r.caveats)
    assert resolve(good="8708.29", inputs=[Material("7208.10", "CN")], country="VN").caveats == []
