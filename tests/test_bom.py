"""Walking a bill of materials.

Also guards the two things that stay out, per the reading of US9177286B2 claim 1:
no certificate of origin is produced, and no preferential qualification is done.
"""

import json
from pathlib import Path

from originshift import bom
from originshift.bom import Node, resolve_bom

ROOT = Path(__file__).resolve().parents[1]


def _tree(**over):
    d = {
        "good": "8708.29",
        "country": "MX",
        "label": "door assembly",
        "components": [
            {
                "good": "8708.99",
                "country": "MX",
                "label": "bracket",
                "components": [{"good": "7208.10", "country": "KR"}],
            },
            {"good": "7208.10", "country": "JP", "label": "panel"},
        ],
    }
    d.update(over)
    return Node.from_dict(d)


def test_a_stated_leaf_is_taken_as_given(corpus):
    root = resolve_bom(_tree(), corpus=corpus)
    leaf = next(n for n in root.walk() if n.good == "7208.10" and n.stated)
    assert leaf.origin == "KR"
    assert leaf.result is None  # nothing was determined; it was stated


def test_determination_runs_bottom_up(corpus):
    """A subassembly's origin has to be settled before its parent's rule can be
    applied against it."""
    root = resolve_bom(_tree(), corpus=corpus)
    bracket = next(n for n in root.walk() if n.label == "bracket")
    assert bracket.origin == "MX"
    assert bracket.result.rule_id == "102.20/8708.99"
    assert root.origin == "MX"
    assert root.result.rule_id == "102.20/8708.29"


def test_every_determined_node_cites_its_rule(corpus):
    """A determination a broker cannot trace is not worth filing."""
    root = resolve_bom(_tree(), corpus=corpus)
    for node in root.walk():
        if node.stated:
            continue
        assert node.result.rule_id, f"{node.good} determined without citing a rule"
        assert node.result.vintage


def test_an_unsettled_component_is_recorded_not_swallowed(corpus):
    """A parent standing on an unknown says so."""
    tree = Node.from_dict(
        {
            "good": "8708.29",
            "country": "MX",
            "components": [
                {
                    "good": "2008.11",
                    "country": "CA",
                    "label": "odd part",
                    "components": [{"good": "1202.41", "country": "AR"}],
                },
                {"good": "7208.10", "country": "JP"},
            ],
        }
    )
    root = resolve_bom(tree, corpus=corpus)
    child = next(n for n in root.walk() if n.label == "odd part")
    assert not child.determined
    assert root.blocked_by == ["2008.11 (odd part)"]


def test_an_unsettled_component_is_not_assumed_domestic(corpus):
    """Its country goes up as None, which the resolver reads as foreign."""
    tree = Node.from_dict(
        {
            "good": "8708.29",
            "country": "MX",
            "components": [
                {
                    "good": "2008.11",
                    "country": "CA",
                    "components": [{"good": "1202.41", "country": "AR"}],
                }
            ],
        }
    )
    root = resolve_bom(tree, corpus=corpus)
    assert root.result.basis != "exclusively_domestic"


def test_de_minimis_applies_at_a_node(corpus):
    """The airbag part is 5% of the assembly's value, so 102.13 disregards it."""
    tree = Node.from_dict(
        {
            "good": "8708.29",
            "country": "VN",
            "value": 100.0,
            "components": [
                {"good": "8708.95", "country": "CN", "value": 5.0},
                {"good": "7208.10", "country": "KR", "value": 95.0},
            ],
        }
    )
    root = resolve_bom(tree, corpus=corpus)
    assert root.origin == "VN"
    assert root.result.basis == "tariff_shift_de_minimis"


def test_essential_character_applies_at_a_node(corpus):
    """Where the shift fails, 102.11(b) follows the blocking material upward."""
    tree = Node.from_dict(
        {
            "good": "8708.29",
            "country": "VN",
            "components": [
                {"good": "8708.95", "country": "JP"},
                {"good": "7208.10", "country": "KR"},
            ],
        }
    )
    root = resolve_bom(tree, corpus=corpus)
    assert root.origin == "JP"
    assert root.result.rule_id == "102.11(b)(1)"


def test_the_shipped_example_runs(corpus):
    tree = Node.from_dict(
        json.loads((ROOT / "examples" / "assembly.json").read_text(encoding="utf-8"))
    )
    root = resolve_bom(tree, corpus=corpus)
    assert root.origin == "MX"
    assert bom.render(root)


# ---- patent boundary, per the reading of US9177286B2 claim 1 ----------------


def test_no_certificate_is_produced(corpus):
    """A certificate of origin is a preferential artifact, made to claim a
    benefit under an agreement. This produces a determination."""
    root = resolve_bom(_tree(), corpus=corpus)
    rendered = bom.render(root).lower()
    assert "certificate" not in rendered
    source = (ROOT / "src" / "originshift" / "bom.py").read_text(encoding="utf-8")
    # named only where the module explains why it does not produce one
    assert source.lower().count("certificate") <= 2


def test_nothing_is_stored_between_calls(corpus):
    """Claim 1 requires maintaining item and relationship databases. A BOM
    arrives per call and an answer goes back."""
    first = resolve_bom(_tree(), corpus=corpus)
    second = resolve_bom(_tree(), corpus=corpus)
    assert first is not second
    assert not any(
        name.endswith("_DB") or name.endswith("_STORE") for name in dir(bom)
    )


def test_no_preferential_qualification(corpus):
    """FTA qualification is the patent's home ground and out of scope."""
    root = resolve_bom(_tree(), corpus=corpus)
    bases = {n.result.basis for n in root.walk() if n.result}
    assert bases <= {
        "wholly_obtained",
        "exclusively_domestic",
        "tariff_shift",
        "tariff_shift_de_minimis",
        "essential_character",
        None,
    }
