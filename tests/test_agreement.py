"""Agreement: does the resolver reach CBP's conclusion on real facts?"""

import pytest

from originshift import validate


@pytest.fixture(scope="module")
def cases(corpus):
    path = validate.CASES / "agreement-cases.json"
    if not path.exists():
        pytest.skip("curated cases not present")
    return validate.agreement(corpus)


def test_the_curated_set_is_intact(cases):
    assert len(cases) == 30


def test_the_resolver_never_contradicts_cbp(cases):
    """Where the resolver gives a definite call, it must match the authority.

    A wrong answer is worse than no answer here: the product's whole claim is
    that its output can be defended to CBP.
    """
    wrong = [c for c in cases if c.agrees is False]
    assert wrong == [], [(c.ruling, c.cbp, c.ours) for c in wrong]


def test_coverage_clears_the_bar_for_a_useful_tool(cases):
    """60% coverage with honest abstention is shippable; 95% accuracy on 10%
    coverage is not."""
    decided = [c for c in cases if c.agrees is not None]
    assert len(decided) / len(cases) > 0.60


def test_abstentions_are_the_cases_that_turn_on_a_non_code_fact(cases):
    """Each abstention should name the fact, not shrug."""
    for case in cases:
        if case.ours == "abstained":
            assert case.detail.strip()
