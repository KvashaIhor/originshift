"""Parse 19 CFR 102.21(e)(1) into the grammar.

102.21 governs textiles and apparel, and unlike 102.20 it reaches every import
of chapters 50 through 63 rather than only USMCA marking — 102.21(a) makes it
control "for purposes of the Customs laws".

Its rule table is shaped differently in three ways that matter:

* Sub-rules are numbered, and the numbering carries meaning. "(2) If the country
  of origin cannot be determined under (1) above" is reached, not chosen, while
  "(1) If the good is of staple fibers … (2) If the good is of filaments" are
  selected by a fact about the good.
* Many rules are gated on such a fact — of staple fibers, containing
  pharmaceutical substances, except for waste — which no classification settles.
* Codes run to the HTSUS statistical suffix, 3921.90.2550 as well as 5007.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter

from . import parse_102
from .parse_102 import _ranges
from .grammar import Alternative, CodeRange, Rule, Target

REGIME = "US"

#: "(2) If the country of origin cannot be determined under (1) above, …"
_FALLBACK = re.compile(
    r"^If the country of origin cannot be determined under\s*\(?[\d\s(),ori]+?\)?\s*above,?\s*",
    re.I,
)
#: A numbered sub-rule opener, which may carry a letter: "(1)(a)".
_NUMBERED = re.compile(r"^\((?P<n>\d+)\)\s*(?:\((?P<letter>[a-z])\)\s*)?")
#: A fact about the good that gates the rule. 102.21 writes it four ways.
_CONDITION = re.compile(
    r"^(?:If (?P<if>.+?)|Except for (?P<except>.+?)|For (?P<for>.+?)),\s*"
    r"(?=a change|no change|the country of origin)",
    re.I,
)
#: "a change of those filaments … to heading 5604 from …" states the target the
#: other way round from 102.20's "a change to fillets of heading 0304 from …".
_CHANGE_OF = re.compile(r"^A change of (?P<desc>.+?) to (?=\w)", re.I)
#: "The country of origin … is the country … in which the yarn was spun" — origin
#: follows where a named process happened, not a movement between codes.
_PROCESS = re.compile(r"^The country of origin\b", re.I)
#: "A change from greige fabric of heading 5007 to finished fabric of heading
#: 5007 by both dyeing and printing …" — the finishing-operation rules.
_FINISHING = re.compile(
    r"^A change from (?P<from>.+?) to (?P<to>.+?) by (?P<process>.+)$", re.I | re.S
)


def split_alternatives(text: str) -> list[str]:
    """Break a rule into its sub-rules, keeping the numbering.

    The eCFR puts each on its own line, but a rule recovered from the Federal
    Register arrives as one run of prose, so the numbering has to carry the
    split as well.
    """
    parts: list[str] = []
    for line in text.split("\n"):
        for chunk in re.split(r";\s*or\s+(?=If\b)", line):
            # Only where the marker opens a rule. "cannot be determined under
            # (1) above" carries a number that refers to one, not starts one.
            for piece in re.split(
                r"\s+(?=\(\d+\)(?:\([a-z]\))?\s+"
                r"(?:If\b|Except\b|For\b|A change\b|No change\b|The country\b))",
                chunk,
            ):
                piece = piece.strip()
                if piece:
                    parts.append(piece)
    return parts


#: Kept for callers that used the private name.
_split_alternatives = split_alternatives


def parse_alternative(text: str, scope: list[CodeRange]) -> Alternative:
    """Compile one 102.21 sub-rule, keeping what gates it."""
    raw = re.sub(r"\s+", " ", text).strip()
    body = raw

    sequence = None
    m = _NUMBERED.match(body)
    if m:
        sequence = int(m.group("n"))
        body = body[m.end() :]

    is_fallback = False
    m = _FALLBACK.match(body)
    if m:
        is_fallback = True
        body = body[m.end() :]

    condition = None
    m = _CONDITION.match(body)
    if m:
        if m.group("if"):
            condition = m.group("if")
        elif m.group("for"):
            condition = f"the good is {m.group('for')}"
        else:
            condition = f"the good is not {m.group('except')}"
        condition = condition.strip()
        body = body[m.end() :]

    m = _CHANGE_OF.match(body)
    if m:
        # Restate as 102.20 writes it, so the target description is picked up.
        body = f"A change to {m.group('desc')} of " + body[m.end() :]

    if _PROCESS.match(body):
        alt = Alternative(
            kind="process",
            text=raw,
            # A process rule reaches the goods its row is keyed to. Without a
            # target the index cannot find it, and a good it governs looks like
            # a good with no rule.
            target=Target(ranges=_ranges(body) or list(scope)),
            unparsed_reason="process_rule",
        )
        alt.condition = condition
        alt.sequence = sequence
        alt.is_fallback = is_fallback
        return alt

    m = _FINISHING.match(body.rstrip("."))
    if m:
        # Origin turns on where a named process happened, not on a code change.
        alt = Alternative(
            kind="process",
            text=raw,
            target=Target(ranges=_ranges(m.group("to")) or list(scope)),
            unparsed_reason="process_rule",
        )
    else:
        alt = parse_102.parse_alternative(body, scope)
        alt.text = raw

    alt.condition = condition
    alt.sequence = sequence
    alt.is_fallback = is_fallback
    # A gate on the good is a fact no classification carries, so an alternative
    # cannot be treated as met on codes alone.
    if condition and alt.unparsed_reason is None:
        alt.unparsed_reason = "conditional_on_the_good"
    return alt


#: 102.21(b)(5) lists the non-textile-chapter goods the section still covers,
#: in a compressed form: "4202.12.40-89" means 4202.12.40 through 4202.12.89,
#: "6601.10-99" means 6601.10 through 6601.99.
_COVERAGE_ENTRY = re.compile(
    r"^(?P<start>\d{4}(?:\.\d{2,4}){0,2})"
    r"(?:\s*[-–]\s*(?P<end>\d{2,4}))?"
    r"(?:\s*\((?P<note>[^)]*)\))?\s*$"
)


def covered_goods(xml_text: str) -> tuple[list[CodeRange], list[str]]:
    """What 102.21 reaches: chapters 50-63, plus the list in 102.21(b)(5).

    Which hierarchy applies to a good turns on this. 102.11 says in its first
    line that it governs goods *other than* textile and apparel products covered
    by 102.21, so answering a hat or a car seat cover under 102.11 would cite a
    provision that excludes it.
    """
    root = ET.fromstring(xml_text)
    section = next(d for d in root.iter("DIV8") if d.attrib.get("N") == "102.21")

    ranges = [CodeRange.parse(f"{c:02d}") for c in range(50, 64)]
    notes: list[str] = []
    extract = section.find(".//EXTRACT")
    if extract is None:
        return ranges, notes

    for entry in extract.findall("FP-1"):
        text = re.sub(r"\s+", " ", "".join(entry.itertext())).strip()
        m = _COVERAGE_ENTRY.match(text)
        if not m:
            notes.append(text)
            continue
        start = m.group("start")
        end = None
        if m.group("end"):
            # The tail replaces the same number of trailing digits.
            tail = m.group("end")
            end = start[: len(start) - len(tail)] + tail
        try:
            ranges.append(CodeRange.parse(start, end))
        except ValueError:
            notes.append(text)
            continue
        if m.group("note"):
            # "6505.00 (except for hair-nets of subheading 6505.00)". The
            # carve-out names a good, not a code, so no classification settles
            # it — the range stays covered and the exception travels with the
            # corpus for a consumer to apply.
            notes.append(f"{start}: {m.group('note')}")
    return ranges, notes


def parse(xml_text: str, *, vintage: str, source_url: str) -> list[Rule]:
    """Compile the whole of 102.21(e)(1) into Rule records."""
    root = ET.fromstring(xml_text)
    section = next(d for d in root.iter("DIV8") if d.attrib.get("N") == "102.21")
    body = section.find(".//TABLE/TBODY")
    assert body is not None, "102.21(e)(1) table not found"

    grouped: list[dict] = []
    for tr in body.findall("TR"):
        tds = tr.findall("TD")
        if len(tds) != 2:
            continue
        key = parse_102._cell_text(tds[0]).rstrip(". ")
        value = parse_102._cell_text(tds[1])
        if not key:
            if grouped:
                grouped[-1]["cells"].append(value)
            continue
        grouped.append({"htsus": key, "cells": [value]})

    seen: Counter[str] = Counter()
    rules: list[Rule] = []
    for g in grouped:
        parts = re.split(r"\s*[-–]\s*", g["htsus"])
        try:
            scope = [CodeRange.parse(parts[0], parts[1] if len(parts) > 1 else None)]
        except (ValueError, IndexError):
            scope = []

        texts = [p for cell in g["cells"] for p in split_alternatives(cell)]
        # A sub-rule continued on the next row carries no number of its own.
        merged: list[str] = []
        for t in texts:
            if merged and not _NUMBERED.match(t) and not re.match(
                r"^(If|Except|A change|No change)", t, re.I
            ):
                merged[-1] += " " + t
            else:
                merged.append(t)

        seen[g["htsus"]] += 1
        rule_id = f"102.21(e)(1)/{g['htsus']}"
        if seen[g["htsus"]] > 1:
            rule_id = f"{rule_id}({seen[g['htsus']]})"

        rules.append(
            Rule(
                rule_id=rule_id,
                regime=REGIME,
                htsus=g["htsus"],
                scope=scope,
                alternatives=[parse_alternative(t, scope) for t in merged],
                section="102.21(e)(1) Specific rules by tariff classification",
                text=" ".join(merged),
                vintage=vintage,
                source_url=source_url,
            )
        )
    return rules
