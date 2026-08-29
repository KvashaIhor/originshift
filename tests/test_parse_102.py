"""Regression tests against the real 19 CFR 102.20 text."""


def test_corpus_size_is_stable(rules):
    assert len(rules) == 1032
    assert sum(len(r.alternatives) for r in rules) == 1455


def test_worked_example_from_the_spec(by_htsus):
    rule = by_htsus["8708.29"]
    assert rule.rule_id == "102.20/8708.29"
    (alt,) = rule.alternatives
    assert alt.structured
    assert [str(r) for r in alt.target.ranges] == ["8708.29"]
    assert alt.shift.from_level == "subheading"
    assert [str(r) for r in alt.shift.excluded] == ["8708.95"]


def test_alternatives_split_across_rows_are_rejoined(by_htsus):
    # 0304's second alternative lives on a row with a blank HTSUS cell.
    alts = by_htsus["0304"].alternatives
    assert len(alts) == 2
    assert alts[1].target.description == "fillets of"


def test_enumerated_process_fragments_join_their_parent(by_htsus):
    # "(a) At least one of the following processes: (1) Beveling; ..." continues
    # the alternative above it rather than standing as its own rule.
    rule = by_htsus["7301-7307"]
    assert len(rule.alternatives) == 1
    assert "Beveling" in rule.alternatives[0].text


def test_exception_ranges_are_kept_as_ranges(by_htsus):
    """Ranges stay ranges; expanding them would destroy the corpus (spec 4)."""
    residual = by_htsus["9404.30-9404.90"].alternatives[-1]
    assert residual.residual
    excluded = {str(r) for r in residual.shift.excluded}
    assert {"5007", "5208-5212", "6307.90"} <= excluded


def test_percentages_are_not_read_as_chapters(rules):
    """'more than 20% by weight' must not become chapter 20."""
    import re

    for rule in rules:
        for alt in rule.alternatives:
            if not alt.shift:
                continue
            for r in alt.shift.excluded + alt.shift.from_ranges:
                if r.level == "chapter":
                    assert re.search(
                        rf"chapters?\s+0?{int(r.start)}\b", alt.text, re.I
                    ), f"{r} not backed by the word 'chapter' in: {alt.text[:120]}"


def test_other_than_carve_out_is_not_read_as_a_positive_source(by_htsus):
    """'from any product other than X of Chapter 2' must not require Chapter 2."""
    alt = by_htsus["0210.91-0210.99"].alternatives[1]
    assert alt.shift.from_ranges == []
    assert alt.shift.excluded_descriptions == ["edible meals and flours of Chapter 2"]
    assert not alt.structured  # honestly abstains rather than inverting the rule


def test_descriptive_rules_abstain_rather_than_guess(rules):
    unstructured = [
        a for r in rules for a in r.alternatives if not a.structured
    ]
    assert len(unstructured) == 14
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


def test_named_sources_are_positive_not_exclusions(by_htsus):
    """'from Chapter 17' means the input must come from there."""
    alt = next(
        a for a in by_htsus["1602.90"].alternatives if "from Chapter 17," in a.text
    )
    assert [str(r) for r in alt.shift.from_ranges] == ["17"]
    assert alt.shift.from_level is None
