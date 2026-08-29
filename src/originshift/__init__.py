"""originshift — non-preferential rules of origin, as data.

    >>> from originshift import resolve
    >>> r = resolve(good="8708.29", inputs=["7208.10"], country="VN")
    >>> r.origin, r.rule_id
    ('VN', '102.20/8708.29')
"""

from .corpus import Corpus
from .grammar import CodeRange, Rule
from .resolve import OriginResult, resolve

__all__ = ["Corpus", "CodeRange", "OriginResult", "Rule", "resolve"]
