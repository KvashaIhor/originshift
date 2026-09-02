"""Ingestion: bringing in rules from sources that cannot be fetched and parsed."""

import json

import pytest

from originshift import ingest, parse_102_21

#: As the Federal Register prints a rule table: key padded with dots, the rule
#: wrapped across continuation lines.
FR_SAMPLE = b"""
                              * * * * * * *
6201-6208............................  (1) If the good consists of two
                                        or more component parts, a
                                        change to an assembled good of
                                        heading 6201 through 6208 from
                                        unassembled components.
                                       (2) If the good does not consist
                                        of two or more component parts,
                                        a change to heading 6201 through
                                        6208 from any heading outside
                                        that group, except from heading
                                        5007.

[[Page 68357]]
"""


@pytest.fixture
def document():
    return ingest.Document(
        content=FR_SAMPLE,
        provenance=ingest.Provenance(
            method="file",
            origin="87 FR 68356",
            retrieved="2026-08-29",
            sha256="0" * 64,
            extractor="fr_text",
        ),
    )


def test_a_fixed_width_table_survives_its_line_wrapping(document):
    (rule,) = ingest.extract_text(document)
    assert rule.htsus == "6201-6208"
    assert "wholly" not in rule.rule_text  # nothing invented
    assert "assembled good of heading 6201 through 6208" in rule.rule_text
    assert "[[Page" not in rule.rule_text


def test_page_furniture_is_not_read_as_rule_text(document):
    (rule,) = ingest.extract_text(document)
    assert "*" not in rule.rule_text
    assert "68357" not in rule.rule_text


def test_numbered_sub_rules_split_even_as_one_run_of_prose():
    """The eCFR puts each on its own line; the Federal Register does not."""
    text = (
        "(1) If the good consists of two or more component parts, a change to "
        "an assembled good of heading 6201 through 6208 from unassembled "
        "components. (2) If the good does not consist of two or more component "
        "parts, a change to heading 6201 through 6208 from any heading outside "
        "that group, except from heading 5007."
    )
    assert len(parse_102_21.split_alternatives(text)) == 2


def test_a_number_that_refers_to_a_sub_rule_does_not_start_one():
    """"cannot be determined under (1) above" is a reference, not a marker."""
    text = (
        "(2) If the country of origin cannot be determined under (1) above, a "
        "change to heading 5007 from any other heading."
    )
    assert len(parse_102_21.split_alternatives(text)) == 1


def test_extraction_writes_to_staging_and_never_to_a_corpus(document, tmp_path):
    rules = ingest.extract_text(document)
    path = ingest.stage(document, rules, "sample", staging_dir=tmp_path)
    assert path.suffix == ".csv"
    provenance = json.loads((tmp_path / "sample.provenance.json").read_text())
    assert provenance["sha256"] == "0" * 64
    assert provenance["reviewed_by"] is None  # not yet read by anyone


def test_an_unreviewed_document_is_not_trusted(document):
    assert not document.provenance.trusted
    document.provenance.reviewed_by = "someone"
    assert document.provenance.trusted


def test_an_api_source_is_trusted_without_review():
    p = ingest.Provenance(
        method="api",
        origin="https://www.ecfr.gov/...",
        retrieved="2026-08-29",
        sha256="a" * 64,
        extractor="ecfr_xml",
    )
    assert p.trusted


def test_compiling_records_who_reviewed_it(document, tmp_path):
    ingest.stage(document, ingest.extract_text(document), "sample", staging_dir=tmp_path)
    out = ingest.compile_staged(
        "sample",
        corpus="19-CFR-102.21",
        authority="102.21(e)(1)",
        reviewed_by="a person",
        staging_dir=tmp_path,
        overlay_dir=tmp_path,
    )
    data = json.loads(out.read_text())
    assert data["provenance"]["reviewed_by"] == "a person"
    assert data["provenance"]["origin"] == "87 FR 68356"
    (rule,) = data["rules"]
    assert rule["htsus"] == "6201-6208"
    assert len(rule["alternatives"]) == 2


def test_an_overlay_closes_the_gap_the_ecfr_left(corpus_102_21_base, corpus_102_21):
    """102.21(e)(1) has no rule for 6201-6208 — most apparel — because CBP Dec.
    22-25 was never incorporated. The text is in the Federal Register."""
    assert corpus_102_21_base.candidates("6203.42") == []
    assert corpus_102_21.candidates("6203.42") != []


def test_an_overlaid_rule_says_where_it_came_from(corpus_102_21):
    """An answer resting on a hand-fed document must be tellable from one
    resting on the eCFR."""
    provenance = corpus_102_21.provenance_of("102.21(e)(1)/6201-6208")
    assert provenance is not None
    assert "87 FR 68356" in provenance["origin"]
    assert provenance["reviewed_by"]
    # and a rule from the primary source carries no overlay record
    assert corpus_102_21.provenance_of("102.21(e)(1)/5007") is None
