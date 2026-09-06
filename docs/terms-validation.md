# Validation of the defined-term graph

Generated 2026-09-06 by `python -m originshift.validate_terms --emit`.

The graph says Part 134 defines its central term in a term it does not
carry. If that is true, rulings applying the section have to reach
outside the part to finish the sentence. This counts that.

## 19 CFR 134.1 — the subject

§ 134.1(b) defines country of origin in terms of substantial transformation, which Part 134 never defines.

| | |
|---|---|
| in population | 1092 |
| scored | 1092 |
| excluded, no text | 0 |
| excluded, not retrieved | 0 |
| **reached outside the part** | **629** |
| **share** | **57.6%** |

| authority | rulings |
|---|---|
| Gibson-Thomsen | 343 |
| Uniroyal | 162 |
| Koru | 154 |
| unnamed reported decision | 117 |
| Belcrest | 94 |
| National Hand Tool | 86 |
| Ferrostaal | 32 |
| Energizer | 9 |

## 19 CFR 102.20 — the control

a tariff-shift table whose terms are given by rule; a practitioner applying it has no missing definition to go outside for.

| | |
|---|---|
| in population | 320 |
| scored | 320 |
| excluded, no text | 0 |
| excluded, not retrieved | 0 |
| **reached outside the part** | **93** |
| **share** | **29.1%** |

| authority | rulings |
|---|---|
| unnamed reported decision | 49 |
| Gibson-Thomsen | 22 |
| Uniroyal | 19 |
| National Hand Tool | 17 |
| Belcrest | 14 |
| Energizer | 8 |
| Ferrostaal | 2 |
| Koru | 2 |

## What the comparison says

Subject 57.6% against control 29.1%, a difference of +28.5 percentage points.

Rulings applying § 134.1 reach outside the part more often than rulings applying a section whose terms are given by rule. That is consistent with the graph's claim and is not proof of it: a ruling may cite a case for reasons unrelated to the undefined term.

**Which authority is reached for is the sharper signal.** The rate counts any citation; these are the specific cases, and the substantial-transformation authorities concentrate in the subject population rather than merely appearing more often:

| authority | subject | control | ratio |
|---|---|---|---|
| Gibson-Thomsen | 343 (31.4/100) | 22 (6.9/100) | 4.6x |
| Uniroyal | 162 (14.8/100) | 19 (5.9/100) | 2.5x |
| Koru | 154 (14.1/100) | 2 (0.6/100) | 22.6x |
| unnamed reported decision | 117 (10.7/100) | 49 (15.3/100) | 0.7x |
| Belcrest | 94 (8.6/100) | 14 (4.4/100) | 2.0x |
| National Hand Tool | 86 (7.9/100) | 17 (5.3/100) | 1.5x |
| Ferrostaal | 32 (2.9/100) | 2 (0.6/100) | 4.7x |
| Energizer | 9 (0.8/100) | 8 (2.5/100) | 0.3x |

## What this does not measure

Whether each citation is *for* the undefined term. The count is of
rulings that reach outside the part at all, which is an upper bound on
reaches caused by the missing definition.

The FTC side is not scored here. MUSA enforcement documents are a
different corpus with a different access path, and it has not been
sized — an unsized oracle is what `docs/oracle-sizing.md` exists to
prevent.

