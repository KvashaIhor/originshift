"""Walk a bill of materials, determining origin at each node.

A single finished good is rarely the real question. The real question is a
product with components, some of which are themselves assemblies — and origin
has to be settled bottom-up, because whether a subassembly is foreign to the
country of final production decides whether the finished good's rule is met.

**This produces a determination, not a certificate.** A certificate of origin is
a preferential artifact, made to claim a benefit under a trade agreement; this
answers the non-preferential question of what country a good is from, and cites
the rule. Nothing here is stored between calls: a BOM arrives, an answer goes
back. Preferential and FTA qualification are out of scope, deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Corpus
from .resolve import Material, OriginResult, resolve


@dataclass
class Node:
    """One item in a bill of materials.

    A leaf is a purchased material and carries the country it came from. A node
    with `components` is produced, and its origin is determined rather than
    stated — `country` on such a node is where the production happened.
    """

    good: str
    country: str | None = None
    components: list[Node] = field(default_factory=list)
    value: float | None = None
    #: Facts the rules may turn on, passed through to the resolver.
    wholly_obtained: bool = False
    is_set: bool = False
    operation: str | None = None
    label: str = ""

    @property
    def is_leaf(self) -> bool:
        return not self.components

    @classmethod
    def from_dict(cls, d: dict) -> Node:
        return cls(
            good=d["good"],
            country=d.get("country"),
            components=[cls.from_dict(c) for c in d.get("components", [])],
            value=d.get("value"),
            wholly_obtained=d.get("wholly_obtained", False),
            is_set=d.get("is_set", False),
            operation=d.get("operation"),
            label=d.get("label", ""),
        )


@dataclass
class NodeResult:
    """What was determined for one node, and from what."""

    good: str
    label: str
    depth: int
    #: None where the node's origin could not be determined.
    origin: str | None
    #: True where the country was given rather than worked out.
    stated: bool
    result: OriginResult | None
    children: list[NodeResult] = field(default_factory=list)
    #: Components whose own origin could not be settled. A parent determined
    #: over these is standing on an unknown, and says so.
    blocked_by: list[str] = field(default_factory=list)

    @property
    def determined(self) -> bool:
        return self.origin is not None

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def _material_for(child: NodeResult, node: Node) -> Material:
    source = next((c for c in node.components if c.good == child.good), None)
    return Material(
        code=child.good,
        country=child.origin,
        value=source.value if source else None,
    )


def resolve_bom(
    node: Node,
    *,
    corpus: Corpus | None = None,
    _depth: int = 0,
) -> NodeResult:
    """Determine origin for a BOM, bottom-up, citing the rule at every step.

    A leaf's origin is whatever the BOM states. A produced node's components are
    determined first, and their determined origins are what the node's own rule
    is then applied against. A component whose own origin could not be settled
    goes up with no country, which the resolver reads as foreign — the
    conservative default — and the parent records it in `blocked_by`, so an
    answer resting on an unsettled component is never mistaken for a clean one.
    """
    corpus = corpus or Corpus.load()

    if node.is_leaf:
        return NodeResult(
            good=node.good,
            label=node.label,
            depth=_depth,
            origin=node.country,
            stated=True,
            result=None,
        )

    children = [
        resolve_bom(child, corpus=corpus, _depth=_depth + 1) for child in node.components
    ]
    materials = [_material_for(child, node) for child in children]

    result = resolve(
        good=node.good,
        inputs=materials,
        country=node.country or "",
        good_value=node.value,
        wholly_obtained=node.wholly_obtained,
        is_set=node.is_set,
        operation=node.operation,
        corpus=corpus,
    )
    unsettled = [
        f"{c.good}" + (f" ({c.label})" if c.label else "")
        for c in children
        if not c.determined
    ]
    return NodeResult(
        good=node.good,
        label=node.label,
        depth=_depth,
        origin=result.origin,
        stated=False,
        result=result,
        children=children,
        blocked_by=unsettled,
    )


def render(root: NodeResult) -> str:
    """A readable derivation: every node, its origin, and the rule that gave it."""
    lines: list[str] = []
    for node in root.walk():
        pad = "  " * node.depth
        name = f"{node.good}" + (f"  ({node.label})" if node.label else "")
        if node.stated:
            lines.append(f"{pad}{name} — {node.origin or 'origin not stated'} (given)")
            continue
        r = node.result
        assert r is not None
        verdict = node.origin or r.status
        lines.append(f"{pad}{name} — {verdict}")
        if r.rule_id:
            lines.append(f"{pad}   rule {r.rule_id}: {(r.rule_text or '')[:100]}")
        if r.basis:
            lines.append(f"{pad}   basis {r.basis}")
        if node.blocked_by:
            lines.append(
                f"{pad}   below   origin not settled for "
                + ", ".join(node.blocked_by)
            )
        if r.needed:
            lines.append(f"{pad}   needs {r.needed[:120]}")
    return "\n".join(lines)
