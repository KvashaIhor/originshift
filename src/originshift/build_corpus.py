"""Build the versioned rule corpus.

Run as: python -m originshift.build_corpus [--issue-date YYYY-MM-DD]

The corpus is the artifact other people can depend on without depending on this
code, so it carries its own provenance: which document it came from, which issue
of that document, and which nomenclature vintage it answers under (spec 7).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from . import parse_102, parse_102_21, sources
from .grammar import Rule, digits

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "corpus"

#: 102.20 is written against the HTSUS, which tracks an HS edition. Stated
#: explicitly so a consumer can tell whether the corpus matches their codes.
NOMENCLATURE = {"hs_edition": "HS 2022", "htsus_year": 2026}


#: A target reaching this many headings further than its own HTSUS key is a
#: transcription defect in the regulation rather than a rule of that breadth.
SPAN_TOLERANCE = 20


def _headings(rng) -> int:
    return int(digits(rng.end)[:4]) - int(digits(rng.start)[:4])


def anomalies(rules: list[Rule]) -> list[dict]:
    """Defects in the source text, reported rather than corrected.

    19 CFR 102.20 contains transcription errors. The rule keyed 2824.10-2824.90
    is written "A change to subheading 2824.10 through 2924.90", spanning a
    hundred headings it was never meant to reach; the key 4441-4421 runs
    backwards. Silently repairing either would put words in the regulation's
    mouth, and ignoring them lets one typo answer for a hundred headings, so
    they travel with the corpus and a consumer decides.
    """
    found: list[dict] = []
    for rule in rules:
        for scope in rule.scope:
            if _headings(scope) < 0:
                found.append(
                    {
                        "rule_id": rule.rule_id,
                        "kind": "reversed_htsus_key",
                        "detail": f"the key {rule.htsus} ends before it begins",
                        "text": rule.text[:200],
                    }
                )
        if not rule.scope:
            continue
        widest = max(_headings(s) for s in rule.scope)
        for alt in rule.alternatives:
            if not alt.target:
                continue
            for target in alt.target.ranges:
                if _headings(target) > widest + SPAN_TOLERANCE:
                    found.append(
                        {
                            "rule_id": rule.rule_id,
                            "kind": "target_far_wider_than_key",
                            "detail": (
                                f"target {target} spans {_headings(target)} headings "
                                f"while the key {rule.htsus} spans {widest}"
                            ),
                            "text": alt.text[:200],
                        }
                    )
    return found


#: Headings 102.21(e)(1) does not reach in the eCFR text. CBP Dec. 22-25 was
#: never incorporated, so the rule for most apparel is simply absent.
UNINCORPORATED = {
    "102.21(e)(1)": [
        {
            "kind": "missing_from_source",
            "detail": (
                "no rule for headings 6201 through 6208 — overcoats, suits, "
                "jackets, trousers, shirts, dresses and blouses, the bulk of "
                "apparel. CBP Dec. 22-25, 87 FR 68356 (15 Nov 2022) amended the "
                "entry, but the eCFR records that the revision 'could not be "
                "incorporated due to inaccurate amendatory instruction'"
            ),
            "remedy": (
                "the amended text is in the Federal Register at 87 FR 68356 and "
                "can be brought in through originshift.ingest"
            ),
        }
    ]
}

CORPORA = {
    "102.20": {
        "parser": parse_102,
        "authority": "19 CFR 102.20",
        "title": "Specific rules by tariff classification (non-preferential origin)",
        "scope": (
            "Country-of-origin marking under USMCA and NAFTA, and the 'new or "
            "different article of commerce' test of the Morocco and Bahrain FTAs "
            "(19 CFR 102.0). Not a general origin test for US imports."
        ),
    },
    "102.21": {
        "parser": parse_102_21,
        "authority": "19 CFR 102.21(e)(1)",
        "title": "Textile and apparel products, specific rules by tariff classification",
        "scope": (
            "Controls the country of origin of imported textile and apparel "
            "products for purposes of the Customs laws generally, from any "
            "country, except as to Israel (19 CFR 102.21(a))."
        ),
    },
}


def build(which: str = "102.20", issue_date: str | None = None) -> dict:
    spec = CORPORA[which]
    snap = sources.cfr_part(19, 102, issue_date)
    vintage = f"HTSUS-{NOMENCLATURE['htsus_year']}"
    rules = spec["parser"].parse(snap.text, vintage=vintage, source_url=snap.url)

    alts = [a for r in rules for a in r.alternatives]
    structured = sum(a.structured for a in alts)
    return {
        "corpus": f"19-CFR-{which}",
        "regime": "US",
        "title": spec["title"],
        "authority": spec["authority"],
        "applies_to": spec["scope"],
        "licence": "US Government work, public domain (17 U.S.C. 105)",
        "nomenclature": NOMENCLATURE,
        "vintage": vintage,
        "source_url": snap.url,
        "source_issue_date": snap.issue_date,
        "built_on": date.today().isoformat(),
        "counts": {
            "rules": len(rules),
            "alternatives": len(alts),
            "fully_structured": structured,
            "needs_judgement": len(alts) - structured,
            # Structured but still not answerable on codes alone: a same-position
            # source, a proviso, or an exception written as a description.
            "decidable_from_codes": sum(
                1 for a in alts if a.shift and a.shift.fully_decidable
            ),
            "by_reason": dict(
                Counter(a.unparsed_reason for a in alts if a.unparsed_reason)
            ),
        },
        "anomalies": anomalies(rules) + UNINCORPORATED.get(spec["authority"].replace("19 CFR ", ""), []),
        "rules": [r.to_dict() for r in rules],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--issue-date", help="eCFR issue date; defaults to current")
    ap.add_argument(
        "--corpus", choices=sorted(CORPORA), default=None, help="default: both"
    )
    args = ap.parse_args()

    for which in [args.corpus] if args.corpus else sorted(CORPORA):
        _build_one(which, args.issue_date)


def _build_one(which: str, issue_date: str | None) -> None:
    corpus = build(which, issue_date)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{which}-{corpus['source_issue_date']}.json"
    path.write_text(json.dumps(corpus, indent=1, ensure_ascii=False), encoding="utf-8")

    c = corpus["counts"]
    pct = c["fully_structured"] / c["alternatives"]
    print(f"wrote {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f} KB)")
    print(f"  source     : {corpus['source_url']}")
    print(f"  issue date : {corpus['source_issue_date']}   vintage: {corpus['vintage']}")
    print(f"  rules      : {c['rules']}")
    print(f"  alternatives: {c['alternatives']}  structured {c['fully_structured']} ({pct:.1%})")
    for reason, n in sorted(c["by_reason"].items(), key=lambda kv: -kv[1]):
        print(f"     {n:>3}  {reason}")
    if corpus["anomalies"]:
        print(f"\n  defects in the source text, reported not corrected:")
        for a in corpus["anomalies"]:
            print(f"     {a.get('rule_id', a['kind'])}: {a['detail'][:150]}")


if __name__ == "__main__":
    main()
