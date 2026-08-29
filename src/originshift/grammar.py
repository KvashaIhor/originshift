"""The type system that origin rules compile into.

Ranges are the primitive, never individual codes (spec 4). Expanding
`8481.10 through 8481.80` into every code it covers destroys the structure that
makes the corpus useful, and inflates it for nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Literal

Level = Literal["chapter", "heading", "subheading", "tariff_item"]

#: Digit count that defines each level of the nomenclature.
LEVEL_DIGITS: dict[str, int] = {
    "chapter": 2,
    "heading": 4,
    "subheading": 6,
    "tariff_item": 8,
}


def digits(code: str) -> str:
    """Strip formatting from an HS code: '8708.29' -> '870829'."""
    return re.sub(r"\D", "", code)


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
        lvl = level_of(start)
        if level_of(end) != lvl:
            raise ValueError(f"range {start}-{end} mixes levels")
        return cls(start=start, end=end, level=lvl)

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
class Shift:
    """A tariff-shift requirement: inputs must cross a boundary of the nomenclature."""

    #: The level the input must change across: "any other subheading" -> subheading.
    from_level: Level | None = None
    #: Ranges the input may not come from, i.e. "except from heading 5208 through 5212".
    excluded: list[CodeRange] = field(default_factory=list)
    #: Exceptions the nomenclature cannot express, e.g. "except from formed uppers"
    #: or "except a change resulting from a simple assembly". Kept verbatim: they
    #: bind legally, so a resolver must not treat their absence as satisfaction.
    excluded_descriptions: list[str] = field(default_factory=list)
    #: Ranges the input must come FROM, where the rule names specific origins
    #: instead of a shift: "A change to subheading 1602.90 from Chapter 4".
    from_ranges: list[CodeRange] = field(default_factory=list)
    #: "outside that group" — inputs from within the target's own span do not count.
    outside_that_group: bool = False
    #: "a change ... within chapter 3" — the change happens inside the level, not across it.
    within_group: bool = False
    #: Free-text conditions the codes cannot express, kept verbatim.
    provisos: list[str] = field(default_factory=list)
    #: Source phrasing that did not reduce to a level, kept for inspection.
    raw_source: str = ""


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
                for key in ("excluded", "from_ranges"):
                    alt["shift"][key] = [
                        str(CodeRange(**r)) for r in alt["shift"][key]
                    ]
            if alt.get("target"):
                alt["target"]["ranges"] = [
                    str(CodeRange(**r)) for r in alt["target"]["ranges"]
                ]
        return d
