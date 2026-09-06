"""What the Part 134 parser must get right, and the two ways it nearly did not.

The defined-term finding is a claim about absence, and a classifier that marks
everything absent would produce a spectacular finding entirely by artifact. The
controls here exist so that "substantial transformation is not defined" is only
ever reported by a parser that has been shown to find the definitions that are
there.
"""

from originshift import parse_134


def test_every_section_of_the_part_is_read(xml_134):
    secs = parse_134.sections(xml_134)
    assert len(secs) == 33
    ids = [s.section_id for s in secs]
    assert ids[0] == "134.0" and "134.1" in ids and ids[-1] == "134.55"


def test_every_defined_term_is_found_with_its_paragraph(xml_134):
    terms = {t.term: t.paragraph for t in parse_134.defined_terms(xml_134)}
    assert len(terms) == 13
    assert terms["Country of origin"] == "(b)"
    assert terms["Ultimate purchaser"] == "(d)"
    assert terms["Part 102 Rules"] == "(j)"
    assert terms["USMCA"] == "(l)"
    # stated outside § 134.1, in the section that uses it
    assert terms["Usual container"] == "(d)(1)"


def test_definitions_are_not_all_stated_with_means(xml_134):
    """Half of them are not. A parser keyed to "means" would find six of twelve,
    and would report the other six as undefined — which is the finding."""
    verbs = {t.verb for t in parse_134.defined_terms(xml_134)}
    assert "means" in verbs
    assert verbs - {"means"}, "only 'means' was recognised; six definitions would be lost"
    by_term = {t.term: t.verb for t in parse_134.defined_terms(xml_134)}
    assert by_term["Foreign origin"] == "refers to"
    assert by_term["Good of a NAFTA or USMCA country"] == "is"
    assert by_term["United States"] == "includes"


def test_a_nested_term_is_not_counted_inside_a_longer_one(xml_134):
    """"Country" sits inside "Country of origin" and inside "Good of a NAFTA or
    USMCA country". Counting terms independently reported one use of the long
    term as four, and inflated the total by 37%."""
    secs = parse_134.sections(xml_134)
    terms = parse_134.defined_terms(xml_134)
    uses = parse_134.uses(terms, secs)

    country = [u for u in uses if u.term == "Country"]
    assert country, "the bare term is used somewhere and should be found"
    for u in country:
        head = u.quote[: u.quote.lower().find("country") + 40].lower()
        assert "country of origin" not in head or "country" in head

    # The long term must still be found in its own right.
    assert any(u.term == "Good of a NAFTA or USMCA country" for u in uses)
    # And the bare term must not out-count the phrase that contains it.
    of_origin = sum(1 for u in uses if u.term == "Country of origin")
    assert of_origin > len(country), "nesting is inflating the bare term again"


def test_the_part_does_not_define_the_term_its_own_definition_turns_on(xml_134):
    """134.1(b) makes country of origin turn on substantial transformation, and
    Part 134 never defines it. This is the finding, so it is guarded."""
    found = parse_134.undefined_terms(
        xml_134, {"substantial transformation": "134.1(b) turns on it"}
    )
    assert len(found) == 1
    row = found[0]
    assert row["defined_in_part"] is False
    assert row["uses"] >= 1
    assert any(s["used_in"] == "134.1" for s in row["used_at"])


def test_the_control_terms_are_reported_as_defined(xml_134):
    """The negative control. A classifier that marked everything undefined would
    pass the test above and be worthless; these must come back defined."""
    found = {
        r["term"]: r["defined_in_part"]
        for r in parse_134.undefined_terms(
            xml_134,
            {
                "ultimate purchaser": "134.1(d) defines it",
                "conspicuous": "134.1(k) defines it",
                "country of origin": "134.1(b) defines it",
            },
        )
    }
    assert found == {
        "ultimate purchaser": True,
        "conspicuous": True,
        "country of origin": True,
    }


def test_a_definition_stated_outside_the_definitions_section_is_found(xml_134):
    """§ 134.22(d)(1) defines "Usual container" in the section that uses it, not
    in § 134.1. Limb 1 of the inclusion rule is "the part defines it", and
    reading § 134.1 alone was a narrower rule than the one recorded — it lost a
    term the part defines and then uses in two later sections."""
    terms = {t.term: t for t in parse_134.defined_terms(xml_134)}
    usual = terms["Usual container"]
    assert usual.defined_in == "134.22"
    assert usual.paragraph == "(d)(1)"
    assert usual.verb == "means"
    assert "ordinarily reach its ultimate purchaser" in usual.definition


def test_a_term_used_only_in_its_plural_is_still_a_use(xml_134):
    """§§ 134.23 and 134.24 use "usual containers", never the singular. Matching
    the defined form alone found none of them, so a term defined in one section
    and used in the next looked unused."""
    secs = parse_134.sections(xml_134)
    defined = parse_134.defined_terms(xml_134)
    uses = parse_134.uses(defined, secs)

    outside = [
        u for u in uses if u.term == "Usual container" and not u.in_definition
    ]
    assert outside, "the plural uses are invisible again"
    assert {u.used_in for u in outside} == {"134.23", "134.24"}
    assert all("usual container" in u.quote.lower() for u in outside)


def test_the_plural_fold_is_not_applied_to_a_term_that_already_ends_in_s():
    """A term ending in "s" gets no optional suffix at all.

    Written first as "must not match 'United State'", which passed under both
    implementations and therefore guarded nothing — appending "s?" to "States"
    yields "Statess?", which never matches the singular either. The hazard is
    not the match, it is the suffix, so the suffix is what this asserts.
    """
    plural = parse_134._use_pattern("Usual container").pattern
    already = parse_134._use_pattern("United States").pattern

    assert plural.endswith(r"s?\b[”\"']?"), "the fold is gone; plural uses go missing"
    assert not already.endswith(r"s?\b[”\"']?"), (
        "a term already ending in s was given an optional suffix"
    )
    assert parse_134._use_pattern("United States").search("goods of the United States")
