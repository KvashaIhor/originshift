"""The vocabulary a defined-term corpus is written in, and the graph over it.

A rule corpus answers "what does this rule say". This answers a different
question: for a term the regulation turns on, where is it defined, where is it
used, and — the case the whole exercise exists for — where is it used by a part
that does not define it and does not say where to look.

The resolutions are deliberately five, not two. "Defined" and "undefined" would
put a term resolved by an explicit pointer to another part in the same bucket as
a term the reader is simply expected to already know, and the difference between
those two is the finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: How a use site resolves. Ordered from most to least resolvable.
IN_PART = "in_part"
CROSS_PART = "cross_part"
CROSS_AUTHORITY = "cross_authority"
CASE_LAW = "case_law"
UNSIGNED = "unsigned"

RESOLUTIONS = (IN_PART, CROSS_PART, CROSS_AUTHORITY, CASE_LAW, UNSIGNED)


@dataclass(frozen=True)
class Section:
    """One section of a part, as published."""

    section_id: str
    heading: str
    text: str

    def to_dict(self) -> dict:
        return {"section_id": self.section_id, "heading": self.heading, "text": self.text}


@dataclass(frozen=True)
class Term:
    """A term a part defines, and the words it defines it in."""

    term: str
    defined_in: str
    paragraph: str
    definition: str
    verb: str

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "defined_in": self.defined_in,
            "paragraph": self.paragraph,
            "definition": self.definition,
            "verb": self.verb,
        }


@dataclass(frozen=True)
class Use:
    """A place a part uses a term, with the sentence it uses it in."""

    term: str
    used_in: str
    quote: str
    in_definition: bool = field(default=False)

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "used_in": self.used_in,
            "quote": self.quote,
            "in_definition": self.in_definition,
        }


#: An explicit pointer out of the part. These are what separate `cross_part` and
#: `cross_authority` from `unsigned`: the text names where to look, so a reader
#: who follows it arrives somewhere. A term with no pointer is the finding.
_POINTER = re.compile(
    r"""(
        # "defined in 19 CFR 102.1", and also "defined in section 4 of the
        # Federal Trade Commission Act" — § 323.2 resolves "commerce" the second
        # way, and a pattern that only knew the first reported a term the text
        # plainly resolves as unsigned, which inflates the finding.
        (?:as\s+)?defined\s+in\s+
            (?:(?:\d+\s+)?(?:CFR|C\.F\.R\.|U\.S\.C\.|§)[^,.;]{0,40}
             |section\s+\d+[^,.;]{0,60})
      | provided\s+for\s+in\s+paragraph\s*\([a-z]\)(?:\(\d+\))?
      | set\s+forth\s+in\s+(?:\d+\s+)?(?:CFR|C\.F\.R\.|part|§)[^,.;]{0,40}
      | (?:\d+)\s+U\.S\.C\.\s+\d+
      | (?:\d+)\s+CFR\s+(?:part\s+)?\d+
    )""",
    re.I | re.X,
)

#: A term whose content lives in decided cases rather than in any published
#: rule text. Named explicitly rather than inferred: the corpus says which terms
#: it treats this way, and a reader can disagree with the list.
CASE_LAW_TERMS = {
    "substantial transformation": (
        "common-law test with no rule table; 19 CFR 102 does not implement it "
        "for Section 301 or 232 either"
    ),
}


#: How close a pointer has to sit to the term for it to be that term's pointer.
#: Wide enough for "X, as defined in 19 CFR 102.1", narrow enough that a pointer
#: about a different term in the same sentence does not get credited.
_BINDING_WINDOW = 60


def _bound_pointer(phrase: str, quote: str) -> str | None:
    """A pointer in `quote` only counts if it is a pointer to `phrase`.

    § 323.2 is one long sentence that resolves "commerce" against 15 U.S.C. 44
    while leaving every term of its own test unresolved. Crediting any pointer in
    the sentence to whatever term was being scored reported all five operative
    terms as `cross_authority` — resolvable — and hid the finding completely.
    """
    for m in _POINTER.finditer(quote):
        before = quote[max(0, m.start() - _BINDING_WINDOW) : m.start()]
        if re.search(re.escape(phrase), before, re.I):
            return re.sub(r"\s+", " ", m.group(1)).strip()
        if re.search(re.escape(phrase), m.group(1), re.I):
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


def _own_part(section_id: str) -> str:
    return section_id.split(".")[0]


def classify(
    phrase: str,
    quote: str,
    defined_here: set[str],
    defined_elsewhere: dict[str, str],
) -> tuple[str, str | None]:
    """Where a use of `phrase` resolves, and what it points at.

    `defined_here` is the set of terms the using part defines. `defined_elsewhere`
    maps a term to the corpus that defines it. `quote` is the sentence, which is
    where an explicit pointer would be if there is one.
    """
    low = phrase.lower()
    if low in defined_here:
        return IN_PART, None
    if low in CASE_LAW_TERMS:
        return CASE_LAW, CASE_LAW_TERMS[low]
    if low in defined_elsewhere:
        return CROSS_PART, defined_elsewhere[low]
    pointer = _bound_pointer(phrase, quote)
    if pointer:
        return CROSS_AUTHORITY, pointer
    return UNSIGNED, None


def build(corpora: list[dict]) -> dict:
    """The resolution graph over one or more compiled defined-term corpora.

    Each corpus is a dict with `corpus`, `terms` and `uses` as emitted by a
    parser. Resolution is a property of the USE and not of the term, because the
    same term can be signed in one section and unsigned in another, and folding
    that into a term-level attribute hides the variation worth reporting.
    """
    defined_elsewhere: dict[str, str] = {}
    for c in corpora:
        for t in c["terms"]:
            defined_elsewhere.setdefault(t["term"].lower(), c["corpus"])

    edges: list[dict] = []
    for c in corpora:
        here = {t["term"].lower() for t in c["terms"]}
        others = {k: v for k, v in defined_elsewhere.items() if k not in here}
        for u in c["uses"]:
            if u.get("in_definition"):
                continue
            resolution, points_at = classify(u["term"], u["quote"], here, others)
            edges.append(
                {
                    "corpus": c["corpus"],
                    "term": u["term"],
                    "used_in": u["used_in"],
                    "resolution": resolution,
                    "points_at": points_at,
                    "quote": u["quote"],
                }
            )

    counts: dict[str, int] = {r: 0 for r in RESOLUTIONS}
    for e in edges:
        counts[e["resolution"]] += 1
    return {
        "corpora": [c["corpus"] for c in corpora],
        "counts": counts,
        "edges": edges,
    }
