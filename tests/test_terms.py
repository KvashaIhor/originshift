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


def test_the_emitted_corpora_pass_their_own_self_check():
    """Layer 1. Every definition and quote in the shipped corpus must be findable
    in the section it names. A check that has never failed proves nothing, so
    test_the_self_check_detects_a_fabricated_record holds the other side."""
    import json

    from originshift import paths

    for name in ("134", "323"):
        matches = sorted((paths.PACKAGE_DATA / "corpus").glob(f"{name}-*.json"))
        assert matches, f"{name} corpus not built"
        corpus = json.loads(matches[-1].read_text(encoding="utf-8"))
        assert corpus["self_check"]["passed"], corpus["self_check"]
        assert corpus["source_issue_date"]
        assert corpus["source_url"].startswith("https://www.ecfr.gov/")


def test_the_self_check_detects_a_fabricated_record(xml_134):
    """The control on layer 1."""
    from originshift import build_terms

    secs = parse_134.sections(xml_134)
    defined = parse_134.defined_terms(xml_134)
    used = parse_134.uses(defined, secs)
    assert build_terms._self_check(secs, defined, used)["passed"]

    invented = [
        *defined,
        terms.Term(
            term="Invented",
            defined_in="134.1",
            paragraph="(z)",
            definition="This sentence appears nowhere in the CFR.",
            verb="means",
        ),
    ]
    bad = build_terms._self_check(secs, invented, used)
    assert bad["passed"] is False
    assert "Invented" in bad["definitions_not_found_in_source"]

    misquoted = [
        *used,
        terms.Use(term="Country", used_in="134.55", quote="Not in that section."),
    ]
    bad = build_terms._self_check(secs, defined, misquoted)
    assert bad["passed"] is False
    assert "Country@134.55" in bad["quotes_not_found_in_source"]


def test_the_ftc_corpus_records_where_the_missing_content_lives():
    import json

    from originshift import paths

    corpus = json.loads(
        sorted((paths.PACKAGE_DATA / "corpus").glob("323-*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    note = corpus["notes"][0]
    assert note["part_points_at_it"] is False
    assert "62 FR 63756" in note["content_lives_at"]


def test_every_shipped_corpus_states_the_issue_date_it_is_pinned_to():
    """The pin belongs in the artifact, not only in the code that made it.
    Someone holding the file can then see what it is pinned to without reading
    the builder — which is the whole provenance argument."""
    import json

    from originshift import paths

    built = sorted((paths.PACKAGE_DATA / "corpus").glob("*.json"))
    corpora = [p for p in built if not p.name.startswith("terms-graph")]
    assert corpora
    for path in corpora:
        corpus = json.loads(path.read_text(encoding="utf-8"))
        assert corpus["pinned_issue_date"] == corpus["source_issue_date"], (
            f"{path.name} was built off its pin"
        )


def test_a_rebuild_from_cache_writes_nothing(tmp_path):
    """Defect 1. `built_on` is the day the file was generated, so embedding it
    made every rebuild dirty the tree with identical inputs. Comparison ignores
    that field, so an unchanged corpus is not rewritten."""
    import json

    from originshift import paths

    corpus = {"corpus": "X", "built_on": "2026-01-01", "terms": [], "uses": []}
    path = tmp_path / "x.json"

    assert paths.write_if_changed(path, corpus) is True
    before = path.read_bytes()

    later = {**corpus, "built_on": "2026-12-31"}
    assert paths.write_if_changed(path, later) is False
    assert path.read_bytes() == before, "a later build date rewrote the file"

    changed = {**corpus, "terms": [{"term": "new"}]}
    assert paths.write_if_changed(path, changed) is True
    assert json.loads(path.read_text())["terms"] == [{"term": "new"}]


def test_each_corpus_pins_its_issue_date():
    """Defect 2. eCFR titles move independently — title 16 advanced to
    2026-08-31 while title 19 stayed at 2026-08-26 — so a build defaulting to
    latest emits a graph whose filename names one vintage and whose contents
    name two."""
    from originshift import build_terms

    for spec in build_terms.CORPORA.values():
        assert spec["pinned_issue_date"], "a corpus with no pin follows eCFR silently"


def test_the_shipped_graph_is_single_vintage():
    import json

    from originshift import paths

    graph = json.loads(
        sorted((paths.PACKAGE_DATA / "corpus").glob("terms-graph-*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    dates = set(graph["source_issue_dates"].values())
    assert len(dates) == 1, f"graph mixes vintages: {graph['source_issue_dates']}"


def test_cross_authority_is_populated_from_the_text_not_from_curation():
    """Defect 3. The inventory used to be only the terms we went looking for, so
    the graph reported cross_authority = 0 while § 323.2's own resolution of
    "commerce" sat inside the quoted span of every unsigned edge."""
    import json

    from originshift import paths

    graph = json.loads(
        sorted((paths.PACKAGE_DATA / "corpus").glob("terms-graph-*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    cross = [e for e in graph["edges"] if e["resolution"] == terms.CROSS_AUTHORITY]
    assert cross, "no cross_authority edge; the inventory is curated again"
    assert any(e["term"].lower() == "commerce" for e in cross)
    # and the findings must survive the wider inventory
    assert graph["counts"][terms.UNSIGNED] == 5
    assert graph["counts"][terms.CASE_LAW] == 2


def test_the_inclusion_rule_is_recorded_in_the_corpus():
    import json

    from originshift import paths

    corpus = json.loads(
        sorted((paths.PACKAGE_DATA / "corpus").glob("134-*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    assert "quoting it" in corpus["inclusion_rule"]


def test_a_plural_of_a_defined_term_is_not_unsigned():
    """Counting "ultimate purchasers" as undefined because § 134.1 defines the
    singular would inflate the finding with the regulation's own grammar."""
    assert (
        terms.classify("ultimate purchasers", "used here", {"ultimate purchaser"}, {})[0]
        == terms.IN_PART
    )


def test_the_ftc_overlay_annotates_without_resolving():
    """The regulation's silence is the finding. An overlay that supplied the
    missing definition and let the edge resolve would delete what is being
    reported, so it annotates and the edge stays unsigned."""
    import json

    from originshift import paths

    graph = json.loads(
        sorted((paths.PACKAGE_DATA / "corpus").glob("terms-graph-*.json"))[-1].read_text(
            encoding="utf-8"
        )
    )
    annotated = [e for e in graph["edges"] if "content_lives_at" in e]
    assert annotated, "the FTC overlay supplied nothing"

    edge = next(e for e in annotated if e["term"].lower() == "all or virtually all")
    assert edge["resolution"] == terms.UNSIGNED, (
        "the overlay resolved the edge; the finding has been deleted"
    )
    supplied = edge["content_lives_at"]
    assert "62 FR 63756" in supplied["content_lives_at"]
    assert supplied["reviewed_by"]
    assert supplied["is_binding_rule_text"] is False, (
        "enforcement policy is not rule text and must not be presented as it"
    )
    # and the count is untouched
    assert graph["counts"][terms.UNSIGNED] == 5


def test_the_overlay_carries_reviewed_by_provenance():
    """An overlay is a hand-fed document. It states who read it against what,
    like every other overlay in this package."""
    import json

    from originshift.corpus import OVERLAY_DIR

    path = OVERLAY_DIR / "terms" / "ftc-musa-policy-statement-1997.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    prov = doc["provenance"]
    assert prov["origin"].startswith("62 FR 63756")
    assert prov["sha256"] and len(prov["sha256"]) == 64
    assert "reviewed_by" in prov and prov["reviewed_by"].strip()
    assert "does NOT make" in prov["note"], "the note must say what it does not do"
