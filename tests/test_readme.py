"""The README documents a data format other people will code against.

It drifted once already: it described a `shift.from_level` field for several
commits after the disjunction fix replaced it with `shift.sources`. Anyone
following it would have written code against a field that was not there.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def documented_record():
    blocks = re.findall(r"```json\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    if not blocks:
        pytest.fail("the README no longer shows a corpus record")
    return json.loads(blocks[0])


def test_the_documented_record_matches_a_real_one(documented_record, corpus):
    """Every field shown must exist, with the shape shown, in the built corpus."""
    rule = next(r for r in corpus.rules if r.rule_id == documented_record["rule_id"])
    actual = rule.to_dict()

    def compare(shown, real, path="") -> None:
        if isinstance(shown, dict):
            assert isinstance(real, dict), f"{path}: shape differs"
            for key, value in shown.items():
                assert key in real, f"{path}.{key} is documented but not in the corpus"
                compare(value, real[key], f"{path}.{key}")
        elif isinstance(shown, list):
            assert isinstance(real, list), f"{path}: shape differs"
            for i, value in enumerate(shown):
                compare(value, real[i], f"{path}[{i}]")
        else:
            assert shown == real, f"{path}: README says {shown!r}, corpus has {real!r}"

    compare(documented_record, actual)


def test_the_headline_counts_are_current(corpus, corpus_102_21):
    """The tables at the top state rule counts. Stale numbers mislead."""
    text = README.read_text(encoding="utf-8")
    assert f"{len(corpus.rules):,}" in text, f"102.20 now has {len(corpus.rules)} rules"
    base = [r for r in corpus_102_21.rules if not corpus_102_21.provenance_of(r.rule_id)]
    assert str(len(base)) in text, f"102.21 now has {len(base)} rules"


def test_every_module_listed_exists(corpus):
    """The 'What is here' table names files."""
    text = README.read_text(encoding="utf-8")
    for name in re.findall(r"`(\w+\.py)`", text):
        assert (ROOT / "src" / "originshift" / name).exists(), f"{name} is gone"


def test_the_scope_limit_is_stated_before_the_usage(corpus):
    """Part 102 is not the general origin test for US imports, and someone
    skimming must not miss that."""
    text = README.read_text(encoding="utf-8")
    assert "102.0" in text
    assert text.index("102.0") < text.index("## Resolving")


def test_the_corpus_round_trips_through_its_own_loader(corpus, corpus_102_21):
    """A field added to the grammar but not to the loader is silently dropped on
    load — it has happened twice (condition/sequence, then excluded_when), and
    both times the corpus on disk was right while the object in memory was not.
    """
    import json

    from originshift.corpus import CORPUS_DIR, Corpus

    for which in ("102.20", "102.21"):
        path = sorted(CORPUS_DIR.glob(f"{which}-*.json"))[-1]
        raw = json.loads(path.read_text(encoding="utf-8"))
        out = [r.to_dict() for r in Corpus.from_dict(raw).rules]
        assert out == raw["rules"], f"{which} loses fields on load"


def test_writable_paths_never_land_inside_an_installed_package():
    """Four modules anchored on Path(__file__).parents[2], which from a wheel
    resolves into the virtualenv's lib directory: the documented commands raised
    FileNotFoundError, and anything that wrote would have written into
    site-packages."""
    from originshift import paths

    for target in (paths.CACHE, paths.STAGING):
        assert paths.PACKAGE_DATA not in target.parents, target
        assert "site-packages" not in str(target)
    # read-only data ships with the package and is addressed inside it
    assert paths.VALIDATION.is_relative_to(paths.PACKAGE_DATA)


def test_the_rulings_guard_says_what_to_run():
    """Returning None for a missing index meant run(only=None), which scores
    every cached ruling — a checkout without the index printed different, wrong
    numbers with nothing to say they were wrong."""
    from originshift import validate

    assert issubclass(validate.RulingsNotFetched, FileNotFoundError)
    import inspect

    source = inspect.getsource(validate.ruling_set)
    assert "raise RulingsNotFetched" in source
    assert "--fetch" in source


def _table_rows(text: str, header_contains: str) -> list[list[str]]:
    """The cells of the markdown table whose header carries a phrase.

    Searching the whole document for a percentage has no teeth: a stale figure
    in one table passes because the right figure appears in another. The number
    has to be checked where it is claimed.
    """
    rows: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("|") and header_contains in line:
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
    return rows


def test_the_stated_corpus_figures_are_current(corpus, corpus_102_21):
    """Both figures, in the cells that claim them — not one relabelled as the
    other. The "answerable from codes alone" column reported `fully_structured`,
    a different and much larger number, in the document's first table."""
    import json

    from originshift.corpus import CORPUS_DIR

    text = README.read_text(encoding="utf-8")
    rows = _table_rows(text, "Decidable on codes alone")
    assert rows, "the corpus table is gone"

    for which in ("102.20", "102.21"):
        path = sorted(CORPUS_DIR.glob(f"{which}-*.json"))[-1]
        counts = json.loads(path.read_text(encoding="utf-8"))["counts"]
        total = counts["alternatives"]
        row = next(r for r in rows if which in r[0])
        assert f"{counts['fully_structured'] / total:.1%}" in row[-2], row
        assert f"{counts['decidable_from_codes'] / total:.1%}" in row[-1], row


def test_the_stated_validation_numbers_are_current(corpus):
    """Exact figures, not a loose band — three of them had drifted."""
    from originshift import parse_102_21, validate
    from originshift.corpus import Corpus

    if not validate.rulings_available("102.20"):
        pytest.skip("CROSS rulings not fetched; run validate --fetch")

    text = README.read_text(encoding="utf-8")
    report = validate.run(corpus, only=validate.ruling_set("102.20"))
    assert str(len(report.cases)) in text, f"quotations are now {len(report.cases)}"
    for era, (n, coverage, fidelity) in report.stratify().items():
        assert str(n) in text, f"{era} n is now {n}"
        assert f"{coverage:.1%}" in text, f"{era} coverage is now {coverage:.1%}"
        assert f"{fidelity:.1%}" in text, f"{era} fidelity is now {fidelity:.1%}"


def test_every_python_snippet_runs(corpus):
    """A reader works down the page, so the snippets are executed in order in
    one namespace — but each must supply the names it introduces."""
    import re

    text = README.read_text(encoding="utf-8")
    namespace: dict = {}
    ran = 0
    for n, block in enumerate(re.findall(r"```python\n(.*?)```", text, re.S), 1):
        code = "\n".join(
            line[4:]
            for line in block.splitlines()
            if line.startswith(">>> ") or line.startswith("... ")
        )
        if not code.strip():
            continue
        try:
            exec(compile(code, f"<README snippet {n}>", "exec"), namespace)
        except Exception as exc:  # noqa: BLE001 - the failure is the finding
            raise AssertionError(f"README snippet {n} does not run: {exc}") from exc
        ran += 1
    assert ran >= 5


def test_the_documented_snippet_outputs_are_what_they_print(corpus):
    """The flagship textile example printed a result the code did not produce."""
    from originshift import resolve
    from originshift.textile import TextileFacts

    r = resolve(
        good="6214.10",
        inputs=[],
        country="VN",
        textile=TextileFacts(
            excepted_fibre=False,
            dyed_and_printed_in="IT",
            finishing_operations=("bleaching", "napping"),
        ),
    )
    assert (r.origin, r.rule_id) == ("IT", "102.21(e)(2)(i)")
    assert "('IT', '102.21(e)(2)(i)')" in README.read_text(encoding="utf-8")


def test_the_user_agent_names_a_version_that_exists():
    """It said 0.0.1 and pointed at a URL that does not resolve — while
    pyproject deliberately omits that same URL for exactly that reason."""
    from originshift import sources

    assert "0.0.1" not in sources.USER_AGENT
    assert "http" not in sources.USER_AGENT


def test_the_package_declares_its_types():
    from originshift import paths

    assert (paths.PACKAGE_DATA.parent / "py.typed").exists()


def test_the_plan_and_the_readme_agree_on_the_version_scheme():
    """originshift.md promised a package version tied to nomenclature vintage.
    What was built puts the vintage on the data, which is the better place —
    the plan is amended to say so rather than left contradicting the code."""
    plan = (ROOT / "originshift.md").read_text(encoding="utf-8")
    assert "Version scheme — amended" in plan
    assert "originshift-2026.1" in plan  # the original promise is still shown
