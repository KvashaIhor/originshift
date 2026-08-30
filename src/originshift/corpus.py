"""Load a built corpus and index it for lookup.

Indexing is by parsed target range, never by the HTSUS key column. The key is an
index into the printed table, not a boundary on what a rule reaches: the rule
keyed 3002.12-3002.90 also targets subheadings in 3822, and keying on the column
would silently lose it for any good in 3822.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .grammar import (
    Alternative,
    CodeRange,
    QualifiedExclusion,
    Rule,
    Shift,
    SourceCondition,
    Target,
)

#: Built corpora and reviewed overlays travel with the package, so an install
#: is usable without a checkout. The 6201-6208 overlay is not a convenience: the
#: eCFR carries no rule for most apparel, so shipping without it would leave a
#: hole in the law rather than in the tooling.
PACKAGE_DATA = Path(__file__).resolve().parent / "data"
CORPUS_DIR = PACKAGE_DATA / "corpus"

#: A corpus the user has rebuilt against a newer issue of the regulation, which
#: is preferred over the one that shipped.
from . import paths as _paths  # noqa: E402  (module-level path constants)

CORPUS_DIRS = (_paths.CORPUS_OUT, CORPUS_DIR)
OVERLAY_DIR = PACKAGE_DATA / "overlays"

#: Somewhere for a user's own overlays, kept apart from the shipped ones.
USER_OVERLAYS_ENV = "ORIGINSHIFT_OVERLAYS"


@lru_cache(maxsize=1)
def textile_coverage() -> tuple[CodeRange, ...]:
    """What 102.21 reaches, per 102.21(b)(5).

    Which hierarchy governs a good is a question about 102.21's coverage, not
    about whichever corpus the caller happens to have loaded. Asking a 102.20
    corpus returns nothing, and the good is then answered under a part that
    excludes it — so this is read from the 102.21 corpus whatever is loaded.
    """
    builds = sorted(CORPUS_DIR.glob("102.21-*.json"))
    if not builds:
        return ()
    data = json.loads(builds[-1].read_text(encoding="utf-8"))
    return tuple(_range(x) for x in data.get("covers") or ())


def covered_by_102_21(code: str) -> bool:
    return any(r.contains(code) for r in textile_coverage())


@lru_cache(maxsize=1)
def _coverage_notes() -> tuple[str, ...]:
    builds = sorted(CORPUS_DIR.glob("102.21-*.json"))
    if not builds:
        return ()
    data = json.loads(builds[-1].read_text(encoding="utf-8"))
    return tuple(data.get("covers_notes") or ())


def coverage_caveats(code: str) -> list[str]:
    """Carve-outs in 102.21's coverage that a classification cannot settle.

    102.21(b)(5) reaches "6505.00 (except for hair-nets of subheading 6505.00)".
    Hair-nets are named, not coded, so no code decides it — a hair-net belongs to
    102.20, whose rule reads "A change to hair-nets of subheading 6505.00 from
    any other subheading". The caveat travels with the answer rather than being
    resolved by a guess either way.
    """
    out = []
    for note in _coverage_notes():
        head = note.split(":", 1)[0].strip()
        try:
            if _range(head).contains(code):
                out.append(f"102.21(b)(5) reaches {note}")
        except (ValueError, IndexError):
            continue
    return out


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
            excluded_when=[
                QualifiedExclusion(
                    ranges=[_range(r) for r in q["ranges"]], when=q["when"]
                )
                for q in s.get("excluded_when", ())
            ],
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
        condition=d.get("condition"),
        sequence=d.get("sequence"),
        is_fallback=d.get("is_fallback", False),
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
    name: str = "19-CFR-102.20"
    #: The goods this part reaches. 102.21 states its own coverage at
    #: 102.21(b)(5); which hierarchy applies to a good turns on it.
    covers: list[CodeRange] = field(default_factory=list)
    #: Rules brought in from somewhere other than the primary source, keyed by
    #: rule_id. A consumer can always ask which answers rest on one.
    overlaid: dict[str, dict] = field(default_factory=dict)

    def reaches(self, code: str) -> bool:
        """Is this good one the part governs, per its own coverage list?"""
        return any(r.contains(code) for r in self.covers)

    def provenance_of(self, rule_id: str) -> dict | None:
        """How a rule got here, where it did not come from the primary source."""
        return self.overlaid.get(rule_id)

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
            name=d.get("corpus", "19-CFR-102.20"),
            covers=[_range(x) for x in d.get("covers", [])],
        )

    @classmethod
    def load(
        cls,
        path: str | Path | None = None,
        *,
        which: str = "102.20",
        overlays: bool = True,
    ) -> Corpus:
        """Load a corpus, defaulting to the most recent build of `which`."""
        if path is None:
            # A rebuilt corpus wins over the shipped one, and within either the
            # latest issue date wins.
            builds = [
                b for d in CORPUS_DIRS if d.exists()
                for b in sorted(d.glob(f"{which}-*.json"))
            ]
            if not builds:
                raise FileNotFoundError(
                    f"no {which} corpus in {' or '.join(str(d) for d in CORPUS_DIRS)}; "
                    f"run python -m originshift.build_corpus"
                )
            path = max(builds, key=lambda b: (b.stem, b.parent == CORPUS_DIRS[0]))
        corpus = cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        if overlays:
            corpus.apply_overlays()
        return corpus

    def apply_overlays(self, overlay_dir: Path | None = None) -> list[str]:
        """Merge in rules recovered from outside the primary source.

        An overlay rule replaces a rule of the same id and is otherwise added.
        Either way its provenance is kept, so a consumer can tell an answer
        resting on the eCFR from one resting on a document someone fed in.
        """
        import os

        directories = [overlay_dir] if overlay_dir else [OVERLAY_DIR]
        if overlay_dir is None and os.environ.get(USER_OVERLAYS_ENV):
            directories.append(Path(os.environ[USER_OVERLAYS_ENV]))

        applied: list[str] = []
        by_id = {r.rule_id: i for i, r in enumerate(self.rules)}
        files = [f for d in directories if d.exists() for f in sorted(d.glob("*.json"))]
        for file in files:
            data = json.loads(file.read_text(encoding="utf-8"))
            if data.get("extends") != self.name:
                continue
            for raw in data["rules"]:
                rule = Rule(
                    rule_id=raw["rule_id"],
                    regime=raw["regime"],
                    htsus=raw["htsus"],
                    scope=[_range(x) for x in raw["scope"]],
                    alternatives=[_alternative(a) for a in raw["alternatives"]],
                    section=raw["section"],
                    text=raw["text"],
                    vintage=raw["vintage"],
                    source_url=raw["source_url"],
                )
                if rule.rule_id in by_id:
                    self.rules[by_id[rule.rule_id]] = rule
                else:
                    by_id[rule.rule_id] = len(self.rules)
                    self.rules.append(rule)
                self.overlaid[rule.rule_id] = data["provenance"] | {
                    "overlay": data["overlay"]
                }
                applied.append(rule.rule_id)
        return applied

    def candidates(self, code: str) -> list[tuple[Rule, Alternative]]:
        """Every rule alternative whose target reaches `code`."""
        return [
            (rule, alt)
            for rule in self.rules
            for alt in rule.alternatives
            if alt.target and alt.target.matches(code)
        ]
