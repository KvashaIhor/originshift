"""The resolution graph, and the two ways the classifier faked its own finding.

The deliverable is a count of terms a regulation uses without defining, so both
directions of error corrupt it. Crediting a pointer that belongs to a different
term hides real unsigned terms; failing to recognise a pointer form invents
unsigned terms that are not. § 323.2 contains both traps in one sentence, which
is why it is the fixture here.
"""

import pytest

from originshift import parse_134, parse_323, terms

#: § 323.2, the whole prohibition. It resolves "commerce" against the FTC Act and
#: leaves every term of its own three-limb test unresolved, in one sentence.
S323_2 = (
    "In connection with promoting or offering for sale any good or service, in "
    'or affecting commerce as "commerce" is defined in section 4 of the Federal '
    "Trade Commission Act, 15 U.S.C. 44, it is an unfair or deceptive act or "
    "practice within the meaning of section 5(a)(1) of the Federal Trade "
    "Commission Act, 15 U.S.C. 45(a)(1), to label any product as Made in the "
    "United States unless the final assembly or processing of the product occurs "
    "in the United States, all significant processing that goes into the product "
    "occurs in the United States, and all or virtually all ingredients or "
    "components of the product are made and sourced in the United States."
)

OPERATIVE = list(parse_323.OPERATIVE_TERMS)


@pytest.mark.parametrize("phrase", OPERATIVE)
def test_a_pointer_about_another_term_does_not_resolve_this_one(phrase):
    """The first trap. The sentence resolves "commerce"; crediting that pointer
    to the test's own terms reported all five as resolvable and hid the finding
    entirely."""
    resolution, points_at = terms.classify(phrase, S323_2, set(), {})
    assert resolution == terms.UNSIGNED, f"{phrase!r} was credited {points_at!r}"


def test_the_term_the_text_really_does_resolve_is_recognised():
    """The second trap, the mirror of the first. The pointer here is "defined in
    section 4 of the ... Act", not "defined in 15 U.S.C.", and a pattern that
    knew only the citation form marked a resolved term unsigned — which inflates
    the count the article prints."""
    resolution, points_at = terms.classify("commerce", S323_2, set(), {})
    assert resolution == terms.CROSS_AUTHORITY
    assert "Federal Trade Commission Act" in points_at


def test_cross_authority_is_reachable_at_all():
    """Negative control on the control. If binding the pointer to the term made
    this bucket unreachable, every unsigned count would be an artifact."""
    resolution, points_at = terms.classify(
        "domestic material",
        'The term "domestic material" is defined in 19 CFR 102.1(d).',
        set(),
        {},
    )
    assert resolution == terms.CROSS_AUTHORITY
    assert "102" in points_at


def test_a_term_the_part_defines_resolves_in_part():
    assert terms.classify("Conspicuous", "anything", {"conspicuous"}, {})[0] == terms.IN_PART


def test_a_term_defined_by_another_corpus_is_a_cross_part_edge():
    resolution, points_at = terms.classify(
        "Country of origin", "used here", set(), {"country of origin": "19-CFR-134"}
    )
    assert (resolution, points_at) == (terms.CROSS_PART, "19-CFR-134")


def test_the_case_law_term_is_named_not_inferred():
    resolution, why = terms.classify("substantial transformation", "used here", set(), {})
    assert resolution == terms.CASE_LAW
    assert "no rule table" in why


def test_the_graph_over_both_parts(xml_134, xml_323):
    def corpus(name, mod, xml, extra=()):
        secs, ts = mod.sections(xml), mod.defined_terms(xml)
        return {
            "corpus": name,
            "terms": [t.to_dict() for t in ts],
            "uses": [u.to_dict() for u in mod.uses(ts, secs)]
            + [u.to_dict() for u in extra],
        }

    found = parse_134.undefined_terms(
        xml_134, {"substantial transformation": "134.1(b) turns on it"}
    )
    extra = [
        terms.Use(term=r["term"], used_in=s["used_in"], quote=s["quote"])
        for r in found
        for s in r["used_at"]
    ]
    graph = terms.build(
        [
            corpus("19-CFR-134", parse_134, xml_134, extra),
            corpus("16-CFR-323", parse_323, xml_323, parse_323.operative_uses(xml_323)),
        ]
    )

    counts = graph["counts"]
    assert counts[terms.UNSIGNED] == 5, "the five § 323.2 operative terms"
    assert counts[terms.CASE_LAW] == 2, "substantial transformation, twice"
    # The controls: the graph must also find the terms that DO resolve, or the
    # unsigned count above means nothing.
    assert counts[terms.IN_PART] > 100

    unsigned = {e["term"] for e in graph["edges"] if e["resolution"] == terms.UNSIGNED}
    assert unsigned == set(OPERATIVE)
    assert all(
        e["used_in"] == "323.2"
        for e in graph["edges"]
        if e["resolution"] == terms.UNSIGNED
    )


def test_the_ftc_part_never_says_where_its_test_is_defined(xml_323):
    """The rule states the test and does not cite the policy statement that gives
    "all or virtually all" content. Checked against the source, not asserted."""
    assert parse_323.points_at_the_policy_statement(xml_323) is False
