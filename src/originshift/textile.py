"""The 102.21(c) hierarchy, for textile and apparel products.

102.11 states in its first line that it governs goods **other than** textile and
apparel products covered by 102.21. So a hat, a car seat belt or a pair of
trousers answered under 102.11 would be answered under a provision that excludes
it — and citing the wrong authority is the one failure this project cannot
afford, being worse than saying nothing.

102.21(c) runs five steps in sequence, and only the first two turn on
classifications. The rest turn on where an operation happened: where the good
was knit, where it was wholly assembled, where the most important assembly
occurred. Those are facts about production, so they are asked for by name.

102.13(c) applies here rather than 102.13(a): the textile de minimis allowance
is **7 percent of total weight**, not of value.
"""

from __future__ import annotations

from dataclasses import dataclass

from .corpus import Corpus
from .grammar import CodeRange

#: 102.13(c). Weight, not value.
DE_MINIMIS_WEIGHT = 0.07

#: 102.21(c)(3)(ii) does not reach these, so a wholly-assembled good of one of
#: them falls through to (c)(4) instead.
_ASSEMBLY_EXCEPTED = [
    ("chapter", "59"),
    ("heading", "5609"),
    ("heading", "5807"),
    ("heading", "5811"),
    ("heading", "6213"),
    ("heading", "6214"),
    ("range", ("6301", "6306")),
    ("heading", "6308"),
    ("subheading", "6307.10"),
    ("subheading", "6307.90"),
    ("subheading", "9404.90"),
    ("range", ("9619.00.31", "9619.00.33")),
]


def _excepted_from_assembly() -> list[CodeRange]:
    out: list[CodeRange] = []
    for kind, value in _ASSEMBLY_EXCEPTED:
        if kind == "range":
            out.append(CodeRange.parse(value[0], value[1]))
        else:
            out.append(CodeRange.parse(value))
    return out


@dataclass
class TextileFacts:
    """Facts about production that 102.21(c)(3) to (c)(5) turn on.

    None of these is in a classification. Left unset, the resolver names the one
    it needs rather than assuming it.
    """

    #: Where the good was knit, if it was knit to shape — 102.21(c)(3)(i).
    knit_to_shape_in: str | None = None
    #: Where the good was wholly assembled — 102.21(c)(3)(ii). "Wholly
    #: assembled" is defined at 102.21(b)(6): at least two components, each
    #: preexisting in essentially the same condition, combined in one country.
    wholly_assembled_in: str | None = None
    #: Where the most important assembly or manufacturing process occurred —
    #: 102.21(c)(4).
    most_important_process_in: str | None = None
    #: Where the last important assembly or manufacturing process occurred —
    #: 102.21(c)(5).
    last_important_process_in: str | None = None


def de_minimis_by_weight(
    failing: list[str],
    materials: dict,
    good_weight: float | None,
) -> tuple[bool | None, str]:
    """102.13(c): disregard failing materials at no more than 7% of total weight."""
    weights = [getattr(materials.get(m), "weight", None) for m in failing]
    if good_weight is None or not weights or any(w is None for w in weights):
        return None, (
            f"the weight of {', '.join(failing)} as a share of the total weight "
            f"of the good — under 102.13(c) they are disregarded at no more than "
            f"{DE_MINIMIS_WEIGHT:.0%}, and the change would then be met"
        )
    share = sum(w for w in weights if w is not None) / good_weight
    if share <= DE_MINIMIS_WEIGHT:
        return True, (
            f"disregarded under 102.13(c) at {share:.1%} of the total weight of "
            f"the good"
        )
    return False, (
        f"{', '.join(failing)} come to {share:.1%} of the total weight, above the "
        f"{DE_MINIMIS_WEIGHT:.0%} allowed by 102.13(c)"
    )


def resolve_textile(
    good: str,
    materials: list,
    country: str,
    *,
    corpus: Corpus,
    facts: TextileFacts,
    good_weight: float | None = None,
    wholly_obtained: bool = False,
    operation: str | None = None,
):
    """Walk 102.21(c)(1) through (5) in sequence, citing what applied."""
    from .resolve import (
        NON_QUALIFYING,
        Finding,
        OriginResult,
        _evaluate,
        _failing,
    )

    by_code = {m.code: m for m in materials}
    result = OriginResult(status="unresolved", vintage=corpus.vintage)

    # 102.17 reaches textiles too — 102.21(c) applies 102.12 through 102.19.
    if operation is not None:
        if operation not in NON_QUALIFYING:
            raise ValueError(f"unknown operation {operation!r}")
        result.rule_id = "102.17"
        result.satisfied = False
        result.reason = "non_qualifying_operation"
        result.needed = (
            f"102.17 rules out {NON_QUALIFYING[operation]} as conferring origin, "
            f"whatever the classifications. Origin falls to 102.21(c)(3)"
        )
        return result

    # (c)(1) wholly obtained or produced in a single country
    if wholly_obtained:
        return OriginResult(
            status="resolved",
            origin=country,
            basis="wholly_obtained",
            rule_id="102.21(c)(1)",
            rule_text=(
                "The country of origin of a textile or apparel product is the "
                "single country in which the good was wholly obtained or produced."
            ),
            satisfied=True,
            vintage=corpus.vintage,
        )

    # (c)(2) each foreign material underwent the change specified in (e)(1)
    findings: list[Finding] = []
    candidates = corpus.candidates(good)
    if candidates:
        foreign = [m for m in materials if m.country is None or m.country != country]
        codes = [m.code for m in foreign]
        findings = [_evaluate(rule, alt, good, codes) for rule, alt in candidates]

        met = [f for f in findings if f.satisfied is True]
        if met:
            return OriginResult(
                status="resolved",
                origin=country,
                basis="tariff_shift",
                rule_id=met[0].rule_id,
                rule_text=met[0].rule_text,
                satisfied=True,
                vintage=corpus.vintage,
                trace=findings,
            )

        undecided = [f for f in findings if f.satisfied is None]
        if undecided and not any(
            getattr(facts, name) for name in vars(TextileFacts())
        ):
            first = undecided[0]
            return OriginResult(
                status="unresolved",
                basis="tariff_shift",
                rule_id=first.rule_id,
                rule_text=first.rule_text,
                satisfied=None,
                reason="insufficient_information",
                needed=(
                    first.unverifiable[0]
                    if first.unverifiable
                    else "a fact the rule turns on"
                ),
                vintage=corpus.vintage,
                trace=findings,
            )

        near = [f for f in findings if f.satisfied is False and _failing(f)]
        if near:
            closest = min(near, key=lambda f: len(_failing(f)))
            carried, detail = de_minimis_by_weight(
                _failing(closest), by_code, good_weight
            )
            if carried:
                return OriginResult(
                    status="resolved",
                    origin=country,
                    basis="tariff_shift_de_minimis",
                    rule_id=closest.rule_id,
                    rule_text=closest.rule_text,
                    satisfied=True,
                    reason=detail,
                    vintage=corpus.vintage,
                    trace=findings,
                )

    # (c)(3)(i) knit to shape
    if facts.knit_to_shape_in:
        return OriginResult(
            status="resolved",
            origin=facts.knit_to_shape_in,
            basis="knit_to_shape",
            rule_id="102.21(c)(3)(i)",
            rule_text=(
                "If the good was knit to shape, the country of origin is the "
                "single country in which the good was knit."
            ),
            satisfied=True,
            vintage=corpus.vintage,
            trace=findings,
        )

    # (c)(3)(ii) not knit to shape and wholly assembled in a single country
    excepted = next(
        (r for r in _excepted_from_assembly() if r.contains(good)), None
    )
    if facts.wholly_assembled_in and excepted is None:
        return OriginResult(
            status="resolved",
            origin=facts.wholly_assembled_in,
            basis="wholly_assembled",
            rule_id="102.21(c)(3)(ii)",
            rule_text=(
                "If the good was not knit to shape and was wholly assembled in a "
                "single country, the country of origin is that country."
            ),
            satisfied=True,
            vintage=corpus.vintage,
            trace=findings,
        )

    # (c)(4) most important assembly or manufacturing process
    if facts.most_important_process_in:
        return OriginResult(
            status="resolved",
            origin=facts.most_important_process_in,
            basis="most_important_process",
            rule_id="102.21(c)(4)",
            rule_text=(
                "The country of origin is the single country in which the most "
                "important assembly or manufacturing process occurred."
            ),
            satisfied=True,
            vintage=corpus.vintage,
            trace=findings,
        )

    # (c)(5) last important assembly or manufacturing process
    if facts.last_important_process_in:
        return OriginResult(
            status="resolved",
            origin=facts.last_important_process_in,
            basis="last_important_process",
            rule_id="102.21(c)(5)",
            rule_text=(
                "The country of origin is the last country in which an important "
                "assembly or manufacturing process occurred."
            ),
            satisfied=True,
            vintage=corpus.vintage,
            trace=findings,
        )

    asks = ["whether the good was knit to shape, and where it was knit (c)(3)(i)"]
    if excepted is not None:
        asks.append(
            f"(c)(3)(ii) does not reach {excepted}, so a wholly-assembled good of "
            f"it falls to (c)(4)"
        )
    else:
        asks.append("where the good was wholly assembled, if it was (c)(3)(ii)")
    asks.append("where the most important assembly or manufacturing process occurred (c)(4)")

    blocked = findings[0] if findings else None
    return OriginResult(
        status="unresolved",
        basis="tariff_shift" if blocked else None,
        rule_id=blocked.rule_id if blocked else None,
        rule_text=blocked.rule_text if blocked else None,
        satisfied=False if blocked else None,
        reason="insufficient_information",
        needed=(
            "102.21(c)(1) and (c)(2) did not determine origin. The rest of the "
            "hierarchy turns on where operations happened, not on codes: "
            + "; ".join(asks)
        ),
        vintage=corpus.vintage,
        trace=findings,
    )
