"""The type system that origin rules compile into.

Ranges are the primitive, never individual codes (spec 4). Expanding
`8481.10 through 8481.80` into every code it covers destroys the structure that
makes the corpus useful, and inflates it for nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Literal

Level = Literal[
    "chapter", "heading", "subheading", "tariff_item", "statistical_suffix"
]

#: Digit count that defines each level of the nomenclature. The last two are
#: US-specific: the HTSUS adds a tariff item, and a statistical reporting
#: number beneath the six-digit subheading the HS defines internationally.
LEVEL_DIGITS: dict[str, int] = {
    "chapter": 2,
    "heading": 4,
    "subheading": 6,
    "tariff_item": 8,
    "statistical_suffix": 10,
}

#: A code as written in either rule table: 3921.90.2550 as well as 8708.29.
CODE_PATTERN = r"\d{4}(?:\.\d{2}(?:\.\d{2,4})?)?|\d{1,2}"


def digits(code: str) -> str:
    """Strip formatting from an HS code: '8708.29' -> '870829'."""
    return re.sub(r"\D", "", code)


def _format(d: str) -> str:
    """Render a digit string in the conventional dotted form."""
    if len(d) <= 4:
        return d
    out = f"{d[:4]}.{d[4:6]}"
    return f"{out}.{d[6:]}" if len(d) > 6 else out


def _widen(code: str, level: Level, *, low: bool) -> str:
    """Restate a coarse code at a finer level, spanning everything it covers.

    Heading 1601 at subheading level is 1601.00 as a lower bound and 1601.99 as
    an upper one.
    """
    d = digits(code).ljust(LEVEL_DIGITS[level], "0" if low else "9")
    return _format(d)


def level_of(code: str) -> Level:
    n = len(digits(code))
    for name, size in LEVEL_DIGITS.items():
        if n == size:
            return name  # type: ignore[return-value]
    raise ValueError(f"{code!r} is not a chapter, heading, subheading or tariff item")


@dataclass(frozen=True)
class CodeRange:
    """An inclusive span of the nomenclature, e.g. heading 0101 through 0106.

    A range is compared at its own level: `0101-0106` contains `0104.10`,
    because the first four digits of the candidate fall inside the span.
    """

    start: str
    end: str
    level: Level

    @classmethod
    def parse(cls, start: str, end: str | None = None) -> CodeRange:
        end = end or start
        lo, hi = level_of(start), level_of(end)
        if lo != hi:
            # 102.20 writes spans like "heading 1601 through 1602.50" that cross
            # levels. Restate both ends at the finer level, so the span stays
            # exact rather than being dropped for being irregular.
            fine = lo if LEVEL_DIGITS[lo] > LEVEL_DIGITS[hi] else hi
            start = _widen(start, fine, low=True)
            end = _widen(end, fine, low=False)
            lo = fine
        return cls(start=start, end=end, level=lo)

    def contains(self, code: str) -> bool:
        """Is `code` inside this range, compared at this range's level?"""
        width = LEVEL_DIGITS[self.level]
        d = digits(code)
        if len(d) < width:
            return False  # too coarse to place; caller must ask a broader question
        return digits(self.start) <= d[:width] <= digits(self.end)

    def __str__(self) -> str:
        return self.start if self.start == self.end else f"{self.start}-{self.end}"


@dataclass
class Target:
    """What the rule is about: the good whose origin is in question."""

    ranges: list[CodeRange] = field(default_factory=list)
    #: Narrowing description where the rule targets a named good rather than a
    #: whole code span, e.g. "fillets of heading 0304". Carries legal force, so
    #: it is preserved rather than dropped.
    description: str | None = None
    #: A carve-out inside the target, e.g. "other than smoked goods of heading 0307".
    excluding_description: str | None = None

    def matches(self, code: str) -> bool:
        return any(r.contains(code) for r in self.ranges)

    @property
    def needs_human_judgement(self) -> bool:
        """True when a code alone cannot decide whether the rule applies."""
        return bool(self.description or self.excluding_description)


@dataclass
class SourceCondition:
    """One way the input material may qualify, under a shift.

    102.20 routinely offers several in the alternative:

        "from any other good of subheading 8486.90 or from any other subheading"

    Those two are opposites — inside that subheading, or outside it — so
    collapsing them into a single condition inverts half the rule.
    """

    #: any_other      — input classified outside the target's own position at `level`
    #: same_position  — input inside `ranges`, but a different good
    #: named          — input must come from `ranges`
    kind: Literal["any_other", "same_position", "named"]
    level: Level | None = None
    ranges: list[CodeRange] = field(default_factory=list)
    #: "any other heading outside that group" — the whole scope, not just the
    #: target's own heading, is off limits as a source.
    outside_that_group: bool = False
    text: str = ""

    @property
    def decidable_from_codes(self) -> bool:
        """A same-position source turns on which *good* it is, not its code.

        Two goods can share a subheading, so no HS code can settle it and a
        resolver must ask rather than assume.
        """
        return self.kind != "same_position"


@dataclass
class Shift:
    """A tariff-shift requirement: where the input material may come from."""

    #: Disjunction — the shift is met if any one source condition is met.
    sources: list[SourceCondition] = field(default_factory=list)
    #: Ranges the input may not come from: "except from heading 5208 through 5212".
    excluded: list[CodeRange] = field(default_factory=list)
    #: Exceptions the nomenclature cannot express, e.g. "except from formed uppers"
    #: or "except a change resulting from a simple assembly". Kept verbatim: they
    #: bind legally, so a resolver must not treat their absence as satisfaction.
    excluded_descriptions: list[str] = field(default_factory=list)
    #: Free-text conditions the codes cannot express, kept verbatim.
    provisos: list[str] = field(default_factory=list)
    #: Source phrasing as it appeared, for inspection.
    raw_source: str = ""

    @property
    def fully_decidable(self) -> bool:
        return (
            bool(self.sources)
            and all(s.decidable_from_codes for s in self.sources)
            and not self.excluded_descriptions
            and not self.provisos
        )


@dataclass
class Alternative:
    """One way of satisfying a rule. A rule is satisfied if any alternative is."""

    kind: Literal["tariff_shift", "process", "unstructured"]
    shift: Shift | None = None
    target: Target | None = None
    text: str = ""
    #: True for a rule that applies only to goods the earlier alternatives did not
    #: reach: "For all other goods classified in subheading 9404.30 through 9404.90".
    residual: bool = False
    #: A fact about the good that gates this alternative, e.g. "the good is of
    #: staple fibers" or "the good contains pharmaceutical substances". Like a
    #: named target, it cannot be settled from a classification.
    condition: str | None = None
    #: Position within an ordered rule. 102.21(e)(1) numbers its sub-rules, and
    #: some are tried only when the ones before them did not determine origin.
    sequence: int | None = None
    #: True where the sub-rule opens "If the country of origin cannot be
    #: determined under (1) above" — it is reached, not chosen.
    is_fallback: bool = False
    #: Set when the parser could not fully structure this alternative.
    unparsed_reason: str | None = None

    @property
    def structured(self) -> bool:
        return self.kind == "tariff_shift" and self.unparsed_reason is None


@dataclass
class Rule:
    """One row of a rules-of-origin table, with its source pinned."""

    rule_id: str
    regime: str
    htsus: str
    scope: list[CodeRange]
    alternatives: list[Alternative]
    section: str | None
    text: str
    vintage: str
    source_url: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["scope"] = [str(r) for r in self.scope]
        for alt in d["alternatives"]:
            if alt.get("shift"):
                alt["shift"]["excluded"] = [
                    str(CodeRange(**r)) for r in alt["shift"]["excluded"]
                ]
                for src in alt["shift"]["sources"]:
                    src["ranges"] = [str(CodeRange(**r)) for r in src["ranges"]]
            if alt.get("target"):
                alt["target"]["ranges"] = [
                    str(CodeRange(**r)) for r in alt["target"]["ranges"]
                ]
        return d
