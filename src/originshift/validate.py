"""Score the corpus against CBP's own determinations.

Ground truth is CROSS: binding rulings by the authority whose rules this corpus
compiles. Rule fidelity — did we get the same rule CBP applied? — is only
measurable on HQ rulings, because NY rulings state no reasoning (spec 6).

Comparison is structural, not textual. CBP quotes the regulation loosely: it
pluralises "heading", writes headings in the HS dotted form (48.17 for 4817),
and runs the quote into its own prose. None of that changes the rule, so the
quoted text is parsed with the same grammar as the corpus and the structures are
compared.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from . import parse_102, sources
from .corpus import Corpus
from .grammar import Alternative

Verdict = Literal["equivalent", "differs", "target_absent", "unparsed"]

#: A rule quotation ends at the first period that is not inside a code.
#:
#: 102.20 states every rule as a change between codes. 102.21 does not: most of
#: its rules confer origin on the place of a process ("the country in which the
#: fabric comprising the good was formed by a fabric-making process") or gate on
#: a fact about the good. Scoring only the "A change to" form would measure the
#: third of 102.21 that happens to be code-shaped, and flatter the result.
_SENTENCE = r"(?:[^.]|\.(?=\d))+?\.(?!\d)"
QUOTED_RULE = re.compile(
    r"(?:"
    r"A change to " + _SENTENCE
    + r"|The country of origin of (?:a|the) good[s]? classifiable " + _SENTENCE
    + r"|If the good (?:is|was|does|consists) " + _SENTENCE
    + r")",
    re.I,
)

#: Where CBP's own prose resumes. A rule never contains these, and a quotation
#: that runs past its closing punctuation picks up codes that are not part of it.
NARRATIVE = re.compile(
    r"\b(since|because|therefore|accordingly|constitutes|and thus|in this instance"
    r"|the only materials|we note|in your|you state|the importer|petitioner"
    r"|is satisfied|is not satisfied|the applicable tariff shift)\b",
    re.I,
)

#: 102.21(c)(1) to (c)(5) are the hierarchy, quoted constantly in these rulings.
#: They are not entries in the (e)(1) table and scoring them there would measure
#: the wrong thing.
#: The tell is the subject. An (e)(1) rule is about "a good classifiable under
#: heading 6301"; a (c) hierarchy step is about "the good", with no code named.
HIERARCHY_RESTATEMENT = re.compile(
    r"the country of origin of the good is the single country"
    r"|^If the good was knit to shape"
    r"|knit to shape and (?:was )?wholly assembled"
    r"|most important assembly or manufacturing"
    r"|last country .{0,40}important assembly"
    r"|wholly obtained or produced\b(?!.{0,40}heading)"
    r"|in which the good was knit\b"
    r"|wholly assembled in a single country, territory, or insular possession\.",
    re.I,
)

#: The longest rule in 102.20 runs to about 1,800 characters, so the cap is only
#: a backstop for a quotation that never found its closing punctuation.
MAX_RULE_CHARS = 1900

#: A quote counts only where CBP attributes it to the part being scored. Rulings
#: that cite 102.20 routinely also quote USMCA and NAFTA preferential rules,
#: worded almost identically and a different legal test; rulings that cite
#: 102.21 quote 102.20 and the preferential annexes alongside it.
ATTRIBUTION = re.compile(r"102\.20")
ATTRIBUTION_21 = re.compile(r"102\.21")
ATTRIBUTION_WINDOW = 400


def ruling_set(part: str) -> set[str] | None:
    """The rulings indexed for a part, so the two sets are scored apart."""
    index = sources.CACHE / f"cross-hq-{part}-index.json"
    if not index.exists():
        return None
    return {r["rulingNumber"] for r in json.loads(index.read_text(encoding="utf-8"))}


def plain_text(ruling: dict) -> str:
    body = ruling.get("text") or ""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


def normalise(quote: str) -> str:
    """Undo CBP's quoting habits, which change the wording but not the rule."""
    q = html.unescape(quote).replace("’", "'")
    q = re.sub(r"\b(heading|subheading|chapter)s\b", r"\1", q, flags=re.I)
    # HS writes headings as 48.17; the HTSUS and this corpus write 4817.
    q = re.sub(r"\b(\d{2})\.(\d{2})\b(?!\.\d)", r"\1\2", q)
    return re.sub(r"\s+", " ", q).strip()


def signature(alt: Alternative) -> tuple:
    """What makes two statements of a rule the same rule."""
    if alt.target is None:
        return ()
    if alt.shift is None:
        # A process rule is the same rule if it reaches the same goods and
        # turns on the same operation. There is no shift to compare.
        return (
            tuple(sorted({str(r) for r in alt.target.ranges})),
            ("process",),
            _process_words(alt.text),
        )
    return (
        tuple(sorted({str(r) for r in alt.target.ranges})),
        tuple(sorted({(s.kind, s.level or "") for s in alt.shift.sources})),
        tuple(sorted({str(r) for r in alt.shift.excluded})),
    )


def quoted_rules(text: str, attribution: re.Pattern | None = None) -> list[str]:
    """Every statement of a 102.20 rule in a ruling, and nothing else.

    Two things have to be got right or the score is measuring the wrong thing:
    the quote must be attributed to 102.20 rather than to a preferential annex,
    and it must stop where the rule stops.
    """
    attribution = attribution or ATTRIBUTION
    out: list[str] = []
    for match in QUOTED_RULE.finditer(text):
        window = text[max(0, match.start() - ATTRIBUTION_WINDOW) : match.start()]
        if not attribution.search(window):
            continue
        quote = match.group()
        # A restatement of the 102.21(c) hierarchy is not an (e)(1) table rule
        # and must not be scored as one.
        if HIERARCHY_RESTATEMENT.search(quote):
            continue
        resumed = NARRATIVE.search(quote)
        if resumed:
            quote = quote[: resumed.start()].rstrip(" ,;")
        if 25 < len(quote) <= MAX_RULE_CHARS:
            out.append(quote.strip())
    return out


#: The operations 102.21 confers origin on. Two process rules are the same rule
#: when they reach the same goods and name the same operation.
_PROCESSES = (
    "fabric-making process",
    "knit",
    "wholly assembled",
    "spinning",
    "extrusion",
    "dyed and printed",
    "garnetting",
    "most important assembly",
    "last important assembly",
)


def _process_words(text: str) -> tuple[str, ...]:
    low = text.lower()
    return tuple(p for p in _PROCESSES if p in low)


@dataclass
class FidelityCase:
    ruling: str
    year: str
    quoted: str
    verdict: Verdict
    corpus_rule_id: str | None = None
    detail: str = ""


@dataclass
class Report:
    """The three numbers spec 6 asks for, reported separately."""

    rulings_examined: int = 0
    rulings_quoting_a_rule: int = 0
    cases: list[FidelityCase] = field(default_factory=list)

    @property
    def by_verdict(self) -> Counter:
        return Counter(c.verdict for c in self.cases)

    @property
    def fidelity(self) -> float:
        """Of the rules CBP quoted, how many does the corpus hold as CBP stated?"""
        decided = [c for c in self.cases if c.verdict != "unparsed"]
        if not decided:
            return 0.0
        return sum(c.verdict == "equivalent" for c in decided) / len(decided)

    def stratify(self) -> dict[str, tuple[int, float, float]]:
        """Score by era. A corpus answers under one nomenclature vintage, so
        agreement with older rulings is expected to fall away — and does."""
        eras = {"1994-2002": ("1990", "2002"), "2003-2019": ("2003", "2019"),
                "2020-2026": ("2020", "2026")}
        out: dict[str, tuple[int, float, float]] = {}
        for name, (lo, hi) in eras.items():
            cases = [c for c in self.cases if lo <= c.year <= hi]
            decided = [c for c in cases if c.verdict != "unparsed"]
            if not cases or not decided:
                continue
            placed = sum(c.verdict in ("equivalent", "differs") for c in cases)
            equivalent = sum(c.verdict == "equivalent" for c in decided)
            out[name] = (len(cases), placed / len(cases), equivalent / len(decided))
        return out

    @property
    def coverage(self) -> float:
        """Of the rules CBP quoted, how many does the corpus place at all?"""
        if not self.cases:
            return 0.0
        placed = sum(c.verdict in ("equivalent", "differs") for c in self.cases)
        return placed / len(self.cases)


def check_quote(
    quote: str, corpus: Corpus, grammar=None
) -> tuple[Verdict, str | None, str]:
    """Compare one quoted rule against the corpus, structurally.

    The grammar has to match the part: 102.21 states most of its rules as a
    process or a condition on the good, which the 102.20 grammar cannot read.
    """
    grammar = grammar or parse_102
    alt = grammar.parse_alternative(normalise(quote), scope=[])
    if alt.target is None or not alt.target.ranges:
        return "unparsed", None, "the quotation does not parse as a rule"

    want = signature(alt)
    anchor = alt.target.ranges[0].start
    candidates = corpus.candidates(anchor)
    if not candidates:
        return "target_absent", None, f"no rule in the corpus targets {anchor}"

    for rule, corpus_alt in candidates:
        if signature(corpus_alt) == want:
            return "equivalent", rule.rule_id, ""

    rule, corpus_alt = candidates[0]
    return (
        "differs",
        rule.rule_id,
        f"corpus holds {signature(corpus_alt)}, CBP quoted {want}",
    )


def run(
    corpus: Corpus | None = None,
    cache_dir: Path | None = None,
    *,
    attribution: re.Pattern | None = None,
    only: set[str] | None = None,
    grammar=None,
) -> Report:
    """Score a corpus against every cached HQ ruling that quotes its part.

    `only` restricts to a set of ruling numbers, so the 102.20 and 102.21 sets
    are scored apart — the cache holds both and a ruling citing one routinely
    quotes the other.
    """
    corpus = corpus or Corpus.load()
    cache_dir = cache_dir or (sources.CACHE / "cross")

    report = Report()
    for path in sorted(cache_dir.glob("*.json")):
        if only is not None and path.stem not in only:
            continue
        ruling = json.loads(path.read_text(encoding="utf-8"))
        text = plain_text(ruling)
        report.rulings_examined += 1

        quotes = set(quoted_rules(text, attribution))
        if not quotes:
            continue
        report.rulings_quoting_a_rule += 1

        year = (ruling.get("rulingDate") or "")[:4]
        for quote in sorted(quotes):
            verdict, rule_id, detail = check_quote(quote, corpus, grammar)
            report.cases.append(
                FidelityCase(
                    ruling=ruling["rulingNumber"],
                    year=year,
                    quoted=quote,
                    verdict=verdict,
                    corpus_rule_id=rule_id,
                    detail=detail,
                )
            )
    return report


# --------------------------------------------------------------------------
# 102.21: which step of the hierarchy did CBP reach?
# --------------------------------------------------------------------------

_CH = r"(?:[^.]|\.(?=\d))"
STEP_CITED = re.compile(
    rf"{_CH}{{0,140}}?102\.21\(c\)\((?P<step>\d)\)(?:\((?P<sub>[ivx]+)\))?"
    rf"{_CH}{{0,140}}?\.(?!\d)",
    re.I,
)
_STEP_RECITED = re.compile(r"\bstates?\b|\bprovides?\b|reads|set forth|following rules", re.I)
_STEP_DENIED = re.compile(
    r"cannot be determined|not applicable|inapplicable|does not (?:apply|confer)", re.I
)
_STEP_APPLIED = re.compile(
    r"\bis applicable\b|\bapplies\b|pursuant to|in accordance with"
    r"|by application of|conferred|country of origin is",
    re.I,
)
#: A ruling covering several fact patterns has no single answer to compare.
_MULTI_SCENARIO = re.compile(r"\bscenario\b|\bstyle #|\bcountry [ABC]\b", re.I)
_GOOD_CODE = re.compile(
    r"(?:classifiable|classified) (?:in|under)\s+(?:sub)?heading\s+"
    r"(\d{4}(?:\.\d{2,4}){0,2})",
    re.I,
)


@dataclass
class StepCase:
    ruling: str
    year: str
    step: str
    good: str | None
    reachable: bool | None  # None where the good could not be identified


def applied_step(text: str) -> str | None:
    """The one paragraph of 102.21(c) a ruling applied, if it applied just one."""
    applied = set()
    for m in STEP_CITED.finditer(text):
        sentence = m.group()
        if _STEP_RECITED.search(sentence) or _STEP_DENIED.search(sentence):
            continue
        if _STEP_APPLIED.search(sentence):
            applied.add(m.group("step") + (m.group("sub") or ""))
    if len(applied) != 1 or _MULTI_SCENARIO.search(text):
        return None
    return applied.pop()


def steps(corpus: Corpus, cache_dir: Path | None = None) -> list[StepCase]:
    """Where CBP applied 102.21(c)(2), can this corpus reach (c)(2) at all?

    Not a full agreement measure — the production facts are not extractable at
    scale — but it catches the failure that matters: a rule CBP could satisfy
    that this corpus offers no route to.
    """
    from .textile import (
        E2_GOODS,
        TextileFacts,
        _condition_holds,
        _e2_ranges,
        _process_named,
    )

    cache_dir = cache_dir or (sources.CACHE / "cross")
    only = ruling_set("102.21") or set()

    out: list[StepCase] = []
    for path in sorted(cache_dir.glob("*.json")):
        if path.stem not in only:
            continue
        ruling = json.loads(path.read_text(encoding="utf-8"))
        text = plain_text(ruling)
        step = applied_step(text)
        if step is None:
            continue

        codes = [c for c, _ in Counter(_GOOD_CODE.findall(text)).most_common()]
        good = next((c for c in codes if corpus.reaches(c)), None)
        reachable = None
        if good:
            # (c)(2) is met by a requirement in either table, so a good (e)(2)
            # takes has a route through it even where (e)(1) offers none.
            reachable = any(r.contains(good) for r in _e2_ranges()) or any(
                (alt.structured or _process_named(alt.text))
                for _, alt in corpus.candidates(good)
                if _condition_holds(alt.condition, TextileFacts(), good) is not False
            )
        out.append(
            StepCase(
                ruling=ruling["rulingNumber"],
                year=(ruling.get("rulingDate") or "")[:4],
                step=step,
                good=good,
                reachable=reachable,
            )
        )
    return out


@dataclass
class TextileCase:
    ruling: str
    year: int
    cbp_step: str
    cbp_country: str
    our_step: str | None
    our_country: str | None
    detail: str

    @property
    def country_agrees(self) -> bool:
        return self.our_country == self.cbp_country

    @property
    def step_agrees(self) -> bool:
        return self.our_step == self.cbp_step


#: rule_id -> the paragraph of 102.21(c) that carried the answer.
_STEP_OF = {
    "102.21(c)(1)": "1",
    "102.21(c)(3)(i)": "3i",
    "102.21(c)(3)(ii)": "3ii",
    "102.21(c)(4)": "4",
    "102.21(c)(5)": "5",
}


def _step_reached(result) -> str | None:
    """Which paragraph the resolver landed on. Anything answered out of (e)(1)
    or (e)(2) is (c)(2), since that is the step those tables serve."""
    rule = result.rule_id or ""
    if rule in _STEP_OF:
        return _STEP_OF[rule]
    if rule.startswith("102.21(e)"):
        return "2"
    return None


def textiles(corpus: Corpus | None = None, path: Path | None = None) -> list[TextileCase]:
    """Run the resolver over the curated textile cases and compare with CBP."""
    from .resolve import resolve
    from .textile import TextileFacts

    corpus = corpus or Corpus.load(which="102.21")
    path = path or (CASES / "textile-cases.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    out: list[TextileCase] = []
    for case in data["cases"]:
        raw = dict(case.get("facts", {}))
        wholly_obtained = raw.pop("wholly_obtained", False)
        facts = TextileFacts(**raw)
        result = resolve(
            good=case["good"],
            inputs=[],
            country=case["country"],
            wholly_obtained=wholly_obtained,
            textile=facts,
            corpus=corpus,
        )
        out.append(
            TextileCase(
                ruling=case["ruling"],
                year=case["year"],
                cbp_step=case["step"],
                cbp_country=case["country"],
                our_step=_step_reached(result),
                our_country=result.origin,
                detail=result.reason or result.needed or (result.rule_id or ""),
            )
        )
    return out


def report_textiles(cases: list[TextileCase]) -> None:
    right = [c for c in cases if c.country_agrees]
    same_step = [c for c in cases if c.step_agrees]
    print(f"curated textile cases            : {len(cases)}")
    print(f"   reached CBP's country         : {len(right)}/{len(cases)}")
    print(f"   by the same paragraph of (c)  : {len(same_step)}/{len(cases)}")
    for case in cases:
        mark = "ok " if case.country_agrees else "NO "
        step = "" if case.step_agrees else f"  [CBP (c)({case.cbp_step}), we (c)({case.our_step})]"
        print(
            f"   {mark}[{case.ruling} {case.year}] {case.cbp_country} / "
            f"{case.our_country or '-'}{step}"
        )
        if not case.country_agrees:
            print(f"        {case.detail[:150]}")


def report_steps(cases: list[StepCase]) -> None:
    by_step = Counter(c.step for c in cases)
    print(f"rulings applying exactly one 102.21(c) step : {len(cases)}")
    for step, n in sorted(by_step.items()):
        print(f"   {n:>4}  (c)({step})")

    two = [c for c in cases if c.step == "2" and c.reachable is not None]
    if two:
        ok = [c for c in two if c.reachable]
        print()
        print(f"of the (c)(2) cases with an identifiable good : {len(two)}")
        print(f"   this corpus offers a route to (c)(2)      : {len(ok)}/{len(two)}")
        for case in two:
            if not case.reachable:
                print(f"     no route: {case.ruling} ({case.good})")
    unknown = sum(1 for c in cases if c.reachable is None)
    if unknown:
        print()
        print(f"   good not identifiable from the text       : {unknown}")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--disagreements",
        action="store_true",
        help="print each disagreement in full, for reading",
    )
    args = ap.parse_args()

    print("=" * 74)
    print("AGREEMENT — does the resolver reach CBP's conclusion on the facts?")
    print("=" * 74)
    report_agreement(agreement())
    print()
    print("=" * 74)
    print("RULE FIDELITY — does the corpus hold the rule CBP applied? (102.20)")
    print("=" * 74)

    report = run(only=ruling_set("102.20"))
    print(f"HQ rulings examined      : {report.rulings_examined}")
    print(f"  quoting a 102.20 rule  : {report.rulings_quoting_a_rule}")
    print(f"  rule quotations        : {len(report.cases)}")
    print()
    for verdict, n in report.by_verdict.most_common():
        print(f"  {n:>4}  {verdict}")
    print()
    print(f"coverage      : {report.coverage:.1%}  (quoted rules the corpus places)")
    print(f"rule fidelity : {report.fidelity:.1%}  (placed rules matching CBP's text)")

    print("\nby era of the ruling (the corpus answers under HTSUS 2026):")
    for era, (n, cov, fid) in report.stratify().items():
        print(f"   {era}  n={n:<4} coverage={cov:6.1%}  fidelity={fid:6.1%}")

    from . import parse_102_21

    corpus_21 = Corpus.load(which="102.21")
    print()
    print("=" * 74)
    print("102.21 — TEXTILES AND APPAREL")
    print("=" * 74)
    t = run(
        corpus_21,
        attribution=ATTRIBUTION_21,
        only=ruling_set("102.21"),
        grammar=parse_102_21,
    )
    print(f"HQ rulings examined      : {t.rulings_examined}")
    print(f"  quoting an (e)(1) rule : {t.rulings_quoting_a_rule}")
    print(f"  rule quotations        : {len(t.cases)}")
    print(f"  coverage               : {t.coverage:.1%}")
    print(f"  rule fidelity          : {t.fidelity:.1%}")
    print()
    report_steps(steps(corpus_21))
    print()
    report_textiles(globals()["textiles"](corpus_21))

    if args.disagreements:
        print("\n" + "=" * 74)
        print("DISAGREEMENTS — read these; they are not all corpus defects.")
        print("=" * 74)
        for case in report.cases:
            if case.verdict in ("equivalent",):
                continue
            print(f"\n[{case.ruling} {case.year}] {case.verdict}")
            print(f"  CBP quoted : {case.quoted[:200]}")
            if case.detail:
                print(f"  {case.detail[:200]}")



# --------------------------------------------------------------------------
# Agreement: does the resolver reach CBP's conclusion on the facts?
# --------------------------------------------------------------------------

CASES = Path(__file__).resolve().parents[2] / "data" / "validation"


@dataclass
class AgreementCase:
    ruling: str
    year: int
    cbp: str
    ours: str
    agrees: bool | None  # None where the resolver declined to decide
    detail: str
    #: Set only where the ruling states both the materials' origins and the
    #: country CBP held, so the whole hierarchy can be scored rather than the
    #: shift alone.
    cbp_country: str | None = None
    our_country: str | None = None


#: A resolved good says nothing on its own about whether the 102.20 shift held.
#: Reaching 102.11(b) at all means it did not — that is why the hierarchy moved
#: on — so the shift verdict has to be read from the basis, not from `satisfied`.
SHIFT_HELD = {"tariff_shift", "tariff_shift_de_minimis"}
SHIFT_FAILED = {"essential_character"}


def _our_verdict(result) -> tuple[str, str]:
    """Reduce an OriginResult to the question CBP answered: did the shift hold?"""
    if result.status == "ambiguous":
        return "ambiguous", result.reason or ""
    if result.reason == "no_rule_for_this_classification":
        return "no_rule", result.needed or ""
    if result.basis in SHIFT_FAILED:
        return "not_met", result.reason or ""
    if result.satisfied is True:
        return "met", result.rule_id or ""
    if result.satisfied is False:
        return "not_met", (result.needed or "")
    return "abstained", (result.needed or "")


def agreement(corpus: Corpus | None = None, path: Path | None = None) -> list[AgreementCase]:
    """Run the resolver over the curated cases and compare with CBP."""
    from .resolve import resolve

    corpus = corpus or Corpus.load()
    path = path or (CASES / "agreement-cases.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    from .resolve import Material

    out: list[AgreementCase] = []
    for case in data["cases"]:
        origins = case.get("origins", {})
        materials = [Material(code, origins.get(code)) for code in case["materials"]]
        result = resolve(
            good=case["good"],
            inputs=materials,
            country="XX",  # the operation's country; immaterial to the shift
            corpus=corpus,
        )
        ours, detail = _our_verdict(result)
        agrees = None if ours in ("abstained", "no_rule", "ambiguous") else ours == case["cbp"]
        out.append(
            AgreementCase(
                case["ruling"],
                case["year"],
                case["cbp"],
                ours,
                agrees,
                detail,
                cbp_country=case.get("cbp_country"),
                our_country=result.origin,
            )
        )
    return out


def report_agreement(cases: list[AgreementCase]) -> None:
    decided = [c for c in cases if c.agrees is not None]
    agreed = [c for c in decided if c.agrees]
    counts = Counter(c.ours for c in cases)
    baseline = Counter(c.cbp for c in cases).most_common(1)[0][1] / len(cases)

    print(f"curated cases            : {len(cases)}")
    for outcome, n in counts.most_common():
        print(f"   {n:>3}  {outcome}")
    print()
    print(f"coverage (a definite call): {len(decided)}/{len(cases)} = {len(decided)/len(cases):.1%}")
    if decided:
        print(f"agreement with CBP       : {len(agreed)}/{len(decided)} = {len(agreed)/len(decided):.1%}")
    print(f"majority-class baseline  : {baseline:.1%}  (always answering '{Counter(c.cbp for c in cases).most_common(1)[0][0]}')")

    scored = [c for c in cases if c.cbp_country]
    if scored:
        right = [c for c in scored if c.our_country == c.cbp_country]
        print()
        print(f"of those, cases stating the materials' origins and the country")
        print(f"CBP held, so the whole hierarchy can be scored : {len(scored)}")
        print(f"   reached CBP's country                      : {len(right)}/{len(scored)}")
        for c in scored:
            mark = "ok " if c.our_country == c.cbp_country else "NO "
            print(f"   {mark}[{c.ruling} {c.year}] CBP {c.cbp_country}, we {c.our_country}")

    disagreed = [c for c in decided if not c.agrees]
    if disagreed:
        print("\ndisagreements:")
        for c in disagreed:
            print(f"   [{c.ruling} {c.year}] CBP said {c.cbp}, we said {c.ours}")
            print(f"      {c.detail[:150]}")
    abstained = [c for c in cases if c.ours == "abstained"]
    if abstained:
        print("\nabstentions (neither right nor wrong — the resolver declined):")
        for c in abstained:
            print(f"   [{c.ruling} {c.year}] CBP said {c.cbp}; {c.detail[:120]}")
    other = [c for c in cases if c.ours in ("no_rule", "ambiguous")]
    if other:
        print("\nnot answerable from this corpus:")
        for c in other:
            print(f"   [{c.ruling} {c.year}] {c.ours}: {c.detail[:110]}")


if __name__ == "__main__":
    main()
