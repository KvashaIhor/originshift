# Contributing

## The most valuable thing you can do

**Check a rule against the eCFR and open an issue when the corpus disagrees.**

That is not a courtesy ask. A compilation can be wrong in ways no test catches.
A range reads backwards. An exception attaches to the wrong alternative. A
condition inverts, and every test still passes because nothing else knows what
the rule was supposed to say.

The validator scores against CBP's own rulings and publishes every disagreement
in [docs/validation.md](docs/validation.md), which is where to look first — but
it only reaches rules CBP has quoted in a ruling. Most have not been.

If you work with Part 102, you will read a rule here that you already know the
answer to. That is the check nothing else in this project can perform.

An issue is enough. The rule id, what the eCFR says, and what the corpus holds.

## Reviewing an ingested rule

Some rules reach the corpus from a document the eCFR does not carry — the
102.21(e)(1) entry for headings 6201 through 6208, and the two 102.20 entries
CBP Dec. 22-25 failed to incorporate. Those come in through `ingest`, which
writes to a staging file and refuses to compile without `--reviewed-by`.

Reviewing one means reading the staged text against the Federal Register,
character by character, and saying so under your own name. The last review
caught a page-heading fragment the extractor had appended to a rule, which the
parser had structured without complaint.

There is no backlog to work through. Every Federal Register document amending
Part 102 between 1994 and 2026 has been checked, one failed to incorporate, and
all three of its entries are already overlaid. A new one appears when a future
amendment fails the same way, which is what
[docs/validation.md](docs/validation.md) and the `anomalies` list exist to
surface. Open an issue if you find one.

## Running it

```
pip install -e ".[dev,ingest]"
pytest                                 # passes on a fresh clone
python -m originshift.validate --fetch # the CROSS rulings, ~5 min, ~12 MB
pytest                                 # now including the validation measures
```

The rulings are not committed. Until they are fetched, those tests skip and say
so.

## What the tests are for

They hold claims. `test_readme.py` fails when a number in
the README stops matching the code. `test_docs.py` fails when the two copies of
the scope table disagree, or when the scorecard answers under a different eCFR
issue than the corpus on disk. `test_overlays.py` fails when an overlay is filed
against a corpus that does not govern the goods it carries.

If you change a figure, the test that guarded it should fail. If it does not,
the test was not guarding it.

**New behaviour arrives with a test that fails without it.** Not as a rule about
coverage — as the only way to tell a feature from an assertion that it works.
The same goes for a bug fix: write the test that reproduces the bug first, so
the fix has something to prove.

`ruff check src tests` runs in CI and must be clean. The rule selection in
`pyproject.toml` is narrow on purpose; if a rule fights the code rather than
finding a defect in it, say so in the pull request and it can be turned off.

## What will not be merged

**Anything that repairs the regulation.** Defects in the source are reported and
kept, with the verbatim text. A corpus that silently corrects its source is
answering under a rule that does not exist.

**Anything that guesses.** The three outcomes are `resolved`, `unresolved` and
`ambiguous`. A determination that is not supported by a rule on the facts given
must come back `unresolved` naming what is missing. Lowering the abstention rate
by inferring a fact is the one change that defeats the purpose of the tool.

**A dependency**, unless it is doing something genuinely hard. The package
depends on `certifi` and nothing else, and that is deliberate: it goes into
environments where an install is a procurement question.

## Style

Match what is there. Comments state the invariant, never the incident that
produced it. Names say what a thing is. The README's own history is the guide:
figures carry their basis, and a claim that has been corrected keeps the
correction visible.
