"""The 102.21(c) hierarchy, for textile and apparel products.

102.11 states in its first line that it governs goods **other than** textile and
apparel products covered by 102.21. A hat, a car seat belt or a pair of trousers
answered under 102.11 would be answered under a provision that excludes it.

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
    # 102.21(c)(3)(ii) excepts "fabrics of chapter 59" — not the whole chapter.
    # Transmission belting of 5910 and machine clothing of 5911 are goods, not
    # fabrics, and (c)(3)(ii) does reach them.
    ("range", ("5901", "5909")),
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
    #: Is the good of cotton, of wool, or a blend 16 percent or more cotton by
    #: weight? That one question decides whether 102.21(e)(2) takes the good or
    #: (e)(1) keeps it. True keeps it with (e)(1).
    excepted_fibre: bool | None = None
    #: Set where the user has determined that 102.21(c)(2) does not settle
    #: origin — that no rule in paragraph (e) is met on the facts.
    #:
    #: (c)(3) applies "where the country of origin cannot be determined under
    #: (c)(1) or (2)", and an unanswered question is not the same as a finding.
    #: Without this the resolver asks for the (c)(2) facts rather than stepping
    #: past them, because (c)(2) and (c)(3) routinely give different countries.
    c2_does_not_determine: bool = False
    #: Where the fabric was both dyed and printed — 102.21(e)(2)(i).
    dyed_and_printed_in: str | None = None
    #: Which finishing operations accompanied it. (e)(2)(i) requires two or
    #: more, so the count is the test and a single one does not carry it.
    finishing_operations: tuple[str, ...] = ()


def de_minimis_by_weight(
    failing: list[str],
    materials: list,
    good_weight: float | None,
) -> tuple[bool | None, str]:
    """102.13(c): disregard failing materials at no more than 7% of total weight.

    Every material with a failing code contributes, not one per code — two can
    share a classification.
    """
    codes = set(failing)
    weights = [m.weight for m in materials if m.code in codes]
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

#: The carve-out is one question with three limbs, so it is stated as one fact.
#: Answering a single limb settles nothing: a wool scarf is not of cotton.
EXCEPTED_FIBRE = "of cotton, of wool, or a blend 16 percent or more cotton"

#: Older callers may state the limbs separately; all three must then be settled.
FIBRE_KEYS = ("of cotton", "of wool", "cotton blend")

#: 102.21(e)(2) governs these, and only where the good is not of cotton, not of
#: wool, and not a blend 16 percent or more cotton by weight. Anything else in
#: these headings stays with (e)(1).
E2_GOODS = (
    "6213",
    "6214",
    "6117.10",
    "6302.22",
    "6302.29",
    "6302.53",
    "6302.59",
    "6302.93",
    "6302.99",
    "6303.92",
    "6303.99",
    "6304.19",
    "6304.93",
    "6304.99",
    "9404.90.85",
    "9404.90.95",
)

#: 102.21(e)(2)(i) needs the dyeing and printing to be accompanied by two or
#: more of these. One is not enough, and the count is the whole test.
FINISHING_OPERATIONS = (
    "bleaching",
    "shrinking",
    "fulling",
    "napping",
    "decating",
    "permanent stiffening",
    "weighting",
    "permanent embossing",
    "moireing",
)


def _or_join(items) -> str:
    """Join alternatives with "or". A semicolon leaves the relation between
    them to the reader, and these are branches of one rule."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + (", or " if len(items) > 2 else " or ") + items[-1]


def _e2_ranges() -> list[CodeRange]:
    return [CodeRange.parse(c) for c in E2_GOODS]


def e2_governs(good: str, facts: "TextileFacts") -> bool | None:
    """Does 102.21(e)(2) take this good, rather than the (e)(1) table?

    Returns None where the fibre has not been stated, since that is what
    decides it — a cotton scarf of 6214 stays with (e)(1).
    """
    if not any(r.contains(good) for r in _e2_ranges()):
        return False
    if facts.excepted_fibre is not None:
        return not facts.excepted_fibre
    stated = {
        phrase.lower(): held
        for phrase, held in facts.conditions.items()
        if phrase.lower() in FIBRE_KEYS
    }
    if not stated:
        return None
    # Of cotton, OR of wool, OR a blend 16 percent or more cotton — any one of
    # them keeps the good with (e)(1). Returning on the first key stated let
    # dict order decide it: {"of cotton": False, "of wool": True} said (e)(2).
    if any(stated.values()):
        return False
    # All three limbs must be settled before (e)(2) can be ruled in.
    return True if len(stated) == len(FIBRE_KEYS) else None


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
        governs = e2_governs(good, facts) if good else None
        return None if governs is None else not governs

    low = condition.lower()
    for phrase, held in facts.conditions.items():
        if phrase.lower() in low:
            return held
    return None


def defeated_by_materials(alt, good: str, materials: list):
    """The code-level part of an (e)(1) change, checked even where the rule is
    also gated on a fact or a process.

    102.21(c)(2) confers origin where each foreign material "underwent an
    applicable change in tariff classification, **and/or** met any other
    requirement" — the two are conjunctive for the material set. A rule that
    names a process still excepts what it excepts, so a material from an
    excepted provision defeats it however the process went.

    Returns the check that defeats the alternative, or None.
    """
    from .resolve import _check_material

    if alt.shift is None:
        return None

    # A source stated as a description cannot judge "not shifted" — only the
    # named exceptions are decidable there.
    code_decidable = bool(alt.shift.sources) and all(
        s.decidable_from_codes for s in alt.shift.sources
    )
    fatal = ("excluded", "not_shifted") if code_decidable else ("excluded",)

    for material in materials:
        check = _check_material(alt, good, material.code)
        if check.outcome in fatal:
            return check
    return None


def resolve_e2(good: str, country: str, facts: TextileFacts, corpus: Corpus):
    """102.21(e)(2), for the listed goods that are not of cotton or of wool."""
    from .resolve import OriginResult

    def resolved(origin, rule_id, text, why):
        return OriginResult(
            status="resolved",
            origin=origin,
            basis="process",
            rule_id=rule_id,
            rule_text=text,
            satisfied=True,
            reason=why,
            vintage=corpus.vintage,
        )

    asks: list[str] = []

    # (e)(2)(i): "two or more of the following finishing operations" means two
    # different ones, so the set is load-bearing.
    accompanying = sorted(
        {op.lower() for op in facts.finishing_operations if op.lower() in FINISHING_OPERATIONS}
    )
    if facts.dyed_and_printed_in and len(accompanying) >= 2:
        return resolved(
            facts.dyed_and_printed_in,
            "102.21(e)(2)(i)",
            "The country of origin of the good is the country in which the fabric "
            "comprising the good was both dyed and printed when accompanied by two "
            "or more of the following finishing operations: "
            + ", ".join(FINISHING_OPERATIONS),
            f"dyed and printed in {facts.dyed_and_printed_in}, accompanied by "
            + ", ".join(accompanying),
        )
    if facts.dyed_and_printed_in and len(accompanying) < 2:
        asks.append(
            f"(e)(2)(i) needs the dyeing and printing accompanied by two or more of "
            f"{', '.join(FINISHING_OPERATIONS)}. {len(accompanying)} given"
        )
    else:
        asks.append("where the fabric was both dyed and printed, and with which "
                    "finishing operations (e)(2)(i)")

    is_6117_10 = CodeRange.parse("6117.10").contains(good)
    knit = facts.conditions.get("knit to shape")
    parts = facts.conditions.get("two or more component parts")

    # (e)(2)(ii) does not reach a 6117.10 good that is knit to shape or made of
    # two or more parts — those take (e)(2)(iii). Until it is known which, (ii)
    # cannot be applied: it follows the fabric-making country where (iii)
    # follows the knitting or the assembly.
    if is_6117_10 and knit is None and parts is None:
        return OriginResult(
            status="unresolved",
            basis="process",
            rule_id="102.21(e)(2)",
            satisfied=None,
            reason="insufficient_information",
            needed=(
                f"whether {good} is knit to shape or consists of two or more "
                f"component parts. (e)(2)(ii) excepts those goods and (e)(2)(iii) "
                f"takes them, and the two follow different operations"
            ),
            vintage=corpus.vintage,
        )
    special = is_6117_10 and bool(knit or parts)

    if not special:
        # (e)(2)(ii) — but it does not reach 6117.10 goods that are knit to
        # shape or made of two or more parts; those take (e)(2)(iii).
        where = facts.process_in.get("fabric-making process")
        if where:
            return resolved(
                where,
                "102.21(e)(2)(ii)",
                "If the country of origin cannot be determined under (e)(2)(i), "
                "the country of origin is the country in which the fabric "
                "comprising the good was formed by a fabric-making process.",
                f"the fabric-making process occurred in {where}",
            )
        if is_6117_10 and knit is None and parts is None:
            asks.append(
                "whether the good is knit to shape or consists of two or more "
                "component parts, which decides (e)(2)(ii) against (e)(2)(iii)"
            )
        asks.append("where the fabric-making process occurred (e)(2)(ii)")
    else:
        # (e)(2)(iii), for 6117.10 only
        if knit:
            where = facts.process_in.get("knit")
            if where:
                return resolved(
                    where,
                    "102.21(e)(2)(iii)(A)",
                    "If the good is knit to shape, the country of origin is the "
                    "country in which a change to subheading 6117.10 from yarn "
                    "occurs, provided that the knit to shape components are knit "
                    "in a single country.",
                    f"knit from yarn in {where}",
                )
            asks.append("where the knit to shape components were knit (e)(2)(iii)(A)")
        else:
            where = facts.process_in.get("wholly assembled")
            if where:
                return resolved(
                    where,
                    "102.21(e)(2)(iii)(B)",
                    "If the good is not knit to shape and consists of two or more "
                    "component parts, the country of origin is the country in "
                    "which a change to an assembled good of subheading 6117.10 "
                    "from unassembled components occurs, provided that the change "
                    "is the result of the good being wholly assembled in a single "
                    "country.",
                    f"wholly assembled in {where}",
                )
            asks.append("where the good was wholly assembled (e)(2)(iii)(B)")

    return OriginResult(
        status="unresolved",
        basis="process",
        rule_id="102.21(e)(2)",
        satisfied=None,
        reason="insufficient_information",
        needed=(
            f"102.21(e)(2) governs {good}, and it turns on where operations "
            f"happened: " + "; ".join(asks)
        ),
        vintage=corpus.vintage,
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

    # Paragraph (e) has two tables. (e)(2) takes the listed goods unless they
    # are of cotton or of wool, in which case (e)(1) keeps them.
    takes_e2 = e2_governs(good, facts)
    e2_asks: list[str] = []
    if takes_e2:
        answered = resolve_e2(good, country, facts, corpus)
        if answered.status == "resolved":
            return answered
        # (c) is sequential. Where (e)(2) has not determined origin, (c)(3) to
        # (c)(5) still apply — returning here would strand the good at (c)(2).
        e2_asks.append(answered.needed or "")

    # (c)(2) each foreign material underwent the change specified in (e)(1),
    # "and/or met any other requirement" there. A process rule is met by stating
    # where the process happened, so it is as much a route to (c)(2) as a shift.
    findings: list[Finding] = []
    candidates = [] if takes_e2 else corpus.candidates(good)
    ordered = sorted(
        candidates, key=lambda rc: (rc[1].sequence or 0, rc[1].is_fallback)
    )
    unmet_conditions: list[str] = []
    # Only foreign materials are tested; a domestic one has nothing to shift.
    foreign = [m for m in materials if m.country is None or m.country != country]

    for rule, alt in ordered:
        holds = _condition_holds(alt.condition, facts, good)
        if holds is False:
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
        # that names one. 102.21(c)(2) takes either — but where the rule also
        # states a change, the materials must survive it.
        if alt.kind == "process" or not alt.structured:
            named = _process_named(alt.text)
            where = facts.process_in.get(named) if named else None
            if where:
                blocked = defeated_by_materials(alt, good, foreign)
                if blocked is not None:
                    findings.append(
                        Finding(
                            rule_id=rule.rule_id,
                            rule_text=alt.text,
                            satisfied=False,
                            checks=[blocked],
                        )
                    )
                    continue
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
                    trace=findings,
                )
            if named:
                unmet_conditions.append(f"where the {named} occurred")
            continue

        if alt.shift is None:
            continue
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
        carried, detail = de_minimis_by_weight(_failing(closest), materials, good_weight)
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

    # (c)(3) applies "where the country of origin cannot be determined under
    # (c)(1) or (2)". An unanswered question is not the same as cannot be
    # determined, so an (e)(1) rule that could still be met is never stepped
    # past — however many later facts the caller happens to have supplied.
    if unmet_conditions and not facts.c2_does_not_determine:
        return OriginResult(
            status="unresolved",
            basis="tariff_shift",
            rule_id=ordered[0][0].rule_id if ordered else None,
            rule_text=ordered[0][1].text if ordered else None,
            satisfied=None,
            reason="insufficient_information",
            needed=(
                "102.21(c)(2) turns on a requirement in (e)(1) that no "
                "classification carries: "
                # These are branches of one rule, so "or" states what a
                # semicolon left to the reader: establishing any one of them
                # settles which alternative applies.
                + _or_join(dict.fromkeys(u for u in unmet_conditions if u))
                + ". State which holds, or record that (c)(2) does not settle "
                "this good"
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
    # "if the good was not knit to shape and the good was wholly assembled".
    # A caller who has said the good IS knit to shape has ruled (c)(3)(ii) out,
    # whether or not they also named where it was knit.
    knit_to_shape = facts.conditions.get("knit to shape")
    if knit_to_shape and not facts.knit_to_shape_in:
        return OriginResult(
            status="unresolved",
            basis="process",
            rule_id="102.21(c)(3)(i)",
            satisfied=None,
            reason="insufficient_information",
            needed=(
                "the good is knit to shape, so 102.21(c)(3)(i) applies and "
                "(c)(3)(ii) does not — what is needed is the single country in "
                "which it was knit"
            ),
            vintage=corpus.vintage,
            trace=findings,
        )
    if facts.wholly_assembled_in and excepted is None and not knit_to_shape:
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

    asks = list(e2_asks)
    asks.append("whether the good was knit to shape, and where it was knit (c)(3)(i)")
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
            + "; ".join(a for a in asks if a)
        ),
        vintage=corpus.vintage,
        trace=findings,
    )
