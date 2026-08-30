"""Parse 19 CFR 102.20 into the grammar.

102.20 is one HTML-style table of ~1,500 rows in the eCFR XML. Two things make it
harder than a table read:

* A rule's alternatives are split across rows, with the HTSUS column left blank on
  every row after the first.
* Some alternatives continue into enumerated or bulleted fragments on their own
  rows ("(a) At least one of the following processes:", "* Lathes ... or").

Both are joined back together before any grammar is applied.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter

from .grammar import (
    Alternative,
    CodeRange,
    QualifiedExclusion,
    Rule,
    Shift,
    SourceCondition,
    Target,
)

REGIME = "US"

# A code as it appears in the text: 4-digit heading, 6-digit subheading with a dot,
# 8-digit tariff item, or a bare 1-2 digit chapter.
CODE = r"\d{4}(?:\.\d{2}(?:\.\d{2})?)?|\d{1,2}"
LEVEL_WORD = r"chapters?|headings?|subheadings?"

_RANGE = re.compile(
    rf"(?:(?P<lvl>{LEVEL_WORD})\s+)?"
    rf"(?P<start>{CODE})"
    rf"(?:\s*(?:through|to)\s*(?P<end>{CODE}))?",
    re.I,
)
class _Span:
    """Minimal stand-in for a regex match, for the descriptive-source fallback."""

    __slots__ = ("_start", "_end")

    def __init__(self, start: int, end: int) -> None:
        self._start, self._end = start, end

    def start(self) -> int:
        return self._start

    def end(self) -> int:
        return self._end


_CONTINUATION = re.compile(r"^\s*(?:[••]|\([a-z0-9]{1,2}\)\s)", re.I)
_ENUM_ONLY = re.compile(r"^\s*\([a-z0-9]{1,2}\)", re.I)


def _cell_text(el: ET.Element) -> str:
    """Flatten a <TD>, turning <br/> into a newline so alternatives stay separable."""
    out: list[str] = []

    def walk(node: ET.Element, root: bool = False) -> None:
        if node.tag == "br":
            out.append("\n")
        if not root and node.text:
            out.append(node.text)
        for child in node:
            walk(child)
        if not root and node.tail:
            out.append(node.tail)

    if el.text:
        out.append(el.text)
    for child in el:
        walk(child)
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()


def _pad_chapter(code: str) -> str:
    return code.zfill(2) if len(code) <= 2 else code


def _ranges(text: str) -> list[CodeRange]:
    """Pull every code range out of a clause, inferring level from digit count.

    Handles mixed-level lists such as
    "Chapter 4, Chapter 17, heading 2009, or subheading 2202.90".

    A bare one- or two-digit number is only ever read as a chapter when the word
    "Chapter" introduces it. Without that guard, "more than 20% by weight" and
    "no more than 60 percent" silently become chapters 20 and 60 — a wrong
    exclusion that would make the resolver reject valid inputs.
    """
    found: list[CodeRange] = []
    for m in _RANGE.finditer(text):
        lvl = (m.group("lvl") or "").rstrip("s").lower()
        raw_start = m.group("start")
        if len(raw_start) <= 2 and lvl != "chapter":
            continue
        if re.match(r"\s*(?:%|percent|per\s*cent)", text[m.end() :], re.I):
            continue  # a quantity, not a code
        start = _pad_chapter(raw_start)
        end = _pad_chapter(m.group("end")) if m.group("end") else None
        try:
            found.append(CodeRange.parse(start, end))
        except ValueError:
            continue  # a stray number that is not a nomenclature code
    return found


#: A source clause offers alternatives: "X or from Y", "X or any other Z".
#: Splitting needs a lookahead, or the "or" inside a range list gets eaten.
_OR = re.compile(r"\s+or\s+(?=from\s+|any\b|within\b)", re.I)

_SAME_POSITION = re.compile(
    rf"any\s+(?:other\s+)?(?:\w+\s+)?(?:goods?|products?)\s+of\s+(?P<lvl>{LEVEL_WORD})",
    re.I,
)
_ANY_OTHER = re.compile(rf"any\s+(?:other\s+)?(?P<lvl>{LEVEL_WORD})", re.I)
_WITHIN = re.compile(rf"within\s+(?P<lvl>{LEVEL_WORD})", re.I)


def _source_condition(
    phrase: str, scope: list[CodeRange]
) -> SourceCondition | None:
    """Read one branch of a source clause.

    102.20 writes five shapes, and two of them mean opposite things:

        "any other subheading"                  -> outside the target's subheading
        "any subheading outside that group"     -> ditto, across the whole scope
        "any other good of subheading 8486.90"  -> INSIDE 8486.90, a different good
        "any other product of Chapter 4"        -> ditto, at chapter level
        "within chapter 3"                      -> inside chapter 3
        "Chapter 17"                            -> from that named position
    """
    phrase = phrase.strip(" ,.")
    if not phrase:
        return None

    m = _SAME_POSITION.search(phrase)
    if m:
        ranges = _ranges(phrase[m.end() :])
        return SourceCondition(
            kind="same_position",
            level=m.group("lvl").rstrip("s").lower(),  # type: ignore[arg-type]
            ranges=ranges or list(scope),
            text=phrase,
        )

    m = _WITHIN.search(phrase)
    if m:
        ranges = _ranges(phrase[m.end() :])
        return SourceCondition(
            kind="same_position",
            level=m.group("lvl").rstrip("s").lower(),  # type: ignore[arg-type]
            ranges=ranges or list(scope),
            text=phrase,
        )

    m = _ANY_OTHER.search(phrase)
    if m:
        return SourceCondition(
            kind="any_other",
            level=m.group("lvl").rstrip("s").lower(),  # type: ignore[arg-type]
            outside_that_group=bool(re.search(r"outside that group", phrase, re.I)),
            text=phrase,
        )

    ranges = _ranges(phrase)
    if ranges:
        return SourceCondition(kind="named", ranges=ranges, text=phrase)
    return None  # a described good, e.g. "any other product", "feathers or down"


#: An exception carrying its own condition: "except from heading 8501 when
#: resulting from simple assembly", "except from subheading X when that change
#: is pursuant to General Rule of Interpretation 2(a)".
_QUALIFIER = re.compile(
    r"\s*(?P<when>(?:when|if|where)\b.+)$", re.I | re.S
)


def _split_qualified(exceptions: str) -> tuple[str, list[QualifiedExclusion]]:
    """Separate exceptions that bite outright from those that bite on a condition.

    102.18(a) is explicit that a GRI 2(a) exception applies only "if the change
    results from the assembly of parts into an incomplete or unfinished good".
    Keeping the codes and dropping the qualifier turns a conditional bar into an
    absolute one, and the shift then fails for changes the rule allows.
    """
    plain: list[str] = []
    qualified: list[QualifiedExclusion] = []
    for clause in re.split(r",?\s*(?:and\s+)?except\b", exceptions, flags=re.I):
        if not clause.strip():
            continue
        m = _QUALIFIER.search(clause)
        if m and _ranges(clause[: m.start()]):
            qualified.append(
                QualifiedExclusion(
                    ranges=_ranges(clause[: m.start()]),
                    when=m.group("when").strip(" ,."),
                )
            )
        else:
            plain.append(clause)
    return " except ".join(plain), qualified


def _split_provisos(source: str) -> tuple[str, list[str]]:
    """Peel off 'provided that ...' conditions, which codes cannot express."""
    provisos: list[str] = []
    while True:
        m = re.search(r",?\s*provided(?:,| that)\s", source, re.I)
        if not m:
            return source.strip(), provisos
        provisos.append(source[m.start() :].strip(" ,."))
        source = source[: m.start()]


def _parse_target(text: str) -> tuple[Target, str | None]:
    """Split 'a change to X' into codes plus any narrowing description."""
    excluding = None
    m = re.search(r",?\s*other than (?:a change to )?(.+?),\s*from\b", text, re.I)
    if m:
        excluding = m.group(1).strip()
        text = text[: m.start()] + " from" + text[m.end() :]

    ranges = _ranges(text)
    # Anything before the first code, minus the level word, narrows the target.
    desc = None
    first = _RANGE.search(text)
    if first:
        lead = text[: first.start()].strip(" ,")
        lead = re.sub(rf"\b(?:{LEVEL_WORD})\b\s*$", "", lead, flags=re.I).strip(" ,")
        if lead and lead.lower() not in {"a good of", "goods of", "a", "an"}:
            desc = lead
    else:
        desc = text.strip(" ,") or None
    return Target(ranges=ranges, description=desc, excluding_description=excluding), None


def parse_alternative(text: str, scope: list[CodeRange]) -> Alternative:
    """Compile one alternative into the grammar, or record why it could not be."""
    raw = re.sub(r"\s+", " ", text).strip()
    body = raw.rstrip(".; ")

    # A residual rule catches whatever the alternatives above it did not:
    # "For all other goods classified in X, a change from Y" is the same shape as
    # "A change to X from Y", plus a flag that it applies last.
    residual = False
    rm = re.match(
        r"^For all other goods classified in\s+(?P<scope>.+?),\s*a change from\s+(?P<src>.+)$",
        body,
        re.I | re.S,
    )
    if rm:
        residual = True
        body = f"A change to {rm.group('scope')} from {rm.group('src')}"

    m = re.match(r"^A change to\s+(.*)$", body, re.I | re.S)
    if not m:
        if re.match(r"^A change from\s+", body, re.I):
            # 9007.20, and a drafting slip at 8524.11-8524.99 that writes
            # "A change from ... from ..." where "A change to" was meant.
            return Alternative(
                kind="tariff_shift",
                text=raw,
                residual=residual,
                unparsed_reason="reverse_phrasing",
            )
        return Alternative(
            kind="process", text=raw, residual=residual, unparsed_reason="not_a_shift"
        )

    rest = m.group(1)
    # Split target from source at the last top-level " from " that starts a source
    # phrase, so descriptions containing "from" do not break the split.
    # Prefer an unambiguous source opener; only then accept a named source, so a
    # "from" inside a target description does not steal the split.
    STRONG = r"(?:any|within|outside)\b"
    NAMED = rf"(?:a|an|the|{LEVEL_WORD})\b|\d"
    split = None
    for pattern in (STRONG, NAMED):
        for sm in re.finditer(r"\s+from\s+", rest, re.I):
            if re.match(pattern, rest[sm.end() :], re.I):
                split = sm
                break
        if split is not None:
            break
    if split is None:
        # The source names a good rather than a nomenclature position
        # ("from mustard flour or meal"). Split after the target's own code so
        # the target is still usable, and let the resolver report the gap.
        first_code = _RANGE.search(rest)
        after = first_code.end() if first_code else 0
        tail = next((m for m in re.finditer(r"\s+from\s+", rest[after:], re.I)), None)
        if tail is None:
            return Alternative(
                kind="process",
                text=raw,
                residual=residual,
                unparsed_reason="no_source_clause",
            )
        split = _Span(after + tail.start(), after + tail.end())

    target_text, source_text = rest[: split.start()], rest[split.end() :]
    target, _ = _parse_target(target_text)
    if not target.ranges:
        target.ranges = list(scope)

    source_text, provisos = _split_provisos(source_text)

    exm = re.search(r",?\s*(?:and\s+)?except\b", source_text, re.I)
    base, exceptions_text = (
        (source_text[: exm.start()], source_text[exm.end() :])
        if exm
        else (source_text, "")
    )
    unconditional_text, qualified = _split_qualified(exceptions_text)

    # "from any product other than edible meals and flours of Chapter 2" excludes
    # those goods; it does not require the input to come from Chapter 2. Peel the
    # carve-out off before reading codes, or the sense of the rule inverts.
    carve_out = None
    om = re.search(r"\bother than\b", base, re.I)
    if om:
        carve_out = base[om.end() :].strip(" ,.")
        base = base[: om.start()].strip(" ,")

    excluded = _ranges(unconditional_text)
    # An exception with no codes in it is a description, and still binds.
    # Only where nothing at all was captured — a qualified exception is now
    # modelled, not left as an unreadable description.
    captured = bool(excluded) or bool(qualified)
    excluded_desc = (
        [] if captured or not exceptions_text.strip() else [exceptions_text.strip(" ,.")]
    )
    if carve_out:
        excluded_desc.append(carve_out)
    branches = [
        _source_condition(p, scope) for p in _OR.split(base) if p.strip()
    ]
    sources = [b for b in branches if b is not None]

    shift = Shift(
        sources=sources,
        excluded=excluded,
        excluded_when=qualified,
        excluded_descriptions=excluded_desc,
        provisos=provisos,
        raw_source=source_text.strip(),
    )

    reason = None
    if not sources:
        # e.g. "from any other product", "from feathers or down": the source is a
        # description. A resolver cannot decide this from HS codes alone.
        reason = "descriptive_source"
    elif len(sources) < len(branches):
        reason = "partly_descriptive_source"

    return Alternative(
        kind="tariff_shift",
        shift=shift,
        target=target,
        text=raw,
        residual=residual,
        unparsed_reason=reason,
    )


def _rows(xml_text: str) -> tuple[list[tuple[str, str, str | None]], ET.Element]:
    root = ET.fromstring(xml_text)
    section = next(
        d for d in root.iter("DIV8") if d.attrib.get("N") == "102.20"
    )
    body = section.find(".//TABLE/TBODY")
    assert body is not None, "102.20 table not found"

    out: list[tuple[str, str, str | None]] = []
    heading: str | None = None
    for tr in body.findall("TR"):
        tds = tr.findall("TD")
        if len(tds) != 2:
            continue
        if tds[0].find("strong") is not None or tds[1].find("strong") is not None:
            heading = _cell_text(tds[1])
            continue
        out.append((_cell_text(tds[0]).rstrip(". "), _cell_text(tds[1]), heading))
    return out, root


def parse(xml_text: str, *, vintage: str, source_url: str) -> list[Rule]:
    """Compile the whole of 102.20 into Rule records."""
    rows, _ = _rows(xml_text)

    grouped: list[dict] = []
    for htsus, value, heading in rows:
        if not htsus:  # continuation of the rule above
            if grouped:
                grouped[-1]["branches"].append(value)
            continue
        grouped.append({"htsus": htsus, "section": heading, "branches": [value]})

    # 102.20 repeats a few HTSUS keys on separate rows (2915.39, 3102.90,
    # 3104.90, 3808.99), so the key alone is not a unique identifier.
    seen: Counter[str] = Counter()

    rules: list[Rule] = []
    for g in grouped:
        # Re-join fragments that continue the alternative above them.
        branches: list[str] = []
        for b in g["branches"]:
            for piece in (p.strip() for p in b.split("\n")):
                if not piece:
                    continue
                if branches and _CONTINUATION.match(piece) and not re.match(
                    r"^A change\b", piece, re.I
                ):
                    branches[-1] += " " + piece
                elif branches and _ENUM_ONLY.match(piece):
                    branches[-1] += " " + piece
                else:
                    branches.append(piece)

        parts = re.split(r"\s*[-–]\s*", g["htsus"])
        try:
            scope = [CodeRange.parse(parts[0], parts[1] if len(parts) > 1 else None)]
        except (ValueError, IndexError):
            scope = []

        seen[g["htsus"]] += 1
        occurrence = seen[g["htsus"]]
        rule_id = f"102.20/{g['htsus']}"
        if occurrence > 1:
            rule_id = f"{rule_id}({occurrence})"

        rules.append(
            Rule(
                rule_id=rule_id,
                regime=REGIME,
                htsus=g["htsus"],
                scope=scope,
                alternatives=[parse_alternative(b, scope) for b in branches],
                section=g["section"],
                text=" ".join(branches),
                vintage=vintage,
                source_url=source_url,
            )
        )
    return rules
