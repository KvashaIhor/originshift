from originshift.grammar import CodeRange, level_of


def test_level_inferred_from_digit_count():
    assert level_of("04") == "chapter"
    assert level_of("8708") == "heading"
    assert level_of("8708.29") == "subheading"
    assert level_of("8708.29.50") == "tariff_item"


def test_range_is_compared_at_its_own_level():
    headings = CodeRange.parse("0101", "0106")
    assert headings.contains("0104.10")  # a subheading inside the span
    assert headings.contains("0101")
    assert not headings.contains("0107")


def test_range_rejects_a_code_too_coarse_to_place():
    # A chapter cannot answer a question asked at subheading level.
    assert not CodeRange.parse("8708.29").contains("8708")


def test_ranges_may_not_mix_levels():
    import pytest

    with pytest.raises(ValueError):
        CodeRange.parse("0101", "0104.10")
