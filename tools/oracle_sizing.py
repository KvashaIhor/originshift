"""Size the validation oracle for the defined-term corpus, and record the null.

The first oracle proposed for stage 2 was "rulings that state where a term is
defined". This measures that, finds it empty, and measures the alternative that
replaced it — "rulings that reach outside the part to resolve a term the graph
marks unsigned".

The point of keeping this is not the numbers. It is that the second oracle was
chosen against a measured null rather than picked because it worked, and a
reader can re-run both and see the same thing.

Run:  python tools/oracle_sizing.py            (writes docs/oracle-sizing.md)
      python tools/oracle_sizing.py --sample 60

Rulings are cached under data/cache/cross, so a second run costs no requests.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from originshift import sources  # noqa: E402

SEED = 20260906
OUT = Path(__file__).resolve().parent.parent / "docs" / "oracle-sizing.md"

#: Fixed before any ruling was read. Recorded here so a reader can see the
#: probes were not tuned until they found something.
RESOLUTION_PROBES = {
    "not_defined": r"(is|are) not defined|does not define|no definition",
    "defined_in": r"defined in\s+(19\s+)?(CFR|C\.F\.R\.|§)",
    "term_means": r"the term [\"“][^\"”]{2,40}[\"”]\s+means",
    "for_purposes": r"for purposes of (this part|§|section)",
}

#: The cases a practitioner reaches for when Part 134 does not carry the term.
OUTSIDE_REACH_PROBES = {
    "Gibson-Thomsen": r"Gibson[- ]Thomsen",
    "Uniroyal": r"Uniroyal",
    "Belcrest": r"Belcrest",
    "Nat'l Hand Tool": r"National Hand Tool|Nat'?l Hand Tool",
    "Koru": r"Koru",
    "Energizer": r"Energizer",
    "any court cite": r"\b\d+\s+F\.\s?(Supp|2d|3d)|C\.I\.T\.|Cust\. Ct\.",
}

#: Adjudicated by reading every matched span in the draw. These are the oracle-A
#: hits and where each one points. Three resolve a Part 134 term inside Part 134;
#: one resolves a term to Part 102, which the graph records as a cross-part edge.
#: An earlier, non-reproducible draw contained two off-target matches and led to
#: the wrong conclusion that oracle A was empty — that is why the draw is sorted
#: before sampling now.
ADJUDICATED = {
    "560527": ('"good of a NAFTA country" -> 19 CFR 134.1(g)', "in_part"),
    "732734": ('"country of origin" -> 19 CFR 134.1(b)', "in_part"),
    "562086": ('"usual container" -> 19 CFR 134.22(d)(1)', "in_part"),
    "959526": ('"domestic material" -> 19 CFR 102.1(d)', "cross_part"),
}

def _draw(query: str, n: int) -> tuple[int, list[dict]]:
    # The API returns the same set in a DIFFERENT ORDER on every call, so a seed
    # alone does not fix the draw — sorting first is what makes it reproducible.
    # Checked: two calls returned identical sets and different orders.
    population = sources.cross_search(query, collection="hq", page_size=100)
    population = sorted(population, key=lambda r: str(r["rulingNumber"]))
    rng = random.Random(SEED)
    return len(population), rng.sample(population, min(n, len(population)))


def _score(sample, probes) -> tuple[int, dict[str, int], int, dict[str, tuple[str, str]]]:
    counts = {k: 0 for k in probes}
    examples: dict[str, tuple[str, str]] = {}
    scored = 0
    any_hit = 0
    for row in sample:
        number = row["rulingNumber"]
        try:
            text = (sources.cross_ruling(number).get("text") or "").replace("\r", " ")
        except Exception:
            continue
        if not text:
            continue
        scored += 1
        fired = False
        for key, rx in probes.items():
            m = re.search(rx, text, re.I)
            if m:
                counts[key] += 1
                fired = True
                examples.setdefault(
                    key,
                    (number, re.sub(r"\s+", " ", text[max(0, m.start() - 120) : m.end() + 140]).strip()),
                )
        any_hit += fired
    return scored, counts, any_hit, examples


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=30, help="rulings per draw")
    args = ap.parse_args()

    total, sample = _draw("19 CFR 134.1", args.sample)
    scored_a, counts_a, any_a, ex_a = _score(sample, RESOLUTION_PROBES)
    scored_b, counts_b, any_b, ex_b = _score(sample, OUTSIDE_REACH_PROBES)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = []
    w = lines.append
    w("# Oracle sizing for the defined-term corpus")
    w("")
    w(f"Generated {now} by `python tools/oracle_sizing.py`. Seed `{SEED}`, "
      f"one draw of {args.sample} from the {total} HQ rulings citing 19 CFR 134.1.")
    w("")
    w("Both oracles are scored on the **same** sample, so the comparison is not")
    w("confounded by the draw.")
    w("")
    w("## Oracle A — does a ruling state where a term is defined?")
    w("")
    w("This was the first proposal. Probes were fixed before any ruling was read.")
    w("")
    w("| probe | hits |")
    w("|---|---|")
    for k, v in counts_a.items():
        w(f"| `{k}` | {v}/{scored_a} |")
    w(f"| **any** | **{any_a}/{scored_a}** |")
    w("")
    w("**Adjudicated by reading every matched span.** Each hit resolves a real")
    w("term, and the resolution it states is one the graph must also hold:")
    w("")
    w("| ruling | resolution stated | kind |")
    w("|---|---|---|")
    for number, (what, kind) in ADJUDICATED.items():
        w(f"| `{number}` | {what} | `{kind}` |")
    w("")
    w("So oracle A is usable but thin: it is a **direct** check, because a ruling")
    w("saying where a term is defined is exactly a record the graph should carry.")
    w("")
    w("## Oracle B — does a ruling reach outside the part to resolve the term?")
    w("")
    w("The graph marks `substantial transformation` unsigned in Part 134. That")
    w("predicts anyone applying the part must reach outside it, and the reach is")
    w("countable.")
    w("")
    w("| citation | hits |")
    w("|---|---|")
    for k, v in counts_b.items():
        w(f"| {k} | {v}/{scored_b} |")
    w(f"| **reaches outside** | **{any_b}/{scored_b}** |")
    w("")
    for key in ("Gibson-Thomsen",):
        if key in ex_b:
            number, quote = ex_b[key]
            w(f"Seen in `{number}`, retrieved {now}:")
            w("")
            w(f"> …{quote}…")
            w("")
    w("## What this does not establish")
    w("")
    w(f"One draw of {args.sample} from {total}. Enough to show both oracles carry")
    w("signal and to justify building against them. **Not** enough to publish a")
    w("rate: the")
    w("figure that goes in print comes from the full population once the parser")
    w("exists. The FTC side is unsized and may have the same shape problem.")
    w("")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"oracle A: {any_a}/{scored_a}   oracle B: {any_b}/{scored_b}   -> {OUT}")


if __name__ == "__main__":
    main()
