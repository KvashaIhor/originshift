"""The resolver: apply the corpus to a good and cite what it used.

Three outcomes and no others (spec 5). `unresolved` always names the missing
item, because a user who knows what to go and find out is better served than one
handed a confident guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from typing import TYPE_CHECKING

from .corpus import Corpus, coverage_caveats, covered_by_102_21
from .grammar import Alternative, CodeRange, LEVEL_DIGITS, Rule, digits

if TYPE_CHECKING:
    from .textile import TextileFacts

Status = Literal["resolved", "unresolved", "ambiguous"]
Outcome = Literal["shifted", "not_shifted", "excluded", "needs_judgement"]

#: 102.17. A material is not treated as having undergone the change merely
#: because one of these was done to it, however the codes fall.
NON_QUALIFYING = {
    "change_in_end_use": "a change in end-use (102.17(a))",
    "dismantling": "dismantling or disassembly (102.17(b))",
    "simple_packing": (
        "simple packing, repacking or retail packaging without more than minor "
        "processing (102.17(c))"
    ),
    "mere_dilution": "mere dilution with water or another substance (102.17(d))",
    "gri_2a_collection": (
        "collecting parts that are classifiable as the assembled good under "
        "GRI 2(a), without more than minor processing (102.17(e))"
    ),
}

Operation = Literal[
    "change_in_end_use",
    "dismantling",
    "simple_packing",
    "mere_dilution",
    "gri_2a_collection",
]

#: 102.13(b) withholds the de minimis allowance from goods of these chapters.
NO_DE_MINIMIS_CHAPTERS = {"01", "02", "03", "04", "07", "08", "11", "12", "15", "17", "20"}

#: 102.13(a): 7 percent of the value of the good, or 10 percent for Chapter 22.
DE_MINIMIS = 0.07
DE_MINIMIS_CHAPTER_22 = 0.10


#: 102.15(a). A material in one of these roles is disregarded when testing
#: whether the good undergoes the applicable change. Role is a fact about how
#: the material is used, not something its classification says.
DISREGARDED_ROLES = {
    "retail_packaging": (
        "packaging materials and containers in which the good is packaged for "
        "retail sale, classified with the good (102.15(a)(1))"
    ),
    "accessory": (
        "accessories, spare parts or tools delivered with the good, classified "
        "with it and shipped with it (102.15(a)(2))"
    ),
    "packing": (
        "packing materials and containers in which the good is packed for "
        "shipment (102.15(a)(3))"
    ),
    "indirect": "indirect materials (102.15(a)(4))",
}

Role = Literal["retail_packaging", "accessory", "packing", "indirect"]


@dataclass
class Material:
    """A material incorporated into the good.

    `country` is where the material is from; left unset it is treated as foreign,
    which is the conservative reading — a material cannot be assumed domestic.
    `value` is needed only for the 102.13 de minimis allowance.
    """

    code: str
    country: str | None = None
    value: float | None = None
    #: Only for 102.13(c), the textile de minimis, which is by weight.
    weight: float | None = None
    #: A 102.15 role, if the material has one. Retail packaging classified with
    #: the good can never shift, so left as an ordinary material it always fails
    #: and then becomes the single material in a disallowed provision — which
    #: 102.18(b)(1)(iii) makes the essential-character material. The packaging
    #: would decide the origin of the goods inside it.
    role: Role | None = None

    @classmethod
    def of(cls, item: "str | Material") -> "Material":
        return item if isinstance(item, Material) else cls(code=item)


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
    #: Which rule carried the answer: wholly_obtained, exclusively_domestic,
    #: tariff_shift, or tariff_shift_de_minimis.
    basis: str | None = None
    #: Materials set aside under 102.15, and why.
    disregarded: list[str] = field(default_factory=list)
    #: Carve-outs in the part's own coverage that a classification cannot
    #: settle, and which would send the good to the other part if they applied.
    caveats: list[str] = field(default_factory=list)
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


def _check_material(
    alt: Alternative,
    good: str,
    material: str,
    qualifiers: dict[str, bool] | None = None,
) -> Check:
    """Test one input material against a shift's source conditions."""
    shift = alt.shift
    assert shift is not None

    hit = _covered(material, shift.excluded)
    if hit is not None:
        return Check(material, "excluded", f"excluded from the shift by {hit}")

    # An exception that carries its own condition bars the material only where
    # that condition holds. Applying it outright fails a change the rule allows,
    # and 102.11(b) then hands origin to the wrong country.
    for qualified in shift.excluded_when:
        hit = _covered(material, qualified.ranges)
        if hit is None:
            continue
        settled = qualifiers.get(qualified.when.lower()) if qualifiers else None
        if settled is True:
            return Check(
                material, "excluded", f"excluded by {hit} {qualified.when}"
            )
        if settled is None:
            return Check(
                material,
                "needs_judgement",
                f"{hit} is excepted only {qualified.when}, and whether it was is "
                f"not something the classifications say",
            )

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


def _evaluate(
    rule: Rule,
    alt: Alternative,
    good: str,
    materials: list[str],
    qualifiers: dict[str, bool] | None = None,
) -> Finding:
    #: What each unstructured reason actually asks the user for.
    ASKS = {
        "descriptive_source": (
            "the rule names the materials it accepts by description rather than "
            "by code, so it has to be read against what the materials are"
        ),
        "conditional_on_the_good": "a fact about the good that the rule turns on",
        "process_rule": (
            "where a named operation happened — this rule confers origin on the "
            "place of the process, not on a movement between codes"
        ),
        "reverse_phrasing": "the rule is written as a change out of a code, not into one",
        "no_source_clause": "the rule does not state its source in code terms",
    }

    if alt.shift is None or alt.unparsed_reason:
        asks: list[str] = []
        if alt.condition:
            asks.append(f"whether {alt.condition}, which this rule requires")
        asks.append(
            ASKS.get(
                alt.unparsed_reason or "",
                f"the rule is not reducible to codes ({alt.unparsed_reason})",
            )
        )
        return Finding(
            rule_id=rule.rule_id,
            rule_text=alt.text,
            satisfied=None,
            unverifiable=asks,
        )

    checks = [_check_material(alt, good, m, qualifiers) for m in materials]
    unverifiable = [
        f"the rule requires: {p}" for p in alt.shift.provisos
    ] + [f"the rule excludes: {d}" for d in alt.shift.excluded_descriptions]

    # Some rules name a good rather than reaching every good of a code: "A change
    # to vermouth of heading 2205 from heading 2204" does not apply to sangria,
    # which shares the heading. Matching on the code alone would apply the rule to
    # goods it was never written for, which is the one thing this must not do.
    # 102.21 gates many rules on a fact about the good — "If the good is of
    # staple fibers", "If the good consists of two or more component parts".
    # Like a named target, no classification settles it.
    if alt.condition:
        unverifiable.insert(0, f"whether {alt.condition}, which this rule requires")

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


def _de_minimis_limit(good: str) -> float | None:
    """The 102.13 allowance for a good, or None where 102.13(b) withholds it."""
    chapter = digits(good)[:2].zfill(2)
    if chapter in NO_DE_MINIMIS_CHAPTERS:
        return None
    return DE_MINIMIS_CHAPTER_22 if chapter == "22" else DE_MINIMIS


def _failing(finding: Finding) -> list[str]:
    return [c.material for c in finding.checks if c.outcome in ("not_shifted", "excluded")]


def _de_minimis(
    finding: Finding,
    good: str,
    materials: list[Material],
    good_value: float | None,
) -> tuple[bool | None, str]:
    """Apply 102.13 to the materials that failed the shift.

    Returns whether the allowance carries the good, and what is missing if that
    cannot be said. A material disregarded under 102.13 does not have to shift.
    """
    limit = _de_minimis_limit(good)
    if limit is None:
        return False, (
            f"102.13(b) withholds the de minimis allowance from goods of "
            f"chapter {digits(good)[:2]}"
        )

    # Every material with a failing code, not one per code: two materials can
    # share a classification, and collapsing them counted one value twice and
    # lost the other.
    failed = set(_failing(finding))
    contributing = [m for m in materials if m.code in failed]
    values = [m.value for m in contributing]
    if good_value is None or any(v is None for v in values) or not values:
        return None, (
            f"the value of {', '.join(sorted(failed))} as a share of the value of the "
            f"good — under 102.13 they are disregarded at no more than "
            f"{limit:.0%}, and the shift would then be met"
        )

    share = sum(v for v in values if v is not None) / good_value
    if share <= limit:
        return True, f"disregarded under 102.13 at {share:.1%} of the value of the good"
    return False, (
        f"{', '.join(sorted(failed))} come to {share:.1%} of the value of the good, "
        f"above the {limit:.0%} allowed by 102.13"
    )


def _essential_character(
    rule: Rule,
    alt: Alternative,
    good: str,
    materials: list[Material],
    qualifiers: dict[str, bool] | None = None,
) -> tuple[list[Material], list[Check]]:
    """The materials 102.18(b)(1) lets you consider for essential character.

    Only materials "classified in a tariff provision from which a change in
    tariff classification is not allowed under the § 102.20 specific rule" count
    — which is exactly the set that failed the shift. Two departures from
    102.11(a)(3) matter: domestic materials are considered here as well as
    foreign ones, and the question is which provision the material sits in
    rather than whose it is.
    """
    considered: list[Material] = []
    checks: list[Check] = []
    for material in materials:
        check = _check_material(alt, good, material.code, qualifiers)
        checks.append(check)
        if check.outcome in ("not_shifted", "excluded"):
            considered.append(material)
    return considered, checks


def resolve(
    good: str,
    inputs: list[str] | list[Material],
    country: str,
    **kwargs,
) -> OriginResult:
    """Decide whether `country` confers origin on `good`, and cite the rule.

    See `_resolve` for the hierarchy. This wrapper sets aside the materials
    102.15 says to disregard and records them on whatever result comes back, so
    no exit path can quietly lose that they were set aside.
    """
    materials = [Material.of(m) for m in inputs]
    for m in materials:
        if m.role is not None and m.role not in DISREGARDED_ROLES:
            raise ValueError(
                f"unknown 102.15 role {m.role!r}; expected one of "
                + ", ".join(sorted(DISREGARDED_ROLES))
            )
    kept = [m for m in materials if m.role is None]
    set_aside = [m for m in materials if m.role is not None]

    result = _resolve(good, kept, country, **kwargs)
    result.disregarded = [
        f"{m.code}: {DISREGARDED_ROLES[m.role]}" for m in set_aside if m.role
    ]
    result.caveats = coverage_caveats(good)
    return result


def _resolve(
    good: str,
    inputs: list[str] | list[Material],
    country: str,
    *,
    good_value: float | None = None,
    wholly_obtained: bool = False,
    is_set: bool = False,
    operation: Operation | None = None,
    good_weight: float | None = None,
    textile: "TextileFacts | None" = None,
    qualifiers: dict[str, bool] | None = None,
    regime: str = "US",
    corpus: Corpus | None = None,
) -> OriginResult:
    """Decide whether `country` confers origin on `good`, and cite the rule.

    Walks 102.11 in order. Paragraph (a) is answerable from classifications:
    (a)(1) wholly obtained, (a)(2) produced exclusively from domestic materials,
    (a)(3) every foreign material undergoes the change set out in 102.20, with
    the 102.13 de minimis allowance applied to any that do not.

    Where (a) produces no answer, 102.11(b) follows the single material that
    imparts the essential character. That is decidable more often than it looks:
    102.18(b)(1) confines the candidates to materials in a provision from which
    change is not allowed, and 102.18(b)(1)(iii) settles the case outright where
    only one qualifies. Judgement is only reached with two or more, where
    102.18(b)(2) weighs bulk, quantity, value and role — and there the resolver
    names the candidates and stops. Set `is_set` for a good classified as a set,
    which 102.11(b) excepts and 102.11(c) takes instead.

    Naming an `operation` from 102.17 defeats (a)(3) however the codes fall: a
    material does not undergo the change merely by being repacked or dismantled.

    `good` and `inputs` are HS codes under the corpus's nomenclature vintage;
    an input may instead be a `Material` carrying its country and value.
    `country` is where the operation happened.
    """
    corpus = corpus or Corpus.load()
    if regime != corpus.regime:
        raise ValueError(f"corpus is regime {corpus.regime}, not {regime}")

    materials = [Material.of(m) for m in inputs]
    base = OriginResult(status="unresolved", vintage=corpus.vintage)

    # 102.11 governs goods "other than textile and apparel products covered by
    # § 102.21", so a covered good takes 102.21(c) instead. Citing 102.11 for a
    # hat or a seat belt would cite a provision that excludes it.
    if covered_by_102_21(good):
        from .textile import TextileFacts, resolve_textile

        if corpus.name != "19-CFR-102.21":
            corpus = Corpus.load(which="102.21")

        return resolve_textile(
            good,
            materials,
            country,
            corpus=corpus,
            facts=textile or TextileFacts(),
            good_weight=good_weight,
            wholly_obtained=wholly_obtained,
            operation=operation,
        )

    # 102.11(a)(1)
    if wholly_obtained:
        return OriginResult(
            status="resolved",
            origin=country,
            basis="wholly_obtained",
            rule_id="102.11(a)(1)",
            rule_text="The good is wholly obtained or produced.",
            satisfied=True,
            vintage=corpus.vintage,
        )

    # 102.11(a)(2). A material of unstated origin cannot be assumed domestic.
    foreign = [m for m in materials if m.country is None or m.country != country]
    if materials and not foreign:
        return OriginResult(
            status="resolved",
            origin=country,
            basis="exclusively_domestic",
            rule_id="102.11(a)(2)",
            rule_text="The good is produced exclusively from domestic materials.",
            satisfied=True,
            vintage=corpus.vintage,
        )

    # 102.17, which (a)(3) picks up through "all other applicable requirements".
    if operation is not None:
        if operation not in NON_QUALIFYING:
            raise ValueError(
                f"unknown operation {operation!r}; expected one of "
                + ", ".join(sorted(NON_QUALIFYING))
            )
        return OriginResult(
            status="unresolved",
            basis="tariff_shift",
            rule_id="102.17",
            rule_text=(
                "A foreign material shall not be considered to have undergone an "
                "applicable change in tariff classification specified in § 102.20 "
                "… merely by reason of "
                + NON_QUALIFYING[operation]
            ),
            satisfied=False,
            reason="non_qualifying_operation",
            needed=(
                f"102.17 rules out {NON_QUALIFYING[operation]} as conferring "
                f"origin, whatever the classifications. Origin falls to be "
                f"determined under 102.11(b)"
            ),
            vintage=corpus.vintage,
        )

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

    if not materials:
        base.reason = "no_input_materials_given"
        base.needed = (
            "the HS codes of the materials; with none, origin turns on "
            "102.11(a)(1)-(2), which need a fact about production rather than "
            "a classification"
        )
        return base

    codes = [m.code for m in foreign]
    findings = [
        _evaluate(rule, alt, good, codes, qualifiers) for rule, alt in candidates
    ]

    # 102.11(a)(3)
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

    # An alternative that cannot be settled leaves (a)(3) open: the shift has
    # not failed yet, so neither 102.13 nor 102.11(b) is reached.
    undecided = [f for f in findings if f.satisfied is None]
    if undecided:
        first = undecided[0]
        needed = (
            first.unverifiable[0]
            if first.unverifiable
            else next(c.detail for c in first.checks if c.outcome == "needs_judgement")
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

    # Every alternative has definitely failed. 102.13 disregards the materials
    # that failed if they are small enough, which can still carry the good.
    near = [f for f in findings if f.satisfied is False and _failing(f)]
    closest = min(near, key=lambda f: len(_failing(f))) if near else None
    de_minimis_note = ""
    if closest is not None:
        carried, detail = _de_minimis(closest, good, materials, good_value)
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
        # The shift itself is settled either way, so the finding stands and the
        # de minimis route is named rather than swallowing the answer.
        de_minimis_note = f" Unless {detail}." if carried is None else f" {detail.capitalize()}."

    # Paragraph (a) has produced no answer, so 102.11(b) applies: the country of
    # origin of the single material that imparts the essential character.
    first = findings[0] if closest is None else closest
    blocking = next(
        (c for c in first.checks if c.outcome in ("not_shifted", "excluded")), None
    )
    why = f"material {blocking.material} {blocking.detail}. " if blocking else ""
    unresolved = OriginResult(
        status="unresolved",
        basis="tariff_shift",
        rule_id=first.rule_id,
        rule_text=first.rule_text,
        satisfied=False,
        reason="shift_not_satisfied",
        vintage=corpus.vintage,
        trace=findings,
    )

    if is_set:
        unresolved.needed = (
            f"{why}Origin does not fall to {country} under 102.11(a).{de_minimis_note} "
            f"102.11(b) does not reach a good classified as a set, so 102.11(c) "
            f"applies: the origin of all materials that merit equal consideration"
        )
        return unresolved

    # 102.18(b)(1) confines the candidates to materials in a provision from
    # which change is not allowed "under the § 102.20 specific rule ...
    # applicable to the good" — that is the alternative that actually blocked
    # the change. Keying on rule_id alone took the rule's first alternative
    # instead, so the result could report the change blocked by one material
    # under alternative 2 and then nominate the materials alternative 2 says
    # did shift.
    rule, alt = next(
        (
            (r, a)
            for r, a in candidates
            if r.rule_id == first.rule_id and a.text == first.rule_text
        ),
        next(
            ((r, a) for r, a in candidates if r.rule_id == first.rule_id),
            candidates[0],
        ),
    )
    considered, _ = _essential_character(rule, alt, good, materials, qualifiers)

    if len(considered) == 1:
        # 102.18(b)(1)(iii): where only one material sits in a provision from
        # which change is not allowed, that material is the essential-character
        # material. No judgement is called for, and none should be invented.
        material = considered[0]
        if material.country:
            return OriginResult(
                status="resolved",
                origin=material.country,
                basis="essential_character",
                rule_id="102.11(b)(1)",
                rule_text=(
                    "The country of origin of the good is the country or countries "
                    "of origin of the single material that imparts the essential "
                    "character to the good."
                ),
                satisfied=True,
                reason=(
                    f"{material.code} is the only material in a provision from "
                    f"which change is not allowed, so 102.18(b)(1)(iii) makes it "
                    f"the essential-character material"
                ),
                vintage=corpus.vintage,
                trace=findings,
            )
        unresolved.needed = (
            f"{why}Origin does not fall to {country} under 102.11(a).{de_minimis_note} "
            f"Under 102.11(b) it follows {material.code}, the only material in a "
            f"provision from which change is not allowed (102.18(b)(1)(iii)) — so "
            f"what is needed is the country of origin of {material.code}, or, "
            f"where it is fungible and commingled, an inventory management "
            f"method under 102.11(b)(2)"
        )
        return unresolved

    if len(considered) > 1:
        # 102.11(b)(1) follows the country of the essential-character material.
        # Where every candidate shares a country, which one it is cannot change
        # the answer, and the factors in 102.18(b)(2) need not be reached.
        origins = {m.country for m in considered}
        if len(origins) == 1 and None not in origins:
            (only,) = origins
            return OriginResult(
                status="resolved",
                origin=only,
                basis="essential_character",
                rule_id="102.11(b)(1)",
                rule_text=(
                    "The country of origin of the good is the country or countries "
                    "of origin of the single material that imparts the essential "
                    "character to the good."
                ),
                satisfied=True,
                reason=(
                    f"every material 102.18(b)(1) admits — "
                    + ", ".join(m.code for m in considered)
                    + f" — is of {only}, so which imparts the essential character "
                    f"cannot change the answer"
                ),
                vintage=corpus.vintage,
                trace=findings,
            )

        listed = ", ".join(m.code for m in considered)
        unresolved.needed = (
            f"{why}Origin does not fall to {country} under 102.11(a).{de_minimis_note} "
            f"Under 102.11(b) it follows whichever of {listed} imparts the "
            f"essential character. With more than one candidate 102.18(b)(2) "
            f"leaves that to the bulk, quantity, weight, value and role of each, "
            f"which are not classifications and are not in this corpus"
        )
        return unresolved

    unresolved.needed = (
        f"{why}Origin does not fall to {country} under 102.11(a).{de_minimis_note} "
        f"Next is 102.11(b), and no material sits in a provision from which "
        f"change is disallowed, so there is no essential-character candidate to "
        f"follow"
    )
    return unresolved
