"""What a good has to be asked, derived from the rules that reach it.

102.21 decides only 11.9 percent of its alternatives on codes alone. The rest
turn on facts a classification never carries, and the resolver already names the
one it is missing — but it names them one at a time, which is a questionnaire
per line item when the real job is eighty of them.

This asks the corpus instead: for a given good, which alternatives reach it,
what do those alternatives turn on, and in what order should the questions be
put so the fewest of them settle it. The ordering is measured from the rules,
not fixed here — a question that decides eight alternatives is asked before one
that decides one, whatever the good happens to be.

Nothing here infers a fact. It only works out which facts to ask for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .corpus import Corpus

#: The phrases 102.21 states its conditions in, reduced to the substring that
#: identifies one. `TextileFacts.conditions` is matched as a substring of the
#: rule's own wording, so the key must appear in the condition verbatim — and
#: one key covers both branches, since "does not consist of two or more
#: component parts" contains "two or more component parts" and the boolean is
#: what separates them.
_CANON: list[tuple[str, str, str]] = [
    # (key, regex that finds it in a condition, the question to put)
    ("staple fibers", r"of staple fibers", "Is the good of staple fibers?"),
    ("continuous filaments", r"of continuous filaments",
     "Is the good of continuous filaments, including strips?"),
    ("of filaments", r"of filaments\b", "Is the good of filaments?"),
    ("two or more component parts", r"two or more component parts",
     "Does the good consist of two or more component parts?"),
    ("two or more components", r"two or more components(?! parts)",
     "Does the good consist of two or more components?"),
    ("wool or of fine animal hair", r"wool or of fine animal hair",
     "Is the good of wool or of fine animal hair?"),
    ("knit to shape", r"knit to shape", "Was the good knit to shape?"),
]


@dataclass(frozen=True)
class Question:
    """One fact to ask for, and what answering it settles."""

    key: str
    prompt: str
    kind: str
    settles: tuple[str, ...] = field(default_factory=tuple)

    @property
    def weight(self) -> int:
        return len(self.settles)


def _conditions_reaching(good: str, corpus: Corpus) -> list[tuple[str, str]]:
    """Every (alternative id, condition) among the alternatives reaching `good`.

    Identified per alternative, not per rule. Both branches of a conditional
    rule carry the same `rule_id`, so counting rules made a question that
    settles both of them score one instead of two — which is exactly backwards
    for ordering by how much an answer settles.
    """
    return [
        (f"{rule.rule_id}#{i}", (alt.condition or "").strip())
        for i, (rule, alt) in enumerate(corpus.candidates(good))
    ]


def questions_for(good: str, corpus: Corpus | None = None) -> list[Question]:
    """The facts this good turns on, most-settling first.

    Returns an empty list where the rules reaching the good need nothing beyond
    a classification — which is the 11.9 percent, and is the answer rather than
    a failure to find questions.
    """
    corpus = corpus or Corpus.load(which="102.21")
    reaching = _conditions_reaching(good, corpus)
    if not reaching:
        return []

    found: dict[str, set[str]] = {}
    unmatched: dict[str, set[str]] = {}
    for rule_id, condition in reaching:
        if not condition:
            continue
        low = condition.lower()
        hit = False
        for key, pattern, _ in _CANON:
            if re.search(pattern, low):
                found.setdefault(key, set()).add(rule_id)
                hit = True
        if not hit:
            # A condition outside the common vocabulary is still a question;
            # it is asked in the regulation's own words rather than dropped.
            unmatched.setdefault(condition, set()).add(rule_id)

    prompts = {key: prompt for key, _, prompt in _CANON}
    out = [
        Question(key, prompts[key], "condition", tuple(sorted(rules)))
        for key, rules in found.items()
    ]
    out += [
        Question(cond, f"Is it the case that {cond}?", "condition", tuple(sorted(rules)))
        for cond, rules in unmatched.items()
    ]

    # A process rule states no condition on the good; it asks where something
    # happened. Those are facts too, and the resolver needs them just as much.
    processes = {
        alt.text.strip()
        for rule, alt in corpus.candidates(good)
        if alt.kind == "process" and alt.text
    }
    for text in sorted(processes):
        out.append(
            Question(text[:60], f"Where did this occur: {text[:110]}", "process", ())
        )

    # One question decides whether (e)(1) keeps the good or (e)(2) takes it,
    # and it gates every (e)(1) answer for a good an (e)(2) range reaches. It is
    # not a condition in any rule's text, so nothing above finds it.
    from .textile import _e2_ranges

    if any(r.contains(good) for r in _e2_ranges()):
        out.insert(
            0,
            Question(
                "excepted_fibre",
                "Is the good of cotton, of wool, or a blend 16 percent or more "
                "cotton by weight? Any one of them keeps it with (e)(1).",
                "fibre",
                tuple(sorted({a for a, _ in reaching})),
            ),
        )

    # Most-settling first, then stable by key so the order never wobbles.
    out.sort(key=lambda q: (-q.weight, q.key))
    return out
