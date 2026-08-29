# originshift

**Non-preferential rules of origin, as data.** Answers "what country is this good
legally from?" and cites the rule it used.

Status: `corpus/` and `grammar/` built for the US regime. `resolve/` and
`validate/` not started. See [originshift.md](originshift.md) for the full plan.

## What is here

| Component | State |
|---|---|
| `sources.py` | Fetches primary law, pinned to a dated snapshot |
| `grammar.py` | The type system rules compile into — ranges, shifts, exceptions |
| `parse_102.py` | Compiles 19 CFR 102.20 into that grammar |
| `build_corpus.py` | Emits the versioned corpus |
| `resolve/` | Not started |
| `validate/` | Not started |

## The corpus

```
python -m originshift.build_corpus
```

Writes `data/corpus/102.20-<issue-date>.json`: **1,032 rules / 1,455
alternatives**, of which **1,441 (99.0%) are fully structured**. The remaining 14
are recorded with a reason rather than guessed at.

Every record carries its provenance — source URL, eCFR issue date, and the
nomenclature vintage it answers under — so it can be re-derived after the source
is amended.

```json
{
  "rule_id": "102.20/8708.29",
  "scope": ["8708.29"],
  "alternatives": [{
    "kind": "tariff_shift",
    "shift": { "from_level": "subheading", "excluded": ["8708.95"] },
    "target": { "ranges": ["8708.29"] },
    "text": "A change to subheading 8708.29 from any other subheading, except from subheading 8708.95."
  }],
  "vintage": "HTSUS-2026",
  "source_url": "https://www.ecfr.gov/api/versioner/v1/full/2026-08-26/title-19.xml?part=102"
}
```

**Ranges are the primitive.** `5208-5212` is stored as a range, never expanded
into the codes it covers. Expanding destroys the structure that makes the corpus
useful and inflates it for nothing.

## Design commitments

**It never guesses.** Where a rule names a good rather than a code — *"from
mustard flour or meal"*, *"from feathers or down"* — the alternative is marked
`descriptive_source` and left unstructured. An honest abstention tells the user
what to go and find out; a confident wrong answer does not.

This is load-bearing. One rule reads *"from any product other than edible meals
and flours of Chapter 2"*. Read carelessly, that becomes *must come from Chapter
2* — the exact inverse. The parser abstains instead, and a test pins it.

**Non-preferential only.** Preferential (trade-agreement) origin is out of
scope, deliberately: `US9177286B2` runs to 2034 over bill-of-materials origin
traversal with certificate output, and the EU already ships ROSA for free.
Compiling rules and resolving a good against one is not the claimed invention.

## Sources

| Source | Licence |
|---|---|
| 19 CFR 102.20, via the [eCFR API](https://www.ecfr.gov/api/versioner/v1/) | US Government work, public domain (17 U.S.C. §105) |

## Development

```
pip install -e ".[dev]"
pytest
```
