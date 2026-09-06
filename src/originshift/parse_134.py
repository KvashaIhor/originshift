"""Compile 19 CFR Part 134 into sections, defined terms, and their use sites.

Part 134 is not a rule table, so this does not produce rules. It produces the
three things a defined-term question needs: what the part says, what it defines,
and where it uses what it defined.

The part defines its own central term in a term it does not carry. § 134.1(b)
says country of origin turns on whether further work "effect[s] a substantial
transformation", and Part 134 never defines that phrase — it is common-law case
law with no rule table, the same thing 19 CFR 102 does not implement for Section
301. Recording that absence is the point of this module, so an undefined term is
reported and never guessed at.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

#: A definition paragraph in § 134.1: "(a) Country. “Country” means ...". The
#: heading repeats the term before the definition, which is what makes the term
#: extractable without guessing where a definition starts.
_DEFINITION = re.compile(r"^\(([a-z])\)\s+([^.]{2,70}?)\.\s+(.+)$", re.S)

#: The verbs Part 134 states definitions with. It does not use one: (a) and (b)
#: say "means", (c) says "refers to", (d) and (g) say "is", (e) and (f) say
#: "includes". A parser that only knew "means" would silently miss half of them.
_DEFINING_VERB = re.compile(
    r"\b(means|refers to|is generally|is|are|includes)\b", re.I
)


@dataclass(frozen=True)
class Section:
    """One section of the part, as published."""

    section_id: str
    heading: str
    text: str


@dataclass(frozen=True)
class Term:
    """A term the part defines, and the words it defines it in."""

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
    """A place the part uses a term, with the sentence it uses it in."""

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


def _clean(node) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def sections(xml_text: str) -> list[Section]:
    """Every section of the part, in published order."""
    root = ET.fromstring(xml_text)
    out: list[Section] = []
    for div in root.iter("DIV8"):
        n = div.attrib.get("N")
        if not n:
            continue
        heading = _clean(div.find("HEAD")) if div.find("HEAD") is not None else ""
        body = " ".join(
            _clean(p) for p in div if p.tag == "P" and _clean(p)
        )
        out.append(Section(section_id=n, heading=heading, text=body))
    return out


def defined_terms(xml_text: str, definitions_section: str = "134.1") -> list[Term]:
    """The terms the part defines, read from its definitions section."""
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
            para, term, body = m.group(1), m.group(2).strip(), m.group(3).strip()
            verb = _DEFINING_VERB.search(body)
            out.append(
                Term(
                    term=term,
                    defined_in=definitions_section,
                    paragraph=f"({para})",
                    definition=body,
                    # A definition whose verb we cannot name is still recorded;
                    # the corpus reports what it found rather than dropping it.
                    verb=verb.group(1).lower() if verb else "unstated",
                )
            )
    return out


def _sentences(text: str) -> list[str]:
    # Cheap and deliberate: a legal sentence split that respects "U.S." and
    # section numbers is its own project, and a use site only needs enough
    # context to be readable and checkable against the source.
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text) if s.strip()]


def uses(terms: list[Term], secs: list[Section]) -> list[Use]:
    """Every place a defined term is used, quoted in the sentence around it.

    Longest match wins, because Part 134's terms nest: "Country" sits inside
    "Country of origin", and both sit inside "Good of a NAFTA or USMCA country".
    Counting each term independently reports one use of the long term as four,
    and it is not a small effect — 86 of the 111 occurrences of "Country" in the
    part are inside a longer defined term. A span already claimed by a longer
    term is not offered to a shorter one.
    """
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
                    break  # one use per term per sentence
    return out


def undefined_terms(xml_text: str, candidates: dict[str, str]) -> list[dict]:
    """Terms the part turns on and does not define.

    `candidates` maps a phrase to the reason it matters. Nothing is inferred:
    the caller states which phrases carry weight, and this reports where each is
    used and confirms the part carries no definition for it.
    """
    secs = sections(xml_text)
    defined = {t.term.lower() for t in defined_terms(xml_text)}
    out: list[dict] = []
    for phrase, why in candidates.items():
        sites = [
            {"used_in": s.section_id, "quote": sentence}
            for s in secs
            for sentence in _sentences(s.text)
            if re.search(re.escape(phrase), sentence, re.I)
        ]
        if not sites:
            continue
        out.append(
            {
                "term": phrase,
                "why_it_matters": why,
                "defined_in_part": phrase.lower() in defined,
                "used_at": sites,
                "uses": len(sites),
            }
        )
    return out
