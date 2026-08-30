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

import re
from dataclasses import dataclass, field

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


#: The operations 102.21(e)(1) confers origin on. A rule that names one is met
#: by stating where it happened, which is what 102.21(c)(2) means by "met any
#: other requirement, specified for the good in paragraph (e)".
PROCESSES = (
    "fabric-making process",
    "spinning process",
    "extrusion process",
    "dyeing and printing",
    "garnetting",
    "wholly assembled",
    "knit",
)


def _process_named(text: str) -> str | None:
    low = text.lower()
    for name in PROCESSES:
        if name in low:
            return name
    return None


@dataclass
class TextileFacts:
    """Facts about production that 102.21 turns on.

    None of these is in a classification. Left unset, the resolver names the one
    it needs rather than assuming it.
    """

    #: Where a named production process occurred, e.g.
    #: {"fabric-making process": "IN"}. 102.21(c)(2) is met by a process
    #: requirement as much as by a change of code, so without this most of
    #: 102.21 could never be satisfied however much the user knew.
    process_in: dict[str, str] = field(default_factory=dict)
    #: Conditions on the good the caller affirms or denies, matched on a
    #: substring of the rule's own wording:
    #: {"two or more component parts": True}.
    conditions: dict[str, bool] = field(default_factory=dict)

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


#: "the good is not goods of heading 6302 through 6304" is a carve-out by code,
#: which the classification settles. Asking the user would be asking for what we
#: already know.
_CODE_CONDITION = re.compile(
    r"^the good is (?P<negated>not )?(?:goods? of )?"
    r"(?P<codes>(?:chapter|heading|subheading)\s.+)$",
    re.I,
)

#: But a carve-out "provided for in paragraph (e)(2)" is narrower than the
#: headings it names. (e)(2) reaches those headings *except* goods of cotton, of
#: wool, or of a blend 16 percent or more cotton by weight — so a cotton scarf
#: of 6214 is governed by (e)(1) after all. Reading the carve-out as the whole
#: heading excludes goods from the rule that reaches them.
_E2_CROSS_REFERENCE = re.compile(r"paragraph \(e\)\(2\)", re.I)

#: What settles it: the fibre the good is made of.
FIBRE_KEYS = ("of cotton", "of wool", "cotton blend")


def _condition_holds(
    condition: str | None, facts: TextileFacts, good: str | None = None
) -> bool | None:
    """Has the fact this alternative is gated on been settled?

    From the good's own classification where the condition is expressed in
    codes; otherwise from what the caller stated; otherwise not yet.
    """
    if not condition:
        return True

    references_e2 = bool(_E2_CROSS_REFERENCE.search(condition))

    if good:
        m = _CODE_CONDITION.match(condition.strip())
        if m:
            from .parse_102 import _ranges

            ranges = _ranges(m.group("codes"))
            if ranges:
                inside = any(r.contains(good) for r in ranges)
                if not m.group("negated"):
                    return inside if not references_e2 else (None if inside else False)
                # "the good is not goods of <range> provided for in (e)(2)".
                # Outside the range the carve-out cannot reach it, whatever the
                # fibre; inside it, only the fibre decides.
                if not inside:
                    return True
                if not references_e2:
                    return False

    if references_e2:
        for phrase, held in facts.conditions.items():
            if phrase.lower() in condition.lower() or phrase.lower() in FIBRE_KEYS:
                return held
        return None

    low = condition.lower()
    for phrase, held in facts.conditions.items():
        if phrase.lower() in low:
            return held
    return None


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

    # (c)(2) each foreign material underwent the change specified in (e)(1),
    # "and/or met any other requirement" there. A process rule is met by stating
    # where the process happened, so it is as much a route to (c)(2) as a shift.
    findings: list[Finding] = []
    candidates = corpus.candidates(good)
    ordered = sorted(
        candidates, key=lambda rc: (rc[1].sequence or 0, rc[1].is_fallback)
    )
    unmet_conditions: list[str] = []

    governed_by_e2 = False
    for rule, alt in ordered:
        holds = _condition_holds(alt.condition, facts, good)
        if holds is False:
            if _E2_CROSS_REFERENCE.search(alt.condition or ""):
                # The caller has said the good is not of cotton or wool, so
                # 102.21(e)(2) takes it and (e)(1) does not.
                governed_by_e2 = True
            continue
        if holds is None:
            unmet_conditions.append(
                f"whether the good is of cotton or of wool, or a blend 16 percent "
                f"or more cotton by weight — which decides whether 102.21(e)(2) "
                f"takes it instead of (e)(1)"
                if _E2_CROSS_REFERENCE.search(alt.condition or "")
                else (alt.condition or "")
            )
            continue

        # A requirement stated as a process is met by saying where it happened,
        # whether the rule is wholly a process rule or a shift with a proviso
        # that names one. 102.21(c)(2) takes either.
        if alt.kind == "process" or not alt.structured:
            named = _process_named(alt.text)
            where = facts.process_in.get(named) if named else None
            if where:
                return OriginResult(
                    status="resolved",
                    origin=where,
                    basis="process",
                    rule_id=rule.rule_id,
                    rule_text=alt.text,
                    satisfied=True,
                    reason=(
                        f"102.21(c)(2): the good met the requirement specified in "
                        f"(e)(1) — the {named} occurred in {where}"
                    ),
                    vintage=corpus.vintage,
                )
            if named:
                unmet_conditions.append(f"where the {named} occurred")
            continue

        if alt.shift is None:
            continue
        foreign = [m for m in materials if m.country is None or m.country != country]
        finding = _evaluate(rule, alt, good, [m.code for m in foreign])
        findings.append(finding)
        if finding.satisfied is True:
            return OriginResult(
                status="resolved",
                origin=country,
                basis="tariff_shift",
                rule_id=rule.rule_id,
                rule_text=alt.text,
                satisfied=True,
                vintage=corpus.vintage,
                trace=findings,
            )

    near = [f for f in findings if f.satisfied is False and _failing(f)]
    if near:
        closest = min(near, key=lambda f: len(_failing(f)))
        carried, detail = de_minimis_by_weight(_failing(closest), by_code, good_weight)
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

    # An (e)(1) rule that could still be met, if the caller settled the fact it
    # is gated on, must not be stepped past: (c)(3) is only reached where (c)(2)
    # did not determine origin.
    if unmet_conditions and not any(
        getattr(facts, name) for name in ("knit_to_shape_in", "wholly_assembled_in",
                                          "most_important_process_in",
                                          "last_important_process_in")
    ):
        return OriginResult(
            status="unresolved",
            basis="tariff_shift",
            rule_id=ordered[0][0].rule_id if ordered else None,
            rule_text=ordered[0][1].text if ordered else None,
            satisfied=None,
            reason="insufficient_information",
            needed=(
                "102.21(c)(2) turns on a requirement in (e)(1) that is not a code: "
                + "; ".join(u for u in unmet_conditions if u)
                + ". Supply it as a TextileFacts condition or process, or give the "
                "production facts (c)(3) to (c)(5) need"
            ),
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

    if governed_by_e2:
        return OriginResult(
            status="unresolved",
            reason="out_of_scope",
            needed=(
                f"102.21(e)(2) governs {good} — it sets a dyed-and-printed rule "
                f"for these headings other than goods of cotton or of wool — and "
                f"this corpus compiles (e)(1) only, so the rule must be read "
                f"directly at 19 CFR 102.21(e)(2)"
            ),
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
