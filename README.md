# originshift

**Non-preferential rules of origin, as data.** Answers "what country is this good
legally from?" and cites the rule it used.

`0.1.0` · alpha · Python ≥3.11 · Apache-2.0 · corpus `HTSUS-2026`, eCFR `2026-08-26`

**Part 102 only.** For non-textile goods it does not decide Section 301 or 232
origin, and it never decides AD/CVD scope. [Scope, precisely](#scope-precisely).

```
pip install originshift
```

```
originshift resolve --good 6203.42 --inputs 5208.11 --country VN \
    --fibre cotton --component-parts yes --assembled-in VN
#   6203.42  →  RESOLVED   VN   102.21(e)(1)/6201-6208
```

Two corpora, both compiled from the eCFR and pinned to a nomenclature vintage.
**The smaller one has far the wider reach:**

| Corpus | Governs | Rules | You supply | Scored against CBP |
|---|---|---|---|---|
| **102.21** | **Every textile and apparel import, from any country** — 102.21(a) controls their origin *"for purposes of the Customs laws"*, except as to Israel | 101 (+1 overlay) | codes **and production facts** | **13/13** country, 13/13 paragraph |
| **102.20** | Country-of-origin **marking** for goods of Canada and Mexico, under USMCA and NAFTA | 1,032 | codes | **22/22** shift, 8/8 country |

CBP's own ruling database cites 102.21 in 3,310 rulings and 102.20 in 909.

**The two halves ask different things of you.** For 102.20 you give
classifications and get a country back. For 102.21 you also have to say how the
good was made: its fibre, whether it was knit to shape, where it was assembled.
That is what the regulation turns on. All of it sits on a spec sheet, but it has
to reach the tool. Give a garment nothing but codes and you get `unresolved`
back with a list of what it needs.

If you import apparel, 102.21 is the half you want. If you file under USMCA,
102.20 is.

**It never guesses.** Every determination comes back `resolved`, `unresolved`
or `ambiguous`. `unresolved` names the fact the rule needs and stops there.
Where two rules both apply you get both, with their text.

```python
>>> from originshift import resolve
>>> r = resolve(good="2008.11", inputs=["1202.41"], country="CN")
>>> r.status, r.needed
('unresolved',
 'the rule requires: provided that the change is not the result of mere blanching of peanuts')
```

**What Part 102 does not reach.** Per **19 CFR 102.0**, Part 102 is confined to
marking. A textile or apparel good is the exception: 102.21 governs its origin
for purposes of the Customs laws, and the Chapter 99 provisions key off that
determination. For any other good, Section 301 and Section 232 origin turn
on the common-law substantial transformation test. That test is case law. It has
no rule table, and nothing here compiles one. Commerce decides AD/CVD scope.
[Scope, precisely](#scope-precisely) sets out the limits.

## What is here

| Component | State |
|---|---|
| `sources.py` | Fetches primary law, pinned to a dated snapshot |
| `grammar.py` | The type system rules compile into — ranges, shifts, exceptions |
| `parse_102.py` | Compiles 19 CFR 102.20 into that grammar |
| `parse_102_21.py` | Compiles 19 CFR 102.21(e)(1) — textiles and apparel |
| `ingest.py` | Brings in rules from sources that cannot be fetched and parsed |
| `build_corpus.py` | Emits the versioned corpus |
| `resolve.py` | Walks 102.11, applies the corpus, and cites what it used |
| `textile.py` | The 102.21(c) hierarchy, for textile and apparel products |
| `bom.py` | Walks a bill of materials, determining origin at each node |
| `cli.py` | `originshift` — single lookups and batch CSV |
| `validate.py` | Scores the corpus against CBP's own rulings |

## The corpus

```
python -m originshift.build_corpus
```

Writes one file per corpus into `src/originshift/data/corpus/`, each named for
the eCFR issue date it was built from. Pass `--corpus` to build just one.

| File | Rules | Alternatives | Parsed into structure | Decidable on codes alone |
|---|---|---|---|---|
| `102.20-<issue-date>.json` | 1,032 | 1,464 | 1,445 (98.7%) | 1,023 (69.9%) |
| `102.21-<issue-date>.json` | 101 | 176 | 56 (31.8%) | 21 (11.9%) |

Everything the parser could not settle is recorded with the reason it could not,
whether that was a source naming a good instead of a code, a condition on the
good, or a rule that turns on where a process happened.

Every record carries its provenance: the source URL, the eCFR issue date, and
the nomenclature vintage it answers under. A rule can be re-derived after the
source is amended.

**The package follows semver. The corpus carries the vintage.** The corpus file
is named for the issue date it was built from, every record states that date as
`source_issue_date` alongside its `vintage`, and every answer returns the
vintage it was decided under. A corpus can therefore be used without the code
and still say what it answers under, and an answer decided under an older
nomenclature says as much instead of going quietly stale.

```json
{
  "rule_id": "102.20/8708.29",
  "scope": [
    "8708.29"
  ],
  "alternatives": [
    {
      "kind": "tariff_shift",
      "shift": {
        "sources": [
          {
            "kind": "any_other",
            "level": "subheading",
            "ranges": [],
            "outside_that_group": false,
            "text": "any other subheading"
          }
        ],
        "excluded": [
          "8708.95"
        ]
      },
      "target": {
        "ranges": [
          "8708.29"
        ]
      },
      "text": "A change to subheading 8708.29 from any other subheading, except from subheading 8708.95."
    }
  ],
  "vintage": "HTSUS-2026",
  "source_url": "https://www.ecfr.gov/api/versioner/v1/full/2026-08-26/title-19.xml?part=102"
}
```

**Ranges are the primitive.** `5208-5212` is stored as a range, never expanded
into the codes it covers. Expanding destroys the structure that makes the corpus
useful and inflates it for nothing.

## Resolving

```python
>>> from originshift import resolve
>>> r = resolve(good="8708.29", inputs=["7208.10", "8708.99"], country="VN")
>>> r.origin, r.rule_id
('VN', '102.20/8708.29')
>>> r.trace[0].checks[0].detail
'in a different subheading from 8708.29'
```

**Which hierarchy applies is decided first.** 102.11 governs goods *"other than
textile and apparel products covered by § 102.21"*. A covered good takes
102.21(c) instead. Coverage runs wider than chapters 50–63: hats, umbrellas and
car seat belts are all 102.21's. Citing 102.11 for one of them would cite a
provision that excludes it.

### Goods under 102.20 — the 102.11 hierarchy

| Step | Basis | Needs |
|---|---|---|
| 102.11(a)(1) | `wholly_obtained` | `wholly_obtained=True` |
| 102.11(a)(2) | `exclusively_domestic` | every material's `country` |
| 102.11(a)(3) | `tariff_shift` | the classifications |
| 102.13 | `tariff_shift_de_minimis` | material values and `good_value` |
| 102.11(b)(1) | `essential_character` | the materials' countries |
| 102.11(b)(2), (c), (d) | — | commingled stock, sets, minor processing: named without being decided |

### Textile and apparel goods — the 102.21(c) hierarchy

| Step | Basis | Needs |
|---|---|---|
| 102.21(c)(1) | `wholly_obtained` | `wholly_obtained=True` |
| 102.21(c)(2) via (e)(1) | `tariff_shift` / `process` | the classifications, or where a named process happened |
| 102.21(c)(2) via (e)(2) | `process` | the fibre, then where the good was dyed and printed, knit, or assembled |
| 102.13(c) | `tariff_shift_de_minimis` | material **weights** and `good_weight` — 7% by weight |
| 102.21(c)(3)(i) | `knit_to_shape` | `TextileFacts(knit_to_shape_in=…)` |
| 102.21(c)(3)(ii) | `wholly_assembled` | `TextileFacts(wholly_assembled_in=…)`, and the good not one of the headings (c)(3)(ii) excepts |
| 102.21(c)(4) | `most_important_process` | `TextileFacts(most_important_process_in=…)` |
| 102.21(c)(5) | `last_important_process` | `TextileFacts(last_important_process_in=…)` |

Only the first two steps turn on codes. The rest turn on where an operation
happened, which is why textile goods abstain so often, and the abstention names
the step it is waiting on.

**Paragraph (e) has two tables, and the fibre decides which applies.** (e)(2)
reaches headings 6213 and 6214 plus fourteen named subheadings:

```
6117.10   6302.22   6302.29   6302.53   6302.59   6302.93   6302.99
6303.92   6303.99   6304.19   6304.93   6304.99   9404.90.85   9404.90.95
```

It reaches those and nothing else. Fibre then carves it back: a good of cotton,
of wool, or of a blend 16% or more cotton by weight stays with (e)(1) even so.
A silk scarf of 6214 is therefore (e)(2)'s, while a cotton one is (e)(1)'s.
6302.10 and 6304.20 are (e)(1)'s outright. Where the fibre has not been stated,
neither table is picked and the resolver asks.

```python
>>> from originshift.textile import TextileFacts
>>> r = resolve(good="6214.10", inputs=[], country="VN",
...             textile=TextileFacts(excepted_fibre=False,
...                                  dyed_and_printed_in="IT",
...                                  finishing_operations=("bleaching", "napping")))
>>> r.origin, r.rule_id
('IT', '102.21(e)(2)(i)')
```

(e)(2)(i) needs the dyeing and printing accompanied by **two or more** of nine
named finishing operations. One will not carry it. The count is the whole test.

**102.11(b) is mostly decidable.** 102.18(b)(1) confines the essential-character
candidates to materials sitting in a provision from which change is not allowed,
which is the set that failed the shift. **102.18(b)(1)(iii)** then settles it
outright:

> *If there is only one material that is classified in a tariff provision from
> which a change in tariff classification is not allowed … then that material
> **will represent** the single material that imparts the essential character.*

Judgement is only reached with two or more candidates, and even then only when
they come from different countries. In all 19 curated cases where the shift
definitely failed, exactly one material was in a disallowed provision, and the
regulation therefore named the answer in every one. Domestic materials count
here, unlike under (a)(3).

`102.17` is applied where an `operation` is given. Repacking, dismantling, mere
dilution, a change in end-use and a GRI 2(a) collection of parts confer no
origin, however the codes fall.

```python
>>> from originshift.resolve import Material
>>> r = resolve(good="8708.29", inputs=[Material("8708.95", value=3.0)],
...             country="VN", good_value=100.0)
>>> r.basis, r.reason
('tariff_shift_de_minimis', 'disregarded under 102.13 at 3.0% of the value of the good')
```

Materials of unstated origin are treated as foreign. Assuming otherwise would
hand out origin on missing information.

Three outcomes and no others:

| Outcome | Meaning |
|---|---|
| `resolved` | a rule applied; origin and rule ID returned |
| `unresolved` | no rule applied, or the inputs are insufficient — **the missing item is named** |
| `ambiguous` | more than one rule applies; all candidates returned with their rules |

```python
>>> r = resolve(good="2008.11", inputs=["1202.41"], country="CN")
>>> r.status, r.needed
('unresolved',
 'the rule requires: provided that the change is not the result of mere blanching of peanuts')
```

## Command line

```
originshift resolve --good 8708.29 --inputs 7208.10,8708.99 --country VN
originshift resolve --csv entries.csv --out results.csv
originshift bom assembly.json
originshift rule 6203.42 --corpus 102.21
originshift corpora
```

`--csv` takes a file of entries and writes a file of determinations, which is
usually the question: what does this say about last quarter's entries.
`entries.csv` needs a `good` column. Everything else is optional:

| Column | |
|---|---|
| `good` | **required** — HS code of the finished article |
| `country` | where the operation happened |
| `materials` | material HS codes, comma-separated |
| `material_countries` | positional, matching `materials` |
| `material_values`, `good_value` | for the 102.13 de minimis allowance |
| `wholly_obtained`, `is_set` | flags |
| `operation` | a 102.17 operation, e.g. `simple_packing` |
| `corpus` | force `102.20` or `102.21`; otherwise whichever has a rule |
| `good_weight`, `material_weights` | for the 102.13(c) textile allowance, which is by weight |

For textiles and apparel. Each is named for what sits on a spec sheet, leaving
you free to ignore which rule it feeds:

| Column | |
|---|---|
| `fibre` | `cotton`, `wool`, `cotton-blend` or `other` — decides whether 102.21(e)(1) or (e)(2) governs |
| `knit_to_shape` | yes / no |
| `component_parts` | yes / no — two or more |
| `knit_in`, `assembled_in`, `fabric_made_in` | where each operation happened |
| `dyed_printed_in`, `finishing` | for 102.21(e)(2)(i), which needs two or more named finishing operations |
| `most_important_process_in`, `last_important_process_in` | 102.21(c)(4) and (c)(5) |
| `c2_settled` | yes, where you have found that 102.21(c)(2) does not settle the good |

```
originshift resolve --good 6203.42 --inputs 5208.11 --country VN \
    --fibre cotton --component-parts yes --assembled-in VN
#   6203.42  →  RESOLVED   VN   102.21(e)(1)/6201-6208
```

Every output row carries `status`, `origin`, `basis`, `rule_id`, `rule_text`,
`needed`, `vintage` and `source`. A determination in a spreadsheet is therefore
as traceable as one from the API. `source` reads `eCFR`, or names the document an
overlaid rule came from.

Worked files: `examples/entries.csv`, `examples/apparel.csv`,
`examples/assembly.json`.

## Bills of materials

A single finished good is rarely the real question.

```
originshift bom examples/assembly.json
```

```
5/5 nodes settled
8708.29  (door assembly, produced in Mexico) — MX
   rule 102.20/8708.29: A change to subheading 8708.29 from any other subheading, except…
   basis tariff_shift_de_minimis
  8708.99  (bracket subassembly, produced in Mexico) — MX
     rule 102.20/8708.99: A change to subheading 8708.99 from any other subheading, except…
     basis tariff_shift
    7208.10  (hot-rolled steel coil) — KR (given)
  7208.10  (steel panel) — JP (given)
  8708.95  (airbag component) — CN (given)
```

The steel coil is indented under the bracket subassembly because that is where
it sits: the bracket's origin is settled first, and the door assembly's rule is
then applied against the result.

Origin is settled bottom-up, because whether a subassembly is foreign to the
country of final production decides whether the finished good's rule is met.

A component whose own origin could not be settled goes up with **no country**.
The resolver reads that as foreign, which is the conservative default, and the
parent records the component in `blocked_by`. An answer standing on an unknown
is never mistaken for a clean one.

**This produces a determination. It never produces a certificate of origin**,
and it does no preferential or FTA qualification. Both are out of scope by
design.

## What `unresolved` means

**`unresolved` means the rules do not decide the question on what you gave.**
The rule was usually found and is cited; what is missing is a fact, and the
result names it. It is not an error condition.

```python
>>> r = resolve(good="2008.11", inputs=["1202.41"], country="CN")
>>> r.status
'unresolved'
>>> r.rule_id                      # the rule was found, and is cited
'102.20/2008.11'
>>> r.needed
'the rule requires: provided that the change is not the result of mere blanching of peanuts'
```

Supply the missing fact and it resolves. Most of what `unresolved` asks for is
one of a short list:

| `reason` | What to supply |
|---|---|
| `insufficient_information` | the fact named in `needed` — a value, a process, what the good is |
| `shift_not_satisfied` | nothing; the shift genuinely failed. `needed` names the material and the paragraph that applies next |
| `no_input_materials_given` | the materials' HS codes, or `wholly_obtained=True` |
| `no_rule_for_this_classification` | a code the corpus's vintage carries, or the other corpus |
| `non_qualifying_operation` | nothing; 102.17 rules the operation out however the codes fall |

`ambiguous` is rarer and means two rules both apply and the corpus does not rank
them. Both are returned with their text.

**For textiles, `unresolved` without production facts is the normal case, by
design.** Only 11.9% of 102.21 needs nothing but a classification, because
textile origin turns on fabric-making, knitting and assembly. For chapters
50–63 the tool gives you a precise statement of *what you must establish*,
drawn from the rule that applies to your code. The alternative is reading
102.21(e)(1) yourself.

## Validation

```
python -m originshift.validate [--disagreements]
```

Ground truth is CBP's own HQ rulings, which are binding determinations by
the authority whose rules this corpus compiles. 312 HQ rulings cite 102.20; 228
of them quote a rule, giving 242 quotations to score. A ruling citing 102.20
routinely quotes 102.21 as well, and a rule for a good 102.21 governs is scored
against that corpus instead of counted against this one.

Comparison is structural, because CBP quotes the regulation loosely: it
pluralises "heading", writes headings in the HS dotted form (`48.17` for
`4817`), and runs a quotation into its own prose.

| Era of ruling | n | Coverage | Rule fidelity |
|---|---|---|---|
| 2020–2026 | 45 | **97.8%** | **86.4%** |
| 2003–2019 | 28 | 85.7% | 66.7% |
| 1994–2002 | 169 | 82.2% | 67.3% |

**Coverage** is how many quoted rules the corpus can place at all; **fidelity**
is how many it holds as CBP stated them.

Agreement falls away with the age of the ruling, which is why a vintage is
pinned at all. The corpus answers under HTSUS 2026, and HS renumbering moves the
codes out from under older rulings. CBP's 2025 quotation of `9401.90` has no
counterpart once HS 2022 has split it into `9401.91` through `9401.99`.

Two things shape that number. Rulings citing 102.20 routinely also quote **USMCA
and NAFTA preferential rules**, which are worded almost identically and are a
different legal test. They come to 44% of everything the extractor finds, and
are excluded before scoring. A quotation is also cut where the rule ends, since
one that runs on into CBP's prose picks up codes that are not part of it.

The full scorecard — every denominator, the verdict breakdown, and each
disagreement in full — is [docs/validation.md](https://github.com/KvashaIhor/originshift/blob/main/docs/validation.md), written by
the validator so it cannot drift from what the code measures.

## Design commitments

**Some rules cannot be structured.** A few name a good where you would expect a
code, as in *"from feathers or down"*. Others turn on a fact no classification carries.
Either way the alternative is left unstructured, the reason is recorded, and the
resolver abstains and says what it needs. An honest abstention tells you what to
go and find out.

The regulation rewards that caution. One rule reads *"from any product other
than edible meals and flours of Chapter 2"*. Read as a positive source, that
becomes *must come from Chapter 2*, which is the exact inverse.

**Defects in the source are reported, never corrected.** 102.20 contains
transcription errors. The rule keyed `2824.10-2824.90` is written *"A change to
subheading 2824.10 through **2924**.90"*, which spans a hundred headings it was
never meant to reach, and the key `4441-4421` runs backwards. Repairing either
would put words in the regulation's mouth; ignoring them lets one typo answer
for a hundred headings. They ship in the corpus's `anomalies` list with the
verbatim text, and the consumer decides.

**Rules the source does not carry can be fed in, and stay marked.** 102.21(e)(1)
has **no entry for headings 6201 through 6208**, which is most apparel:
overcoats, suits, jackets, trousers, shirts, dresses, blouses. CBP Dec. 22-25
was never incorporated, and the eCFR records why: the revision *"could not be
incorporated due to inaccurate amendatory instruction."* The text exists in the
Federal Register.

```
python -m originshift.ingest extract 87-FR-68356.pdf --origin "87 FR 68356" --name cbp-dec-22-25
#   read the staged rows against the source, correct them, then
python -m originshift.ingest compile cbp-dec-22-25 --reviewed-by "your name"
```

Extraction never writes to a corpus. It writes a staging CSV for a person to
check, every document is hashed, and every rule carries where it came from and
who read it. An answer resting on a hand-fed document can always be told from
one resting on the eCFR:

```python
>>> from originshift import Corpus
>>> c = Corpus.load(which="102.21")
>>> c.provenance_of("102.21(e)(1)/6201-6208")["origin"]
'87 FR 68356 (CBP Dec. 22-25, 15 Nov 2022)'
>>> c.provenance_of("102.21(e)(1)/5007") is None   # straight from the eCFR
True
```

**Nothing is stored between calls.** Resolution runs in your process, holds no
state, and makes no network request. The corpus is read from disk and ships with
the package. Fetching sources and rebuilding the corpus are separate commands you
run deliberately.

**Non-preferential only.** Preferential (trade-agreement) origin is out of
scope, deliberately: `US9177286B2` runs to 2034 over bill-of-materials origin
traversal with certificate output, and the EU already ships ROSA for free.
Compiling rules and resolving a good against one is not the claimed invention.

## Sources

| Source | Licence |
|---|---|
| 19 CFR 102.20 and 102.21, via the [eCFR API](https://www.ecfr.gov/api/versioner/v1/) | US Government work, public domain (17 U.S.C. §105) |
| CBP CROSS rulings, for validation | US Government work, public domain |
| Federal Register, for text the CFR did not incorporate | US Government work, public domain |

## Scope, precisely

Stated in full, with the use statement, in [docs/scope.md](https://github.com/KvashaIhor/originshift/blob/main/docs/scope.md).

**19 CFR 102.0** confines Part 102 to USMCA and NAFTA country-of-origin
**marking**, plus the "new or different article of commerce" test of the Morocco
and Bahrain FTAs.

**19 CFR 102.21(a)** is the wider grant: it controls the origin of textile and
apparel products *"for purposes of the Customs laws"*, from any country, except
as to Israel. Not marking-only, not USMCA-only.

### What Part 102 does not decide

| Question | Decided by | In this tool? |
|---|---|---|
| Marking origin, USMCA/NAFTA goods | 19 CFR 102.20 | yes |
| Textile and apparel origin, any country | 19 CFR 102.21 | yes |
| **Section 301 origin, textile and apparel goods** | 19 CFR 102.21 | **yes** |
| **Section 301 / Section 232 origin, all other goods** | common-law substantial transformation | **no** |
| **AD/CVD scope** | Commerce scope analysis | **no** |
| Marking origin, other non-USMCA goods | common-law substantial transformation | **no** |
| **Preferential / FTA qualification** | the agreement's own rules of origin | **no, deliberately** |

Substantial transformation is case law. It has no rule table, and nothing this
project could compile. For a good outside 102.21, a tool claiming to answer
Section 301 origin out of Part 102 would be wrong, and a licensed broker would
know it.

For a textile or apparel good the answer inverts, on CBP's own authority.
19 U.S.C. 3592 is Congress's expression of substantial transformation for these
goods, and 19 CFR 102.21 implements it. In HQ H323925 (21 November 2022) CBP
held pillows subject to Section 301 "because the pillows at issue are products
of China, as determined by the rules of origin for textiles and apparel
products set forth in § 102.21", and refused the importer's substantial
transformation argument, holding that the authorities it relied on either
concerned goods that were not textile or apparel products or predated 102.21's
effective date. The origin this tool returns for a textile or apparel good is
the origin the Chapter 99 provisions key off.

Origin is one input. Whether a good is a textile or apparel product under
102.21(b)(5), which Chapter 99 provision reaches it, whether an exclusion
applies, and at what rate are all outside this tool.

Textile origin turns on facts a classification does not carry. Whether the good
is of staple fibers or of filaments. Where the fabric-making process happened.
Whether it was knit to shape.

| Corpus | Parsed into structure | Decidable on codes alone |
|---|---|---|
| 102.20 | 1,445 / 1,464 = 98.7% | 1,023 / 1,464 = 69.9% |
| 102.21 | 56 / 176 = 31.8% | 21 / 176 = 11.9% |

Read the second column as a property of the rule table. It describes the
regulation and never the tool, counting rules that need nothing beyond a
classification, and for textiles almost none do, because 102.21 is written
around processes. It says nothing about how often you get an answer. Supply
what the rules ask for and the curated cases resolve 13 of 13.

## Development

```
pip install -e ".[dev,ingest]"
pytest                                 # passes on a fresh clone
python -m originshift.validate --fetch # download the CROSS rulings (~5 min)
pytest                                 # now including the validation measures
python -m originshift.build_corpus     # rebuild both corpora from the eCFR
python -m originshift.validate         # score them against CBP's rulings
```

The 789 CROSS rulings the validation measures are scored over are **not
committed**, being 12 MB the package never reads. Until they are fetched, those
tests skip and say so. The pinned regulation snapshot and the two ruling indices
are committed, which is enough for everything else to run on a clone.

Built corpora, reviewed overlays and the curated validation cases live in
`src/originshift/data/` and ship with the package, so an install needs no
checkout. Rebuilding from a newer issue of the regulation writes to your cache
directory instead of into the installed package, and a corpus found there is
preferred over the one that shipped. Anything written at runtime, meaning
fetched sources and ingest staging, goes to the repository's `data/` in a
checkout and to your cache directory (`XDG_CACHE_HOME`, else
`~/.cache/originshift`) from an install, and never inside the installed package.
Point `ORIGINSHIFT_OVERLAYS` at a directory to load your own overlays alongside
the shipped ones.
