"""Regression tests against the real 19 CFR 102.20 text."""

import re

from collections import Counter


def test_corpus_size_is_stable(rules):
    assert len(rules) == 1032
    assert sum(len(r.alternatives) for r in rules) == 1464


def test_worked_example_from_the_spec(by_htsus):
    rule = by_htsus["8708.29"]
    assert rule.rule_id == "102.20/8708.29"
    (alt,) = rule.alternatives
    assert alt.structured
    assert [str(r) for r in alt.target.ranges] == ["8708.29"]
    (source,) = alt.shift.sources
    assert source.kind == "any_other" and source.level == "subheading"
    assert [str(r) for r in alt.shift.excluded] == ["8708.95"]
    assert alt.shift.fully_decidable


def test_alternatives_split_across_rows_are_rejoined(by_htsus):
    # 0304's second alternative lives on a row with a blank HTSUS cell.
    alts = by_htsus["0304"].alternatives
    assert len(alts) == 2
    assert alts[1].target.description == "fillets of"


def test_enumerated_process_fragments_join_their_parent(by_htsus):
    # "(a) At least one of the following processes: (1) Beveling; ..." continues
    # the alternative it qualifies rather than standing as its own rule.
    #
    # 7301-7307 states two ways to satisfy it, joined by "or a change within
    # heading 7307 …". Held as one alternative, "within heading 7307" — a
    # hundred characters into the second — made the first read as
    # `same_position` when it is `any_other`. They are separated; the process
    # enumeration stays with the alternative it belongs to.
    rule = by_htsus["7301-7307"]
    assert len(rule.alternatives) == 2
    assert "Beveling" in rule.alternatives[1].text
    assert [s.kind for s in rule.alternatives[0].shift.sources] == ["any_other"]


def test_exception_ranges_are_kept_as_ranges(by_htsus):
    """Ranges stay ranges; expanding them would destroy the corpus (spec 4)."""
    residual = by_htsus["9404.30-9404.90"].alternatives[-1]
    assert residual.residual
    excluded = {str(r) for r in residual.shift.excluded}
    assert {"5007", "5208-5212", "6307.90"} <= excluded


def test_percentages_are_not_read_as_chapters(rules):
    """'more than 20% by weight' must not become chapter 20."""
    for rule in rules:
        for alt in rule.alternatives:
            if not alt.shift:
                continue
            named = alt.shift.excluded + [
                r for s in alt.shift.sources for r in s.ranges
            ]
            for r in named:
                if r.level == "chapter":
                    assert re.search(
                        rf"chapters?\s+0?{int(r.start)}\b", alt.text, re.I
                    ), f"{r} not backed by the word 'chapter' in: {alt.text[:120]}"


def test_other_than_carve_out_is_not_read_as_a_positive_source(by_htsus):
    """'from any product other than X of Chapter 2' must not require Chapter 2."""
    alt = by_htsus["0210.91-0210.99"].alternatives[1]
    assert alt.shift.sources == []
    assert alt.shift.excluded_descriptions == ["edible meals and flours of Chapter 2"]
    assert not alt.structured  # honestly abstains rather than inverting the rule


def test_a_source_clause_can_offer_alternatives(by_htsus):
    """'from any other good of subheading X or from any other subheading' is two
    opposite conditions, and collapsing them loses half the rule."""
    alt = next(
        a for a in by_htsus["8486.90"].alternatives if "electrical machines" in a.text
    )
    inside, outside = alt.shift.sources
    assert inside.kind == "same_position"
    assert [str(r) for r in inside.ranges] == ["8486.90"]
    assert outside.kind == "any_other" and outside.level == "subheading"
    # An input inside 8486.90 qualifies under the first branch, so the rule
    # cannot be settled on codes alone.
    assert not inside.decidable_from_codes
    assert not alt.shift.fully_decidable


def test_named_sources_are_positive_not_exclusions(by_htsus):
    """'from Chapter 17' means the input must come from there."""
    alt = next(
        a for a in by_htsus["1602.90"].alternatives if "from Chapter 17," in a.text
    )
    (source,) = alt.shift.sources
    assert source.kind == "named"
    assert [str(r) for r in source.ranges] == ["17"]


def test_mixed_level_spans_are_kept_not_dropped(by_htsus):
    """'heading 1601 through 1602.50' crosses levels; it must still resolve."""
    rule = by_htsus["1601-1602.50"]
    (span,) = rule.scope
    assert (str(span), span.level) == ("1601.00-1602.50", "subheading")
    assert span.contains("1601.10") and span.contains("1602.50")
    assert not span.contains("1602.90")
    assert rule.alternatives[0].target.ranges  # not left unable to match anything


def test_a_target_may_reach_outside_its_htsus_key(by_htsus):
    """The key column is an index, not a boundary.

    The rule keyed 3002.12-3002.90 also targets subheadings in 3822. Indexing on
    the key column alone would silently lose it.
    """
    alt = next(
        a for a in by_htsus["3002.12-3002.90"].alternatives if "imines" in a.text
    )
    assert [str(r) for r in alt.target.ranges] == [
        "3002.12-3002.15",
        "3822.11-3822.12",
        "3822.19",
    ]
    assert alt.target.matches("3822.11")


def test_rule_ids_are_unique(rules):
    """102.20 repeats some HTSUS keys on separate rows."""
    dupes = [k for k, n in Counter(r.rule_id for r in rules).items() if n > 1]
    assert dupes == []
    assert "102.20/2915.39(2)" in {r.rule_id for r in rules}


def test_no_alternative_is_left_unable_to_match(rules):
    """An alternative with no target ranges could never fire, silently."""
    for rule in rules:
        for alt in rule.alternatives:
            if alt.target is not None:
                assert alt.target.ranges, f"{rule.rule_id}: {alt.text[:80]}"


def test_a_compound_statement_splits_into_the_rules_it_states():
    """A phrase in the second branch must not decide the kind of the first."""
    from originshift.parse_102 import split_alternatives

    pieces = split_alternatives(
        "A change to heading 7301 through 7307 from any other heading, "
        "including another heading within that group, or a change within "
        "heading 7307 from fitting forgings to fittings by: (a) Beveling."
    )
    assert len(pieces) == 2
    assert pieces[0].startswith("A change to heading 7301")
    assert pieces[1].startswith("a change within heading 7307")
    # Splitting is a fixed point: a piece holds no further top-level branch.
    assert all(len(split_alternatives(p)) == 1 for p in pieces)


def test_a_single_alternative_is_returned_untouched():
    """Trimming a rule that states one alternative would edit its verbatim text."""
    from originshift.parse_102 import split_alternatives

    text = "A change to subheading 8708.29 from any other subheading, except from subheading 8708.95."
    assert split_alternatives(text) == [text]


def test_an_or_that_joins_codes_is_not_a_branch():
    from originshift.parse_102 import split_alternatives

    text = "A change to subheading 2106.90 from any other subheading, except from heading 0401 or 2202."
    assert split_alternatives(text) == [text]


def test_cbp_writes_ranges_with_a_dash_and_the_regulation_writes_through():
    """Only where a level word introduces it: a bare 1994-2002 is a span of years."""
    from originshift.parse_102 import _ranges

    assert [str(r) for r in _ranges("heading 8701-8705")] == ["8701-8705"]
    assert [str(r) for r in _ranges("heading 8701 - 8705")] == ["8701-8705"]
    assert [str(r) for r in _ranges("the 1994-2002 period")] == ["1994"]
    assert _ranges("more than 20-30 percent") == []


def test_descriptive_rules_abstain_rather_than_guess(rules):
    unstructured = [a for r in rules for a in r.alternatives if not a.structured]
    # Separating compound alternatives raised this from 14. A process clause
    # absorbed into a shift alternative used to be counted as structured while
    # corrupting the shift it was absorbed into.
    assert len(unstructured) == 19
    assert all(a.unparsed_reason for a in unstructured)


def test_every_alternative_keeps_its_verbatim_text(rules):
    for rule in rules:
        for alt in rule.alternatives:
            assert alt.text.strip()


def test_provisos_are_preserved_not_dropped(by_htsus):
    """A value threshold the codes cannot express is kept verbatim, not dropped."""
    alts = by_htsus["1602.90"].alternatives
    provisos = [p for a in alts if a.shift for p in a.shift.provisos]
    assert any("50 percent by weight of milk solids" in p for p in provisos)


def test_transcription_defects_are_reported_not_corrected(rules):
    """102.20 contains typos. Repairing them would put words in the regulation's
    mouth; ignoring them lets one typo answer for a hundred headings."""
    from originshift.build_corpus import anomalies

    found = {(a["rule_id"], a["kind"]) for a in anomalies(rules)}
    assert ("102.20/2824.10-2824.90", "target_far_wider_than_key") in found
    assert ("102.20/4441-4421", "reversed_htsus_key") in found
    # the text itself is left exactly as the regulation has it
    rule = next(r for r in rules if r.htsus == "2824.10-2824.90")
    assert "2824.10 through 2924.90" in rule.text


def test_textile_chapters_are_absent_because_102_21_governs_them(rules):
    """Chapters 50-63 are 102.21's, not 102.20's — their absence is correct."""
    covered = {
        c
        for r in rules
        for s in r.scope
        for c in (re.sub(r"\D", "", s.start)[:2], re.sub(r"\D", "", s.end)[:2])
    }
    assert not covered & {f"{c:02d}" for c in range(50, 64)}
    assert "84" in covered and "01" in covered


def test_a_qualified_exception_keeps_its_qualifier(by_htsus):
    """"except from subheading 8301.60 when that change is pursuant to GRI 2(a)"
    does not bar 8301.60 outright.

    Keeping the code and dropping the qualifier turned a conditional bar into an
    absolute one: the shift falsely failed, and 102.11(b) then handed origin to
    the country of a material the rule in fact allows. 102.18(a) is explicit
    that the exception bites only "if the change results from the assembly of
    parts into an incomplete or unfinished good".
    """
    (alt,) = by_htsus["8301.10-8301.50"].alternatives
    assert alt.shift.excluded == []          # not an absolute bar
    (qualified,) = alt.shift.excluded_when
    assert [str(r) for r in qualified.ranges] == ["8301.60"]
    assert "General Rule of Interpretation 2(a)" in qualified.when


def test_qualified_and_absolute_exceptions_are_told_apart(rules):
    absolute = qualified = 0
    for rule in rules:
        for alt in rule.alternatives:
            if not alt.shift:
                continue
            absolute += bool(alt.shift.excluded)
            qualified += bool(alt.shift.excluded_when)
    assert qualified > 80        # "when resulting from a simple assembly", GRI 2(a)
    assert absolute > 400        # the ordinary kind still outnumbers them
