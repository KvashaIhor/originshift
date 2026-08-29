# originshift

**Non-preferential rules of origin, as data.** Answers "what country is this good
legally from?" and cites the rule it used.

Two corpora, both compiled from the eCFR and pinned to a nomenclature vintage.
**The smaller one has far the wider reach:**

| Corpus | Governs | Rules | Answerable from codes alone |
|---|---|---|---|
| **102.21** | **Every textile and apparel import, from any country** — 102.21(a) controls their origin *"for purposes of the Customs laws"*, except as to Israel | 101 (+1 overlay) | 31.8% |
| **102.20** | Country-of-origin **marking** for goods of Canada and Mexico, under USMCA and NAFTA | 1,032 | 99.0% |

If you import apparel, **102.21 is why this exists** — a sector where origin
fraud, transshipment and forced-labour enforcement are all live. If you file
under USMCA, 102.20 is your half.

**Before adopting, read what Part 102 does not do.** Per **19 CFR 102.0** it does
**not** decide Section 301 or Section 232 origin, and it does not decide AD/CVD
scope. Those turn on the uncodified common-law **substantial transformation**
test, which this does not implement and cannot, since it is case law rather than
a rule table. [Scope, precisely](#scope-precisely) sets out the limits.

See [originshift.md](originshift.md) for the original plan, amended where its
reasoning turned out to be wrong.

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
| `bom.py` | Walks a bill of materials, determining origin at each node |
| `cli.py` | `originshift` — single lookups and batch CSV |
| `validate.py` | Scores the corpus against CBP's own rulings |

## The corpus

```
python -m originshift.build_corpus
```

Writes one file per corpus, named for its eCFR issue date — pass `--corpus` to
build just one:

| File | Rules | Alternatives | Answerable from codes alone |
|---|---|---|---|
| `data/corpus/102.20-<issue-date>.json` | 1,032 | 1,455 | 1,441 (99.0%) |
| `data/corpus/102.21-<issue-date>.json` | 101 | 176 | 56 (31.8%) |

Everything else is recorded with a reason rather than guessed at: a source
naming a good instead of a code, a condition on the good, a rule that turns on
where a process happened.

Every record carries its provenance — source URL, eCFR issue date, and the
nomenclature vintage it answers under — so it can be re-derived after the source
is amended.

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

102.20 is one step of a hierarchy, and the resolver walks it in order:

| Step | Basis | Needs |
|---|---|---|
| 102.11(a)(1) | `wholly_obtained` | `wholly_obtained=True` |
| 102.11(a)(2) | `exclusively_domestic` | every material's `country` |
| 102.11(a)(3) | `tariff_shift` | the classifications |
| 102.13 | `tariff_shift_de_minimis` | material values and `good_value` |
| 102.11(b)(1) | `essential_character` | the materials' countries |
| 102.11(b)(2), (c), (d) | — | commingled stock, sets, minor processing: named, not decided |

**102.11(b) is more decidable than it looks.** Essential character sounds like a
judgement, but 102.18(b)(1) confines the candidates to materials sitting in a
provision from which change is not allowed — exactly the set that failed the
shift — and **102.18(b)(1)(iii)** then settles it outright:

> *If there is only one material that is classified in a tariff provision from
> which a change in tariff classification is not allowed … then that material
> **will represent** the single material that imparts the essential character.*

So judgement is only reached with two or more candidates, and even then not if
they share a country. In all 19 curated cases where the shift definitely failed,
exactly one material was in a disallowed provision — so the regulation named the
answer in every one. Domestic materials count here, unlike under (a)(3).

`102.17` is applied where an `operation` is given: repacking, dismantling, mere
dilution, a change in end-use, or a GRI 2(a) collection of parts is not
origin-conferring however the codes fall.

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
pip install originshift
```

```
originshift resolve --good 8708.29 --inputs 7208.10,8708.99 --country VN
originshift resolve --csv entries.csv --out results.csv
originshift bom assembly.json
originshift rule 6203.42 --corpus 102.21
originshift corpora
```

**The batch path is the one that matters.** The question is usually "what does
this say about last quarter's entries", not "what about this one good".
`entries.csv` needs a `good` column; everything else is optional:

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

Every output row carries `status`, `origin`, `basis`, `rule_id`, `rule_text`,
`needed`, `vintage` and `source` — so a determination in a spreadsheet is as
traceable as one from the API. `source` reads `eCFR`, or names the document an
overlaid rule came from.

There is a worked `examples/entries.csv` and `examples/assembly.json`.

## Bills of materials

A single finished good is rarely the real question.

```
originshift bom examples/assembly.json
```

```
8708.29  (door assembly, produced in Mexico) — MX
   rule 102.20/8708.29: A change to subheading 8708.29 from any other subheading, except…
   basis tariff_shift_de_minimis
  8708.99  (bracket subassembly, produced in Mexico) — MX
     rule 102.20/8708.99: A change to subheading 8708.99 from any other subheading, except…
  7208.10  (hot-rolled steel coil) — KR (given)
  7208.10  (steel panel) — JP (given)
  8708.95  (airbag component) — CN (given)
```

Origin is settled bottom-up, because whether a subassembly is foreign to the
country of final production decides whether the finished good's rule is met. A
component whose own origin could not be settled goes up with **no country** —
which the resolver reads as foreign, the conservative default — and the parent
records it in `blocked_by`, so an answer standing on an unknown is never
mistaken for a clean one.

**This produces a determination, not a certificate of origin**, and does no
preferential or FTA qualification. Both are deliberately out of scope — see
[the patent note](originshift.md). Nothing is stored between calls.

## What `unresolved` means

**It is not an error, and it is not a failure to find a rule.** It means the
rules genuinely do not decide the question on what you supplied — and the result
names what is missing.

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

**For textiles, `unresolved` is the normal case, by design.** Only 31.8% of
102.21 is answerable from classifications, because textile origin turns on
fabric-making, knitting and assembly. So for chapters 50–63 this is less an
oracle than a precise statement of *what you must establish*, drawn from the
rule that applies to your code. That is worth having: the alternative is reading
102.21(e)(1) yourself.

## Validation

```
python -m originshift.validate [--disagreements]
```

Ground truth is **CBP's own HQ rulings** — binding determinations by the
authority whose rules this corpus compiles. 312 HQ rulings cite 102.20; 228 of
them quote a rule, giving 252 quotations to score. Comparison is structural, not
textual: CBP pluralises "heading", writes headings in HS dotted form (`48.17`
for `4817`), and runs quotations into its own prose.

| Era of ruling | n | Coverage | Rule fidelity |
|---|---|---|---|
| 2020–2026 | 45 | **97.8%** | **77.3%** |
| 2003–2019 | 28 | 85.7% | 59.3% |
| 1994–2002 | 179 | 77.7% | 50.3% |

**Coverage** is how many quoted rules the corpus can place at all; **fidelity**
is how many it holds as CBP stated them.

Agreement falling away with age is the versioning argument (§7), not a defect.
The corpus answers under HTSUS 2026, and HS renumbering moves the codes out from
under older rulings: CBP's 2025 quotation of `9401.90` has no counterpart because
HS 2022 split it into `9401.91` through `9401.99`.

Two things had to be got right before the numbers meant anything, and both are
pinned by tests. Rulings that cite 102.20 routinely also quote **USMCA and NAFTA
preferential rules**, worded almost identically — 30% of quotations, scored
against the wrong legal test until they were excluded. And a quotation that runs
past its closing punctuation absorbs codes from CBP's following prose.

## Design commitments

**It never guesses.** Where a rule names a good rather than a code — *"from
mustard flour or meal"*, *"from feathers or down"* — the alternative is marked
`descriptive_source` and left unstructured. An honest abstention tells the user
what to go and find out; a confident wrong answer does not.

This is load-bearing. One rule reads *"from any product other than edible meals
and flours of Chapter 2"*. Read carelessly, that becomes *must come from Chapter
2* — the exact inverse. The parser abstains instead, and a test pins it.

**Defects in the source are reported, not corrected.** 102.20 contains
transcription errors — the rule keyed `2824.10-2824.90` is written *"A change to
subheading 2824.10 through **2924**.90"*, spanning a hundred headings it was
never meant to reach, and the key `4441-4421` runs backwards. Repairing either
would put words in the regulation's mouth; ignoring them lets one typo answer
for a hundred headings. They ship in the corpus's `anomalies` list with the
verbatim text, and the consumer decides.

**Rules the source does not carry can be fed in, and stay marked.** 102.21(e)(1)
has **no entry for headings 6201 through 6208** — overcoats, suits, jackets,
trousers, shirts, dresses, blouses, the bulk of apparel — because CBP Dec. 22-25
was never incorporated: the eCFR records that the revision *"could not be
incorporated due to inaccurate amendatory instruction."* The text exists, in the
Federal Register.

```
python -m originshift.ingest extract 87-FR-68356.pdf --origin "87 FR 68356" --name cbp-dec-22-25
#   read the staged rows against the source, correct them, then
python -m originshift.ingest compile cbp-dec-22-25 --reviewed-by "your name"
```

Extraction never writes to a corpus — it writes a staging CSV for a person to
check. Every document is hashed, and every rule carries where it came from and
who read it, so an answer resting on a hand-fed document can always be told from
one resting on the eCFR:

```python
>>> c = Corpus.load(which="102.21")
>>> c.provenance_of("102.21(e)(1)/6201-6208")["origin"]
'87 FR 68356 (CBP Dec. 22-25, 15 Nov 2022)'
>>> c.provenance_of("102.21(e)(1)/5007") is None   # straight from the eCFR
True
```

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
| **Section 301 / Section 232 origin** | common-law **substantial transformation** | **no** |
| **AD/CVD scope** | Commerce scope analysis | **no** |
| Marking origin, other non-USMCA goods | common-law substantial transformation | **no** |
| **Preferential / FTA qualification** | the agreement's own rules of origin | **no, deliberately** |

Substantial transformation is case law, not a rule table, so it is not something
this project can compile. A tool that claimed to answer Section 301 origin from
Part 102 would be wrong, and a licensed broker would know it.

Textile origin mostly turns on facts a classification does not carry — whether
the good is of staple fibers or filaments, where the fabric-making process
happened, whether it was knit to shape. So for chapters 50–63 the tool is less
an oracle than a precise statement of *what you must establish*, drawn from the
rule that applies to your code.

## Development

```
pip install -e ".[dev,ingest]"
pytest
python -m originshift.build_corpus     # rebuild both corpora from the eCFR
python -m originshift.validate         # score them against CBP's rulings
```

Built corpora and reviewed overlays live in `src/originshift/data/` and ship
with the package, so an install works without a checkout. Point
`ORIGINSHIFT_OVERLAYS` at a directory to load your own alongside them.

## Releasing

Not yet published. `python -m build` produces both artefacts and
`python -m twine check dist/*` passes; version is `0.1.0`. Before uploading,
fill in `[project.urls]` in `pyproject.toml` — it is commented out rather than
pointing at a URL that does not resolve.
