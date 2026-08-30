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


# ---- textiles: the CLI could not supply a single fact 102.21 turns on --------


def test_apparel_resolves_through_the_cli(capsys):
    """The README leads with apparel, and for apparel the CLI could only ever
    return unresolved — there was no flag for fibre, knitting or assembly."""
    code, out = run(
        [
            "resolve", "--good", "6203.42", "--inputs", "5208.11", "--country", "VN",
            "--fibre", "cotton", "--component-parts", "yes", "--assembled-in", "VN",
        ],
        capsys,
    )
    assert code == 0
    assert "RESOLVED" in out.out
    assert "102.21(e)(1)/6201-6208" in out.out


def test_the_fibre_flag_chooses_between_the_two_tables(capsys):
    """"cotton" keeps a scarf of 6214 with (e)(1); anything else is (e)(2)'s."""
    _, cotton = run(
        ["resolve", "--good", "6214.20", "--inputs", "5208.11", "--country", "VN",
         "--fibre", "cotton", "--fabric-made-in", "IN"], capsys,
    )
    assert "102.21(e)(1)" in cotton.out

    _, silk = run(
        ["resolve", "--good", "6214.10", "--inputs", "5007.10", "--country", "VN",
         "--fibre", "other", "--dyed-printed-in", "IT",
         "--finishing", "bleaching,napping"], capsys,
    )
    assert "102.21(e)(2)(i)" in silk.out


def test_an_apparel_batch_resolves_and_says_what_is_missing(tmp_path, capsys):
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "examples" / "apparel.csv"
    if not example.exists():
        pytest.skip("example not present")
    out_path = tmp_path / "r.csv"
    code, _ = run(["resolve", "--csv", str(example), "--out", str(out_path)], capsys)
    assert code == 0

    rows = {r["id"]: r for r in csv.DictReader(out_path.open(encoding="utf-8"))}
    assert rows["A-2001"]["origin"] == "VN"   # wholly assembled
    assert rows["A-2002"]["origin"] == "BD"   # knit to shape
    assert rows["A-2003"]["origin"] == "IN"   # fabric-making
    # the row with no facts given must say which it needs, not fail silently
    assert rows["A-2005"]["status"] == "unresolved"
    assert "component parts" in rows["A-2005"]["needed"]


def test_the_needed_message_does_not_speak_python_at_a_cli_user(capsys):
    _, out = run(
        ["resolve", "--good", "6203.42", "--inputs", "5208.11", "--country", "VN"],
        capsys,
    )
    assert "TextileFacts" not in out.out


def test_bom_error_paths_report_rather_than_traceback(tmp_path, capsys):
    """A stack trace is not an error message. The CSV path already did this."""
    missing = run(["bom", str(tmp_path / "nope.json")], capsys)
    assert missing[0] == 1
    assert "no such file" in missing[1].err
    assert "Traceback" not in missing[1].err

    malformed = tmp_path / "bad.json"
    malformed.write_text('{"nogood": 1}', encoding="utf-8")
    bad = run(["bom", str(malformed)], capsys)
    assert bad[0] == 1
    assert "every node needs a 'good' field" in bad[1].err

    invalid = tmp_path / "broken.json"
    invalid.write_text("{", encoding="utf-8")
    broken = run(["bom", str(invalid)], capsys)
    assert broken[0] == 1
    assert "not valid JSON" in broken[1].err


def test_exit_codes_are_documented_and_distinguish_unresolved_from_error(capsys):
    """unresolved is an outcome, and the README says so at length. A script
    needs to be able to tell it from a failure."""
    from originshift import cli

    assert "0 resolved, 2 unresolved" in cli.__doc__

    resolved = run(
        ["resolve", "--good", "8708.29", "--inputs", "7208.10", "--country", "VN"], capsys
    )
    unresolved = run(
        ["resolve", "--good", "8708.29", "--inputs", "8708.95", "--country", "VN"], capsys
    )
    assert resolved[0] == 0
    assert unresolved[0] == 2       # not 1, which is reserved for real errors
