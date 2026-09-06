"""Compile 16 CFR Part 323, the FTC Made in USA rule, into terms and use sites.

Six sections and under 700 words, and the whole part turns on one sentence.
§ 323.2 makes it an unfair or deceptive act to label a product Made in the
United States unless three things hold: final assembly or processing in the
United States, all significant processing in the United States, and all or
virtually all ingredients or components made and sourced in the United States.

The part states that test and defines none of the terms in it. § 323.1 defines
what counts as MAKING the claim — "Made in the United States" as a
representation — and never what makes it true. It does not cite the Enforcement
Policy Statement where "all or virtually all" acquires content, either: the
phrase "62 FR 63756" does not appear in the part, and neither does "Enforcement
Policy Statement". A reader of the rule alone cannot resolve the test and is not
told where to look.

Definitions here are written differently from Part 134 — "(a) The term X means"
rather than "(a) X. 'X' means" — and § 323.1(b) defines two terms in one
sentence, so the extractor is separate rather than shared.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .terms import Section, Term, Use

#: "(a) The term Made in the United States means ..." and
#: "(b) The terms mail order catalog and mail order promotional material mean ..."
_DEFINITION = re.compile(
    r"^\(([a-z])\)\s+The\s+terms?\s+(.+?)\s+means?\s+(.+)$", re.S | re.I
)

#: The three limbs of the § 323.2 test, and the terms each turns on. Stated here
#: rather than discovered, so the corpus reports a list a reader can dispute
#: rather than one a regex produced.
OPERATIVE_TERMS = {
    "final assembly or processing": "limb 1 of the § 323.2 test",
    "significant processing": "limb 2 of the § 323.2 test",
    "all or virtually all": "limb 3 of the § 323.2 test",
    "made and sourced": "limb 3, what must be true of the components",
    "ingredients or components": "limb 3, what the test is applied to",
}

#: Where the substantive content of "all or virtually all" actually lives. The
#: part never names it, which is the finding, so the citation is carried here.
POLICY_STATEMENT = (
    "FTC Enforcement Policy Statement on U.S. Origin Claims, 62 FR 63756 "
    "(Dec. 1, 1997)"
)


def _clean(node) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text) if s.strip()]


def sections(xml_text: str) -> list[Section]:
    root = ET.fromstring(xml_text)
    out: list[Section] = []
    for div in root.iter("DIV8"):
        n = div.attrib.get("N")
        if not n:
            continue
        head = div.find("HEAD")
        out.append(
            Section(
                section_id=n,
                heading=_clean(head) if head is not None else "",
                text=" ".join(_clean(p) for p in div if p.tag == "P" and _clean(p)),
            )
        )
    return out


def defined_terms(xml_text: str, definitions_section: str = "323.1") -> list[Term]:
    """The terms the part defines.

    § 323.1(b) defines two terms in one paragraph — "mail order catalog" and
    "mail order promotional material" — so a paragraph can yield more than one
    term and the conjunction has to be split.
    """
    root = ET.fromstring(xml_text)
    out: list[Term] = []
    for div in root.iter("DIV8"):
        if div.attrib.get("N") != definitions_section:
            continue
        for p in div:
            if p.tag != "P":
                continue
            m = _DEFINITION.match(_clean(p))
            if not m:
                continue
            para, named, body = m.group(1), m.group(2), m.group(3).strip()
            for term in re.split(r"\s+and\s+", named):
                term = term.strip().strip("“”\"'")
                if not term:
                    continue
                out.append(
                    Term(
                        term=term,
                        defined_in=definitions_section,
                        paragraph=f"({para})",
                        definition=body,
                        verb="means",
                    )
                )
    return out


def uses(terms: list[Term], secs: list[Section]) -> list[Use]:
    """Every place a defined term is used, longest match claiming the span."""
    ordered = sorted(terms, key=lambda t: len(t.term), reverse=True)
    patterns = [
        (t, re.compile(r"[“\"']?\b" + re.escape(t.term) + r"\b[”\"']?", re.I))
        for t in ordered
    ]
    out: list[Use] = []
    for sec in secs:
        for sentence in _sentences(sec.text):
            claimed: list[tuple[int, int]] = []
            for term, pattern in patterns:
                for m in pattern.finditer(sentence):
                    if any(m.start() < e and s < m.end() for s, e in claimed):
                        continue
                    claimed.append((m.start(), m.end()))
                    out.append(
                        Use(
                            term=term.term,
                            used_in=sec.section_id,
                            quote=sentence,
                            in_definition=sec.section_id == term.defined_in,
                        )
                    )
                    break
    return out


def operative_uses(xml_text: str) -> list[Use]:
    """The § 323.2 test's own terms, as use sites.

    These are not defined anywhere in the part, so no parser would find them by
    looking for definitions. They are located by the phrases the test states,
    which is why OPERATIVE_TERMS is written down rather than derived.
    """
    out: list[Use] = []
    for sec in sections(xml_text):
        for sentence in _sentences(sec.text):
            for phrase in OPERATIVE_TERMS:
                if re.search(re.escape(phrase), sentence, re.I):
                    out.append(
                        Use(term=phrase, used_in=sec.section_id, quote=sentence)
                    )
    return out


def points_at_the_policy_statement(xml_text: str) -> bool:
    """Whether the part tells a reader where "all or virtually all" is defined.

    It does not. Kept as a function rather than a constant so the claim is
    re-checked against the source on every build instead of being asserted.
    """
    whole = " ".join(s.text for s in sections(xml_text))
    return bool(
        re.search(r"62\s*FR\s*63756|Enforcement Policy Statement", whole, re.I)
    )
