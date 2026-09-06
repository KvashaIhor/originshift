"""Layer 2, and the reason it has a control at all.

The measurement is only evidence if a population with no missing definition
reaches outside less. These tests hold that logic, including the case where the
answer is "this measurement does not support the claim" — a validator that can
only report success is not a validator.
"""

from originshift import validate_terms


def _result(role, query, scored, reached, by=None):
    return {
        "population": query,
        "role": role,
        "query": query,
        "why": "because",
        "in_population": scored,
        "considered": scored,
        "scored": scored,
        "excluded_no_text": 0,
        "excluded_unfetched": 0,
        "reached_outside": reached,
        "share": reached / scored,
        "by_authority": by or {},
    }


def test_the_difference_is_reported_in_percentage_points(tmp_path):
    """It was printed as "+0.3 percentage points" when the gap was 28.5, because
    a fraction was formatted as a float. A wrong number in a published document
    is worse than no number."""
    out = tmp_path / "v.md"
    validate_terms.emit(
        out,
        [
            _result("subject", "19 CFR 134.1", 1000, 576),
            _result("control", "19 CFR 102.20", 1000, 291),
        ],
    )
    text = out.read_text()
    assert "+28.5 percentage points" in text
    assert "+0.3 percentage points" not in text


def test_a_null_result_is_reported_as_a_null_result(tmp_path):
    """The control exists so the measurement can fail. If both populations reach
    outside at the same rate, the document has to say the claim is unsupported
    rather than quietly print the subject's number."""
    out = tmp_path / "v.md"
    validate_terms.emit(
        out,
        [
            _result("subject", "19 CFR 134.1", 1000, 500),
            _result("control", "19 CFR 102.20", 1000, 490),
        ],
    )
    text = out.read_text()
    assert "**That is not evidence.**" in text
    assert "does not support it" in text


def test_the_authority_contrast_is_rated_per_hundred_not_raw(tmp_path):
    """The populations are different sizes — 1,092 against 320 — so raw counts
    would manufacture a contrast from the denominators alone."""
    out = tmp_path / "v.md"
    validate_terms.emit(
        out,
        [
            _result("subject", "19 CFR 134.1", 1000, 600, {"Koru": 100}),
            _result("control", "19 CFR 102.20", 100, 30, {"Koru": 10}),
        ],
    )
    text = out.read_text()
    # 10 per 100 in both, so the ratio is 1.0x despite 100 against 10 raw
    assert "1.0x" in text


def test_the_reach_detector_finds_the_named_authorities():
    assert "Gibson-Thomsen" in validate_terms._reach("see U.S. v. Gibson-Thomsen Co.")
    assert "Koru" in validate_terms._reach("Koru North America v. United States")
    # a reported decision with no name we track still counts, once
    assert validate_terms._reach("see 27 C.I.T. 1234") == ["unnamed reported decision"]
    # and a ruling that reaches for nothing outside is not counted
    assert validate_terms._reach("The article is marked in accordance with the rule.") == []


def test_the_named_authority_wins_over_the_backstop():
    """A ruling citing Gibson-Thomsen by name and by reporter should be counted
    as Gibson-Thomsen, not as an unnamed decision, or the specific contrast is
    diluted into the generic bucket."""
    hits = validate_terms._reach("U.S. v. Gibson-Thomsen Co., 27 C.C.P.A. 267")
    assert hits == ["Gibson-Thomsen"]


def test_the_populations_declare_a_subject_and_a_control():
    roles = {v["role"] for v in validate_terms.POPULATIONS.values()}
    assert roles == {"subject", "control"}
