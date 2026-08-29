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
QUOTED_RULE = re.compile(r"A change to (?:[^.]|\.(?=\d))+?\.(?!\d)", re.I)

#: Where CBP's own prose resumes. A rule never contains these, and a quotation
#: that runs past its closing punctuation picks up codes that are not part of it.
NARRATIVE = re.compile(
    r"\b(since|because|therefore|accordingly|constitutes|and thus|in this instance"
    r"|the only materials|we note|in your|you state|the importer|petitioner"
    r"|is satisfied|is not satisfied|the applicable tariff shift)\b",
    re.I,
)

#: The longest rule in 102.20 runs to about 1,800 characters, so the cap is only
#: a backstop for a quotation that never found its closing punctuation.
MAX_RULE_CHARS = 1900

#: A quote counts as a statement of 102.20 only where CBP attributes it there.
#: Rulings that cite 102.20 routinely also quote USMCA and NAFTA preferential
#: rules, which are worded almost identically and are a different legal test.
ATTRIBUTION = re.compile(r"102\.20")
ATTRIBUTION_WINDOW = 400


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
    if alt.shift is None or alt.target is None:
        return ()
    return (
        tuple(sorted({str(r) for r in alt.target.ranges})),
        tuple(sorted({(s.kind, s.level or "") for s in alt.shift.sources})),
        tuple(sorted({str(r) for r in alt.shift.excluded})),
    )


def quoted_rules(text: str) -> list[str]:
    """Every statement of a 102.20 rule in a ruling, and nothing else.

    Two things have to be got right or the score is measuring the wrong thing:
    the quote must be attributed to 102.20 rather than to a preferential annex,
    and it must stop where the rule stops.
    """
    out: list[str] = []
    for match in QUOTED_RULE.finditer(text):
        window = text[max(0, match.start() - ATTRIBUTION_WINDOW) : match.start()]
        if not ATTRIBUTION.search(window):
            continue
        quote = match.group()
        resumed = NARRATIVE.search(quote)
        if resumed:
            quote = quote[: resumed.start()].rstrip(" ,;")
        if 25 < len(quote) <= MAX_RULE_CHARS:
            out.append(quote.strip())
    return out


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


def check_quote(quote: str, corpus: Corpus) -> tuple[Verdict, str | None, str]:
    """Compare one quoted rule against the corpus, structurally."""
    alt = parse_102.parse_alternative(normalise(quote), scope=[])
    if alt.target is None or not alt.target.ranges or alt.shift is None:
        return "unparsed", None, "the quotation does not parse as a shift rule"

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


def run(corpus: Corpus | None = None, cache_dir: Path | None = None) -> Report:
    """Score the corpus against every cached HQ ruling that quotes 102.20."""
    corpus = corpus or Corpus.load()
    cache_dir = cache_dir or (sources.CACHE / "cross")

    report = Report()
    for path in sorted(cache_dir.glob("*.json")):
        ruling = json.loads(path.read_text(encoding="utf-8"))
        text = plain_text(ruling)
        report.rulings_examined += 1

        quotes = set(quoted_rules(text))
        if not quotes:
            continue
        report.rulings_quoting_a_rule += 1

        year = (ruling.get("rulingDate") or "")[:4]
        for quote in sorted(quotes):
            verdict, rule_id, detail = check_quote(quote, corpus)
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
    print("RULE FIDELITY — does the corpus hold the rule CBP applied?")
    print("=" * 74)

    report = run()
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


def _our_verdict(result) -> tuple[str, str]:
    """Reduce an OriginResult to the question CBP answered: did the shift hold?"""
    if result.status == "ambiguous":
        return "ambiguous", result.reason or ""
    if result.reason == "no_rule_for_this_classification":
        return "no_rule", result.needed or ""
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

    out: list[AgreementCase] = []
    for case in data["cases"]:
        result = resolve(
            good=case["good"],
            inputs=case["materials"],
            country="XX",  # the country is immaterial to whether the shift holds
            corpus=corpus,
        )
        ours, detail = _our_verdict(result)
        agrees = None if ours in ("abstained", "no_rule", "ambiguous") else ours == case["cbp"]
        out.append(
            AgreementCase(case["ruling"], case["year"], case["cbp"], ours, agrees, detail)
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
