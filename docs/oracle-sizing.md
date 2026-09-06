# Oracle sizing for the defined-term corpus

Generated 2026-09-06 by `python tools/oracle_sizing.py`. Seed `20260906`, one draw of 30 from the 1092 HQ rulings citing 19 CFR 134.1.

Both oracles are scored on the **same** sample, so the comparison is not
confounded by the draw.

## Oracle A — does a ruling state where a term is defined?

This was the first proposal. Probes were fixed before any ruling was read.

| probe | hits |
|---|---|
| `not_defined` | 0/30 |
| `defined_in` | 4/30 |
| `term_means` | 0/30 |
| `for_purposes` | 0/30 |
| **any** | **4/30** |

**Adjudicated by reading every matched span.** Each hit resolves a real
term, and the resolution it states is one the graph must also hold:

| ruling | resolution stated | kind |
|---|---|---|
| `560527` | "good of a NAFTA country" -> 19 CFR 134.1(g) | `in_part` |
| `732734` | "country of origin" -> 19 CFR 134.1(b) | `in_part` |
| `562086` | "usual container" -> 19 CFR 134.22(d)(1) | `in_part` |
| `959526` | "domestic material" -> 19 CFR 102.1(d) | `cross_part` |

So oracle A is usable but thin: it is a **direct** check, because a ruling
saying where a term is defined is exactly a record the graph should carry.

## Oracle B — does a ruling reach outside the part to resolve the term?

The graph marks `substantial transformation` unsigned in Part 134. That
predicts anyone applying the part must reach outside it, and the reach is
countable.

| citation | hits |
|---|---|
| Gibson-Thomsen | 6/30 |
| Uniroyal | 1/30 |
| Belcrest | 2/30 |
| Nat'l Hand Tool | 1/30 |
| Koru | 1/30 |
| Energizer | 0/30 |
| any court cite | 10/30 |
| **reaches outside** | **15/30** |

Seen in `968218`, retrieved 2026-09-06:

> …aterial added in another country results in an article having a different name, character, or use. See United States v. Gibson-Thomsen Co., Inc., 27 C.C.P.A., 267 (CAD 98). Section 134.46, CBP Regulations (19 CFR 134.46), contains more restrictive marking requirements de…

## What this does not establish

One draw of 30 from 1092. Enough to show both oracles carry
signal and to justify building against them. **Not** enough to publish a
rate: the
figure that goes in print comes from the full population once the parser
exists. The FTC side is unsized and may have the same shape problem.

