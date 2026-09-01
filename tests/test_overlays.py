"""An overlay files rules into a corpus, and filing them into the wrong one is
silent.

The 102.20 rules recovered from CBP Dec. 22-25 were first compiled with the
default parser and authority, which made them `102.21(e)(1)` rules extending
the textile corpus. 102.20 kept its gaps, 102.21 gained coal-tar oils and
asbestos articles, every answer for them cited a paragraph that does not
contain them, and the whole suite passed.
"""

import json

import pytest

from originshift.corpus import OVERLAY_DIR, Corpus


@pytest.fixture(scope="module")
def overlays():
    files = sorted(OVERLAY_DIR.glob("*.json"))
    assert files, "no overlays ship with the package"
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def test_every_overlay_extends_a_corpus_that_exists(overlays):
    names = {Corpus.load().name, Corpus.load(which="102.21").name}
    for o in overlays:
        assert o["extends"] in names, (
            f"overlay {o['overlay']} extends {o['extends']!r}, which is no corpus; "
            "it will be skipped by every loader and silently do nothing"
        )


def test_an_overlay_rule_id_names_the_authority_it_claims(overlays):
    for o in overlays:
        for rule in o["rules"]:
            assert rule["rule_id"].startswith(o["authority"]), (
                f"{rule['rule_id']} claims authority {o['authority']}; a rule that "
                "cites a provision it was not filed under is a wrong citation"
            )


def test_no_overlay_puts_a_good_into_a_corpus_that_does_not_govern_it():
    """102.21 states its own coverage at (b)(5), and an overlaid rule for a good
    outside it would answer under a provision that excludes that good.

    Scoped to overlaid rules on purpose. The (e)(1) table itself keys some
    entries more broadly than (b)(5) covers — `9619` against a covered range of
    9619.00.31-.33 — so the primary text is not the thing being asserted here.
    """
    c = Corpus.load(which="102.21")
    assert c.covers, "the textile corpus no longer states its coverage"
    strays = [
        rid
        for rid in c.overlaid
        for rule in [next(r for r in c.rules if r.rule_id == rid)]
        if not any(c.reaches(str(s).split("-")[0]) for s in rule.scope)
    ]
    assert not strays, f"overlaid goods 102.21 does not govern: {strays}"


def test_the_recovered_102_20_rules_are_reachable():
    """The point of the overlay: these answer, and say where they came from."""
    c = Corpus.load()
    for code in ("2707.10", "2707.99", "6812.99"):
        assert c.candidates(code), f"no rule for {code}; the overlay is not applied"
    prov = c.provenance_of("102.20/6812.99")
    assert prov and prov["reviewed_by"], "a recovered rule must name its reviewer"
    assert "87 FR 68340" in prov["origin"]


def test_the_6812_self_exception_stays_flagged():
    """The rule excepts a subheading from itself. It reads like an extraction
    defect and is CBP's own wording, so the overlay has to say so — otherwise
    someone eventually "fixes" it into divergence from the law."""
    c = Corpus.load()
    rule, _ = c.candidates("6812.99")[0]
    assert "except from subheading 6812.80 and 6812.99" in rule.alternatives[-1].text
    note = c.provenance_of(rule.rule_id)["note"]
    assert "must not be corrected" in note, (
        "the overlay no longer warns that the self-exception is CBP's wording"
    )
