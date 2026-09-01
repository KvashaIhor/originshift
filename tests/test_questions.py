"""The questionnaire asks the corpus what a good turns on.

102.21 decides 11.9 percent of its alternatives on codes alone; the resolver
names the fact it is missing one at a time, which is a questionnaire per line
item when the job is eighty of them. These hold the generator to asking the
right questions, in an order derived from the rules rather than fixed here.
"""

import pytest

from originshift.cli import _conditions
from originshift.corpus import Corpus
from originshift.questions import questions_for


@pytest.fixture(scope="module")
def textile():
    return Corpus.load(which="102.21")


def test_a_good_decidable_on_codes_alone_is_asked_nothing(textile):
    """No questions is an answer, not a failure to find any."""
    silent = [
        code
        for code in ("5007.10", "5208.11", "6203.42", "6110.20")
        if not any(
            (alt.condition or "").strip() for _, alt in textile.candidates(code)
        )
    ]
    for code in silent:
        assert all(q.kind != "condition" for q in questions_for(code, textile))


def test_questions_are_ordered_by_what_an_answer_settles(textile):
    """Measured per good, not fixed. 6110.20 turns on knit-to-shape in three
    alternatives and component parts in two, so knit-to-shape is asked first."""
    asked = [q for q in questions_for("6110.20", textile) if q.kind == "condition"]
    assert [q.key for q in asked] == ["knit to shape", "two or more component parts"]
    assert [q.weight for q in asked] == [3, 2]


def test_both_branches_of_one_rule_count_toward_the_same_question(textile):
    """6203.42 states the condition and its negation, and one answer settles
    both. Counting rule ids rather than alternatives scored this 1."""
    asked = questions_for("6203.42", textile)
    assert asked[0].key == "two or more component parts"
    assert asked[0].weight == 2


def test_a_good_in_an_e2_range_is_asked_the_fibre_question(textile):
    """One answer decides whether (e)(1) keeps the good or (e)(2) takes it, and
    it is stated in no rule's condition text, so nothing else finds it."""
    assert any(q.kind == "fibre" for q in questions_for("6214.10", textile))
    assert not any(q.kind == "fibre" for q in questions_for("6203.42", textile))


def test_a_condition_outside_the_common_vocabulary_is_still_asked(textile):
    """Twenty-five predicates appear once each. Asked in the regulation's own
    words rather than dropped for not fitting the head vocabulary."""
    asked = questions_for("6214.10", textile)
    assert any("6213 through 6214" in q.key for q in asked)


def test_a_mistyped_condition_is_refused_rather_than_inverted():
    """`_flag` answers a bool for anything, so "mabye" would assert False and
    say the good is NOT of staple fibers. A stated fact silently inverted is
    the one outcome this tool must never produce."""
    assert _conditions(['of staple fibers=yes']) == {"of staple fibers": True}
    assert _conditions(['of staple fibers=no']) == {"of staple fibers": False}
    for bad in ("of staple fibers=mabye", "of staple fibers", "=yes"):
        with pytest.raises(SystemExit):
            _conditions([bad])


def test_every_generated_condition_key_is_answerable(textile):
    """A question the CLI cannot accept is a question that should not be asked.
    Before --condition existed the CLI reached two of 102.21's conditions."""
    for code in ("6203.42", "6110.20", "5602.10", "6214.10"):
        for q in questions_for(code, textile):
            if q.kind == "condition":
                assert _conditions([f"{q.key}=yes"]) == {q.key: True}
