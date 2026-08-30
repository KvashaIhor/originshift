"""The pages under docs/ are the published ones.

Two of the numbers they carry also sit in the README, and a figure stated twice
is a figure that can disagree with itself. The scorecard is generated for that
reason; the scope table is not, so it is checked here instead.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SCOPE = ROOT / "docs" / "scope.md"
VALIDATION = ROOT / "docs" / "validation.md"


def scope_rows(text: str) -> list[str]:
    """The rows of the table whose header asks what is decided by what."""
    rows = re.findall(r"^\| *(?:\*\*)?([^|]+?)(?:\*\*)? *\| *([^|]+?) *\| *([^|]+?) *\|$",
                      text, re.M)
    return [f"{a}|{b}|{c}".replace("**", "").strip()
            for a, b, c in rows
            if "In this tool?" not in c and "---" not in a]


def test_both_scope_tables_say_the_same_thing():
    readme = set(scope_rows(README.read_text(encoding="utf-8")))
    page = set(scope_rows(SCOPE.read_text(encoding="utf-8")))
    missing = page - readme
    assert not missing, f"docs/scope.md states rows the README does not: {missing}"


def test_the_scope_page_names_the_ruling_it_rests_on():
    """The textile carve-out is the one claim here a broker would check."""
    text = SCOPE.read_text(encoding="utf-8")
    assert "H323925" in text
    assert "3592" in text, "the statute the carve-out turns on is not cited"


def test_the_scorecard_answers_under_the_corpus_on_disk(corpus):
    """A stale scorecard is worse than none, because it looks current."""
    if not VALIDATION.exists():
        pytest.skip("docs/validation.md not generated yet")
    text = VALIDATION.read_text(encoding="utf-8")
    assert corpus.vintage in text, "the scorecard does not name the corpus vintage"
    assert corpus.source_issue_date in text, (
        f"the scorecard was generated from a different eCFR issue than the "
        f"corpus on disk ({corpus.source_issue_date}); regenerate it with "
        f"python -m originshift.validate --emit docs/validation.md"
    )


def test_the_readme_points_at_both_pages():
    text = README.read_text(encoding="utf-8")
    assert "docs/scope.md" in text
    assert "docs/validation.md" in text
