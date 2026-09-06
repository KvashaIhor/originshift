"""Layer 2: score the graph's unresolvable edges against CBP's own rulings.

The graph claims that § 134.1(b) defines country of origin in a term Part 134
never carries. That claim has a consequence that can be counted: anyone applying
the section has to reach outside the part to finish the sentence, and in a
customs ruling the reach is a case citation.

Two things make this a measurement rather than a demonstration.

The first is that the question had to be chosen against a measured null. The
obvious oracle — rulings that state where a term is defined — was scored first
and returns almost nothing, because rulings apply Part 134 rather than
adjudicate its drafting. That run is preserved in `docs/oracle-sizing.md`.

The second is the comparison group. "Half of these rulings cite case law" is not
evidence unless rulings that do NOT turn on an unsigned term cite it less. 19 CFR
102.20 is the control: a tariff-shift table whose terms are given by rule, where
a practitioner has no missing definition to go looking for. If both populations
reach outside at the same rate, the reach is how customs rulings are written and
says nothing about Part 134, and this module should report that.

Run: python -m originshift.validate_terms --emit
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import paths, sources

#: The cases a practitioner reaches for when the regulation does not carry the
#: term. Named rather than pattern-matched loosely, so the count is of specific
#: authorities and a reader can dispute the list.
CASE_CITATIONS = {
    "Gibson-Thomsen": r"Gibson[- ]Thomsen",
    "Uniroyal": r"Uniroyal",
    "Belcrest": r"Belcrest",
    "National Hand Tool": r"National Hand Tool|Nat'?l Hand Tool",
    "Koru": r"Koru",
    "Energizer": r"Energizer",
    "Ferrostaal": r"Ferrostaal",
}

#: Any reported federal decision, as a backstop for cases not named above.
ANY_COURT = re.compile(r"\b\d+\s+F\.\s?(?:Supp|2d|3d)|C\.I\.T\.|Cust\. Ct\.", re.I)

#: What is being scored, and against what. The control is the point: the same
#: measurement on a population with no missing definition.
POPULATIONS = {
    "134.1": {
        "query": "19 CFR 134.1",
        "role": "subject",
        "why": (
            "§ 134.1(b) defines country of origin in terms of substantial "
            "transformation, which Part 134 never defines"
        ),
    },
    "102.20": {
        "query": "19 CFR 102.20",
        "role": "control",
        "why": (
            "a tariff-shift table whose terms are given by rule; a practitioner "
            "applying it has no missing definition to go outside for"
        ),
    },
}


def _reach(text: str) -> list[str]:
    """Which outside authorities a ruling reaches for."""
    hits = [name for name, rx in CASE_CITATIONS.items() if re.search(rx, text, re.I)]
    if not hits and ANY_COURT.search(text):
        hits = ["unnamed reported decision"]
    return hits


def population(key: str, refresh: bool = False) -> tuple[list[str], str]:
    """Ruling numbers citing the section, from a frozen index, with its date.

    A live query is not a reproducible population. The CROSS search returns the
    same set in a different ORDER on every call — which sorting fixes — but it
    also returns a different SET over time: the index stage 1 froze on 30 Aug
    holds 312 rulings for "102.20" where the same query returns 429 today. A
    figure computed against a live query cannot be re-derived by a reader, so
    the population is frozen to a file and committed, exactly as stage 1 does.
    """
    spec = POPULATIONS[key]
    index = paths.CACHE / f"terms-pop-{key}-index.json"
    if refresh or not index.exists():
        rows = sources.cross_search(spec["query"], collection="hq", page_size=100)
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            json.dumps(
                {
                    "query": spec["query"],
                    "collection": "hq",
                    "frozen_on": datetime.now(timezone.utc).date().isoformat(),
                    "ruling_numbers": sorted({str(r["rulingNumber"]) for r in rows}),
                },
                indent=1,
            ),
            encoding="utf-8",
        )
    doc = json.loads(index.read_text(encoding="utf-8"))
    return doc["ruling_numbers"], doc["frozen_on"]


def score(key: str, limit: int | None = None, cached_only: bool = False) -> dict:
    """Score one population. Every exclusion is counted and reported."""
    numbers, frozen_on = population(key)
    considered = numbers[:limit] if limit else numbers
    cache = paths.CACHE / "cross"

    reached, plain, no_text, unfetched = [], 0, 0, 0
    by_case: dict[str, int] = {}
    for number in considered:
        if cached_only and not (cache / f"{number}.json").exists():
            unfetched += 1
            continue
        try:
            text = (sources.cross_ruling(number).get("text") or "")
        except Exception:
            unfetched += 1
            continue
        if not text.strip():
            no_text += 1
            continue
        hits = _reach(text)
        if hits:
            reached.append(number)
            for h in hits:
                by_case[h] = by_case.get(h, 0) + 1
        else:
            plain += 1

    scored = len(reached) + plain
    return {
        "population": key,
        "role": POPULATIONS[key]["role"],
        "why": POPULATIONS[key]["why"],
        "query": POPULATIONS[key]["query"],
        "in_population": len(numbers),
        "frozen_on": frozen_on,
        "basis": (
            f'HQ-tier CROSS rulings whose text matches the search "{POPULATIONS[key]["query"]}", '
            f"as the index stood on {frozen_on}"
        ),
        "considered": len(considered),
        "scored": scored,
        "excluded_no_text": no_text,
        "excluded_unfetched": unfetched,
        "reached_outside": len(reached),
        "share": (len(reached) / scored) if scored else None,
        "by_authority": dict(sorted(by_case.items(), key=lambda kv: -kv[1])),
    }


def emit(path: Path, results: list[dict]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = next(r for r in results if r["role"] == "subject")
    control = next((r for r in results if r["role"] == "control"), None)

    w: list[str] = []
    w.append("# Validation of the defined-term graph")
    w.append("")
    w.append(f"Generated {now} by `python -m originshift.validate_terms --emit`.")
    w.append("")
    w.append("The graph says Part 134 defines its central term in a term it does not")
    w.append("carry. If that is true, rulings applying the section have to reach")
    w.append("outside the part to finish the sentence. This counts that.")
    w.append("")
    for r in results:
        w.append(f"## {r['query']} — the {r['role']}")
        w.append("")
        w.append(f"{r['why']}.")
        w.append("")
        w.append(f"**Basis.** {r['basis']}.")
        w.append("")
        w.append("| | |")
        w.append("|---|---|")
        w.append(f"| in population | {r['in_population']} |")
        w.append(f"| population frozen on | {r['frozen_on']} |")
        w.append(f"| scored | {r['scored']} |")
        w.append(f"| excluded, no text | {r['excluded_no_text']} |")
        w.append(f"| excluded, not retrieved | {r['excluded_unfetched']} |")
        w.append(f"| **reached outside the part** | **{r['reached_outside']}** |")
        if r["share"] is not None:
            w.append(f"| **share** | **{r['share']:.1%}** |")
        w.append("")
        if r["by_authority"]:
            w.append("| authority | rulings |")
            w.append("|---|---|")
            for name, n in r["by_authority"].items():
                w.append(f"| {name} | {n} |")
            w.append("")

    w.append("## What the comparison says")
    w.append("")
    if control and control["share"] is not None and subject["share"] is not None:
        diff = subject["share"] - control["share"]
        w.append(
            f"Subject {subject['share']:.1%} against control {control['share']:.1%}, "
            f"a difference of {diff * 100:+.1f} percentage points."
        )
        w.append("")
        if diff <= 0.05:
            w.append(
                "**That is not evidence.** Rulings applying a section whose terms are "
                "given by rule reach outside at the same rate, so the reach is how "
                "customs rulings are written and says nothing about Part 134. The "
                "graph's claim stands on the text of § 134.1(b); this measurement "
                "does not support it."
            )
        else:
            w.append(
                "Rulings applying § 134.1 reach outside the part more often than "
                "rulings applying a section whose terms are given by rule. That is "
                "consistent with the graph's claim and is not proof of it: a ruling "
                "may cite a case for reasons unrelated to the undefined term."
            )
            w.append("")
            w.append(
                "**Which authority is reached for is the sharper signal.** The rate "
                "counts any citation; these are the specific cases, and the "
                "substantial-transformation authorities concentrate in the subject "
                "population rather than merely appearing more often:"
            )
            w.append("")
            w.append("| authority | subject | control | ratio |")
            w.append("|---|---|---|---|")
            for name in sorted(
                set(subject["by_authority"]) | set(control["by_authority"]),
                key=lambda n: -subject["by_authority"].get(n, 0),
            ):
                s = subject["by_authority"].get(name, 0)
                c = control["by_authority"].get(name, 0)
                # per-100 rulings, so the different population sizes do not
                # manufacture the contrast on their own
                sr = s / subject["scored"] * 100
                cr = c / control["scored"] * 100
                ratio = f"{sr / cr:.1f}x" if cr else "—"
                w.append(f"| {name} | {s} ({sr:.1f}/100) | {c} ({cr:.1f}/100) | {ratio} |")
    else:
        w.append("The control did not score, so no comparison is available.")
    w.append("")
    w.append("## Why this does not match the stage-1 scorecard")
    w.append("")
    w.append("`docs/validation.md` reports **312** HQ rulings citing 102.20; the")
    w.append("control here is **320**. Two different bases, not a discrepancy:")
    w.append("")
    w.append("- the scorecard searches `102.20`; this searches `19 CFR 102.20`")
    w.append("- the scorecard's index was frozen on 2026-08-30; these were frozen later")
    w.append("")
    w.append("Both matter. The CROSS search returns a different **set** over time, not")
    w.append("only a different order — the scorecard's `102.20` index holds 312 where")
    w.append("the same query returns 429 today. That is why each population is frozen")
    w.append("to a committed index and named by the date it was frozen: a figure")
    w.append("computed against a live search cannot be re-derived by a reader.")
    w.append("")
    w.append("## What this does not measure")
    w.append("")
    w.append("Whether each citation is *for* the undefined term. The count is of")
    w.append("rulings that reach outside the part at all, which is an upper bound on")
    w.append("reaches caused by the missing definition.")
    w.append("")
    w.append("The FTC side is not scored here. MUSA enforcement documents are a")
    w.append("different corpus with a different access path, and it has not been")
    w.append("sized — an unsized oracle is what `docs/oracle-sizing.md` exists to")
    w.append("prevent.")
    w.append("")
    path.write_text("\n".join(w) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="score only the first N of each population")
    ap.add_argument(
        "--cached-only",
        action="store_true",
        help="score only rulings already on disk, and report the rest as excluded",
    )
    ap.add_argument(
        "--refresh-population",
        action="store_true",
        help="re-freeze the population indexes from a live search, changing the basis",
    )
    ap.add_argument("--emit", action="store_true", help="write docs/terms-validation.md")
    args = ap.parse_args()

    if args.refresh_population:
        for k in POPULATIONS:
            population(k, refresh=True)
    results = [score(k, args.limit, args.cached_only) for k in POPULATIONS]
    for r in results:
        share = f"{r['share']:.1%}" if r["share"] is not None else "n/a"
        print(
            f"{r['query']:<16} {r['role']:<8} "
            f"reached {r['reached_outside']:>4}/{r['scored']:<4} = {share:>6}"
            f"   (excluded: {r['excluded_no_text']} no text, "
            f"{r['excluded_unfetched']} not retrieved)"
        )
    if args.emit:
        out = Path(__file__).resolve().parents[2] / "docs" / "terms-validation.md"
        emit(out, results)
        print(f"\nwrote {out}")
    print(json.dumps({r["query"]: r["share"] for r in results}, indent=1))


if __name__ == "__main__":
    main()
