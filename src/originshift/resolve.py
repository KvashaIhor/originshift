"""The resolver: apply the corpus to a good and cite what it used.

Three outcomes and no others (spec 5). `unresolved` always names the missing
item, because a user who knows what to go and find out is better served than one
handed a confident guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .corpus import Corpus
from .grammar import Alternative, CodeRange, LEVEL_DIGITS, Rule, digits

Status = Literal["resolved", "unresolved", "ambiguous"]
Outcome = Literal["shifted", "not_shifted", "excluded", "needs_judgement"]


@dataclass
class Check:
    """What the resolver concluded about one input material, and why."""

    material: str
    outcome: Outcome
    detail: str


@dataclass
class Finding:
    """One rule alternative, evaluated."""

    rule_id: str
    rule_text: str
    satisfied: bool | None  # None where it cannot be settled from codes
    checks: list[Check] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)


@dataclass
class OriginResult:
    status: Status
    origin: str | None = None
    basis: str | None = None
    rule_id: str | None = None
    rule_text: str | None = None
    satisfied: bool | None = None
    reason: str | None = None
    needed: str | None = None
    vintage: str | None = None
    trace: list[Finding] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.status == "resolved"


def _position(code: str, level: str) -> str:
    return digits(code)[: LEVEL_DIGITS[level]]


def _crosses(good: str, material: str, level: str) -> bool:
    """Does the material sit outside the good's own position at this level?"""
    return _position(good, level) != _position(material, level)


def _covered(material: str, ranges: list[CodeRange]) -> CodeRange | None:
    return next((r for r in ranges if r.contains(material)), None)


def _check_material(alt: Alternative, good: str, material: str) -> Check:
    """Test one input material against a shift's source conditions."""
    shift = alt.shift
    assert shift is not None

    hit = _covered(material, shift.excluded)
    if hit is not None:
        return Check(material, "excluded", f"excluded from the shift by {hit}")

    undecidable: list[str] = []
    for source in shift.sources:
        if source.kind == "any_other":
            if source.outside_that_group:
                if _covered(material, alt.target.ranges) is None:
                    return Check(
                        material,
                        "shifted",
                        f"outside the group {_fmt(alt.target.ranges)}",
                    )
            elif _crosses(good, material, source.level):
                return Check(
                    material,
                    "shifted",
                    f"in a different {source.level} from {good}",
                )
        elif source.kind == "named":
            hit = _covered(material, source.ranges)
            if hit is not None:
                return Check(material, "shifted", f"from {hit}, as the rule requires")
        elif source.kind == "same_position":
            hit = _covered(material, source.ranges)
            if hit is not None:
                # The rule allows a different good from within this position. No
                # HS code can say whether two goods differ, so this needs a fact
                # the codes do not carry.
                undecidable.append(
                    f"whether the material is a different good from the finished "
                    f"article, both being within {hit}"
                )

    if undecidable:
        return Check(material, "needs_judgement", undecidable[0])
    return Check(
        material, "not_shifted", f"does not satisfy: {shift.raw_source or alt.text}"
    )


def _fmt(ranges: list[CodeRange]) -> str:
    return ", ".join(str(r) for r in ranges)


def _evaluate(rule: Rule, alt: Alternative, good: str, materials: list[str]) -> Finding:
    if alt.shift is None or alt.unparsed_reason:
        return Finding(
            rule_id=rule.rule_id,
            rule_text=alt.text,
            satisfied=None,
            unverifiable=[
                f"the rule is not reducible to codes ({alt.unparsed_reason}); "
                f"it must be read directly"
            ],
        )

    checks = [_check_material(alt, good, m) for m in materials]
    unverifiable = [
        f"the rule requires: {p}" for p in alt.shift.provisos
    ] + [f"the rule excludes: {d}" for d in alt.shift.excluded_descriptions]

    # Some rules name a good rather than reaching every good of a code: "A change
    # to vermouth of heading 2205 from heading 2204" does not apply to sangria,
    # which shares the heading. Matching on the code alone would apply the rule to
    # goods it was never written for, which is the one thing this must not do.
    target = alt.target
    if target is not None and target.description:
        unverifiable.append(
            f"whether the good is {target.description.rstrip(' of')!r}, which is "
            f"what this rule covers within {_fmt(target.ranges)}"
        )
    if target is not None and target.excluding_description:
        unverifiable.append(
            f"whether the good is {target.excluding_description!r}, which this "
            f"rule excludes"
        )

    if any(c.outcome in ("not_shifted", "excluded") for c in checks):
        satisfied: bool | None = False
    elif any(c.outcome == "needs_judgement" for c in checks) or unverifiable:
        satisfied = None
    else:
        satisfied = True
    return Finding(rule.rule_id, alt.text, satisfied, checks, unverifiable)


def resolve(
    good: str,
    inputs: list[str],
    country: str,
    regime: str = "US",
    corpus: Corpus | None = None,
) -> OriginResult:
    """Decide whether `country` confers origin on `good`, and cite the rule.

    `good` and `inputs` are HS codes under the corpus's nomenclature vintage.
    `country` is where the operation happened.
    """
    corpus = corpus or Corpus.load()
    if regime != corpus.regime:
        raise ValueError(f"corpus is regime {corpus.regime}, not {regime}")

    base = OriginResult(status="unresolved", vintage=corpus.vintage)

    candidates = corpus.candidates(good)
    if not candidates:
        base.reason = "no_rule_for_this_classification"
        chapter = digits(good)[:2]
        if "50" <= chapter <= "63":
            why = "textiles and apparel are governed by 102.21, not 102.20"
        else:
            why = (
                f"no rule in 102.20 targets it under {corpus.vintage}; the code "
                f"may belong to an earlier nomenclature vintage"
            )
        base.needed = f"a rule covering {good} — {why}"
        return base

    if not inputs:
        base.reason = "no_input_materials_given"
        base.needed = (
            "the HS codes of the non-originating materials; with none, origin "
            "turns on 102.11(a)(1)-(2), which this corpus does not cover"
        )
        return base

    findings = [_evaluate(rule, alt, good, inputs) for rule, alt in candidates]

    met = [f for f in findings if f.satisfied is True]
    if met:
        by_rule = {f.rule_id for f in met}
        if len(by_rule) > 1:
            return OriginResult(
                status="ambiguous",
                reason="more_than_one_rule_is_satisfied",
                needed=(
                    "a choice between "
                    + ", ".join(sorted(by_rule))
                    + "; each is satisfied and this corpus does not rank them"
                ),
                vintage=corpus.vintage,
                trace=findings,
            )
        first = met[0]
        return OriginResult(
            status="resolved",
            origin=country,
            basis="tariff_shift",
            rule_id=first.rule_id,
            rule_text=first.rule_text,
            satisfied=True,
            vintage=corpus.vintage,
            trace=findings,
        )

    undecided = [f for f in findings if f.satisfied is None]
    if undecided:
        first = undecided[0]
        needed = (
            first.unverifiable[0]
            if first.unverifiable
            else next(
                c.detail for c in first.checks if c.outcome == "needs_judgement"
            )
        )
        return OriginResult(
            status="unresolved",
            basis="tariff_shift",
            rule_id=first.rule_id,
            rule_text=first.rule_text,
            satisfied=None,
            reason="insufficient_information",
            needed=needed,
            vintage=corpus.vintage,
            trace=findings,
        )

    first = findings[0]
    blocking = next(
        (c for c in first.checks if c.outcome in ("not_shifted", "excluded")), None
    )
    return OriginResult(
        status="unresolved",
        basis="tariff_shift",
        rule_id=first.rule_id,
        rule_text=first.rule_text,
        satisfied=False,
        reason="shift_not_satisfied",
        needed=(
            f"material {blocking.material} {blocking.detail}; origin does not fall "
            f"to {country} under this rule, and 102.11(b)-(d) would apply next"
            if blocking
            else "the rule is not satisfied"
        ),
        vintage=corpus.vintage,
        trace=findings,
    )
