"""Load a built corpus and index it for lookup.

Indexing is by parsed target range, never by the HTSUS key column. The key is an
index into the printed table, not a boundary on what a rule reaches: the rule
keyed 3002.12-3002.90 also targets subheadings in 3822, and keying on the column
would silently lose it for any good in 3822.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .grammar import (
    Alternative,
    CodeRange,
    Rule,
    Shift,
    SourceCondition,
    Target,
)

CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "corpus"


def _range(text: str) -> CodeRange:
    start, _, end = text.partition("-")
    return CodeRange.parse(start, end or None)


def _alternative(d: dict) -> Alternative:
    shift = None
    if d.get("shift"):
        s = d["shift"]
        shift = Shift(
            sources=[
                SourceCondition(
                    kind=c["kind"],
                    level=c["level"],
                    ranges=[_range(r) for r in c["ranges"]],
                    outside_that_group=c["outside_that_group"],
                    text=c["text"],
                )
                for c in s["sources"]
            ],
            excluded=[_range(r) for r in s["excluded"]],
            excluded_descriptions=s["excluded_descriptions"],
            provisos=s["provisos"],
            raw_source=s["raw_source"],
        )
    target = None
    if d.get("target"):
        t = d["target"]
        target = Target(
            ranges=[_range(r) for r in t["ranges"]],
            description=t["description"],
            excluding_description=t["excluding_description"],
        )
    return Alternative(
        kind=d["kind"],
        shift=shift,
        target=target,
        text=d["text"],
        residual=d["residual"],
        unparsed_reason=d["unparsed_reason"],
    )


@dataclass
class Corpus:
    """A built rule corpus, with its provenance."""

    regime: str
    vintage: str
    source_url: str
    source_issue_date: str
    rules: list[Rule]

    @classmethod
    def from_dict(cls, d: dict) -> Corpus:
        rules = [
            Rule(
                rule_id=r["rule_id"],
                regime=r["regime"],
                htsus=r["htsus"],
                scope=[_range(x) for x in r["scope"]],
                alternatives=[_alternative(a) for a in r["alternatives"]],
                section=r["section"],
                text=r["text"],
                vintage=r["vintage"],
                source_url=r["source_url"],
            )
            for r in d["rules"]
        ]
        return cls(
            regime=d["regime"],
            vintage=d["vintage"],
            source_url=d["source_url"],
            source_issue_date=d["source_issue_date"],
            rules=rules,
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> Corpus:
        """Load a corpus file, defaulting to the most recent build."""
        if path is None:
            builds = sorted(CORPUS_DIR.glob("102.20-*.json"))
            if not builds:
                raise FileNotFoundError(
                    f"no corpus in {CORPUS_DIR}; run python -m originshift.build_corpus"
                )
            path = builds[-1]
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def candidates(self, code: str) -> list[tuple[Rule, Alternative]]:
        """Every rule alternative whose target reaches `code`."""
        return [
            (rule, alt)
            for rule in self.rules
            for alt in rule.alternatives
            if alt.target and alt.target.matches(code)
        ]
