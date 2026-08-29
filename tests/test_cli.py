"""The command line, which is how a compliance analyst reaches this."""

import csv

import pytest

from originshift import cli


def run(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr()


def test_one_good_resolves_and_cites_its_rule(capsys):
    code, out = run(
        ["resolve", "--good", "8708.29", "--inputs", "7208.10,8708.99", "--country", "VN"],
        capsys,
    )
    assert code == 0
    assert "RESOLVED" in out.out
    assert "102.20/8708.29" in out.out
    assert "A change to subheading 8708.29" in out.out


def test_an_unresolved_good_exits_nonzero_but_says_what_is_missing(capsys):
    code, out = run(
        ["resolve", "--good", "2008.11", "--inputs", "1202.41", "--country", "CN"],
        capsys,
    )
    assert code == 2  # distinguishable from an error, which is 1
    assert "UNRESOLVED" in out.out
    assert "mere blanching of peanuts" in out.out


def test_a_batch_writes_one_determination_per_entry(tmp_path, capsys):
    src = tmp_path / "entries.csv"
    src.write_text(
        "id,good,country,materials\n"
        "A,8708.29,VN,7208.10\n"
        "B,8708.29,VN,8708.95\n"
        "C,2008.11,CN,1202.41\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "results.csv"
    code, _ = run(["resolve", "--csv", str(src), "--out", str(out_path)], capsys)
    assert code == 0

    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert [r["id"] for r in rows] == ["A", "B", "C"]
    assert list(rows[0]) == list(cli.OUTPUT_COLUMNS)
    assert rows[0]["status"] == "resolved"
    assert rows[0]["rule_id"] == "102.20/8708.29"
    assert rows[2]["needed"]  # every unresolved row says what is missing


def test_every_output_row_carries_the_rule_and_where_it_came_from(tmp_path, capsys):
    """A determination a broker cannot trace is not worth filing."""
    src = tmp_path / "e.csv"
    src.write_text("good,country,materials\n8708.29,VN,7208.10\n", encoding="utf-8")
    out_path = tmp_path / "r.csv"
    run(["resolve", "--csv", str(src), "--out", str(out_path)], capsys)
    (row,) = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert row["rule_text"].startswith("A change to subheading 8708.29")
    assert row["source"] == "eCFR"
    assert row["vintage"] == "HTSUS-2026"


def test_a_batch_picks_the_corpus_that_has_a_rule(tmp_path, capsys):
    """An analyst should not have to know which part governs their good."""
    src = tmp_path / "e.csv"
    src.write_text(
        "id,good,country,materials\n"
        "textile,6203.42,VN,5208.11\n"
        "auto,8708.29,VN,7208.10\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "r.csv"
    run(["resolve", "--csv", str(src), "--out", str(out_path)], capsys)
    rows = {r["id"]: r for r in csv.DictReader(out_path.open(encoding="utf-8"))}
    assert rows["textile"]["rule_id"].startswith("102.21")
    assert rows["auto"]["rule_id"].startswith("102.20")


def test_an_overlaid_rule_is_marked_as_such_in_the_output(tmp_path, capsys):
    """The 6201-6208 rule is not in the eCFR, and a results file must say so."""
    src = tmp_path / "e.csv"
    src.write_text("good,country,materials\n6203.42,VN,5208.11\n", encoding="utf-8")
    out_path = tmp_path / "r.csv"
    run(["resolve", "--csv", str(src), "--out", str(out_path)], capsys)
    (row,) = list(csv.DictReader(out_path.open(encoding="utf-8")))
    assert "87 FR 68356" in row["source"]


def test_a_batch_reports_that_unresolved_is_not_an_error(tmp_path, capsys):
    src = tmp_path / "e.csv"
    src.write_text("good,country,materials\n2008.11,CN,1202.41\n", encoding="utf-8")
    code, out = run(["resolve", "--csv", str(src), "--out", str(tmp_path / "r.csv")], capsys)
    assert code == 0  # a batch with unresolved rows is a successful run
    assert "unresolved is not an error" in out.err


def test_a_file_without_a_good_column_is_refused(tmp_path, capsys):
    src = tmp_path / "e.csv"
    src.write_text("sku,country\nX,VN\n", encoding="utf-8")
    code, out = run(["resolve", "--csv", str(src)], capsys)
    assert code == 1
    assert "needs a 'good' column" in out.err


def test_the_shipped_example_runs(tmp_path, capsys):
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "examples" / "entries.csv"
    if not example.exists():
        pytest.skip("example not present")
    code, _ = run(["resolve", "--csv", str(example), "--out", str(tmp_path / "r.csv")], capsys)
    assert code == 0
    rows = list(csv.DictReader((tmp_path / "r.csv").open(encoding="utf-8")))
    assert len(rows) == 6
    assert {r["status"] for r in rows} <= {"resolved", "unresolved", "ambiguous"}


def test_rule_lookup_shows_provenance(capsys):
    code, out = run(["rule", "6203.42", "--corpus", "102.21"], capsys)
    assert code == 0
    assert "87 FR 68356" in out.out


def test_corpora_lists_what_is_built_and_what_was_overlaid(capsys):
    code, out = run(["corpora"], capsys)
    assert code == 0
    assert "19-CFR-102.20" in out.out and "19-CFR-102.21" in out.out
    assert "102.21(e)(1)/6201-6208" in out.out
