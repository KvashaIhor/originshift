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

from . import parse_102, sources

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "corpus"

#: 102.20 is written against the HTSUS, which tracks an HS edition. Stated
#: explicitly so a consumer can tell whether the corpus matches their codes.
NOMENCLATURE = {"hs_edition": "HS 2022", "htsus_year": 2026}


def build(issue_date: str | None = None) -> dict:
    snap = sources.cfr_part(19, 102, issue_date)
    vintage = f"HTSUS-{NOMENCLATURE['htsus_year']}"
    rules = parse_102.parse(snap.text, vintage=vintage, source_url=snap.url)

    alts = [a for r in rules for a in r.alternatives]
    structured = sum(a.structured for a in alts)
    return {
        "corpus": "19-CFR-102.20",
        "regime": "US",
        "title": "Specific rules by tariff classification (non-preferential origin)",
        "authority": "19 CFR 102.20",
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
            "by_reason": dict(
                Counter(a.unparsed_reason for a in alts if a.unparsed_reason)
            ),
        },
        "rules": [r.to_dict() for r in rules],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--issue-date", help="eCFR issue date; defaults to current")
    args = ap.parse_args()

    corpus = build(args.issue_date)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"102.20-{corpus['source_issue_date']}.json"
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


if __name__ == "__main__":
    main()
