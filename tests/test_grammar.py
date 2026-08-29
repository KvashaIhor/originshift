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


def test_mixed_level_spans_widen_to_the_finer_level():
    """"heading 1601 through 1602.50" is restated exactly, not rejected."""
    span = CodeRange.parse("1601", "1602.50")
    assert (str(span), span.level) == ("1601.00-1602.50", "subheading")
    assert span.contains("1601.00") and span.contains("1602.50")
    assert not span.contains("1602.51")


def test_a_coarse_upper_bound_covers_all_of_itself():
    """"subheading 1602.50 through heading 1605" must include 1605.99."""
    span = CodeRange.parse("1602.50", "1605")
    assert str(span) == "1602.50-1605.99"
    assert span.contains("1605.99")
