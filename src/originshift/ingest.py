"""Bring in rules from sources that cannot be fetched and parsed.

Not every rule is reachable from an API. 19 CFR 102.21(e)(1) has no entry for
headings 6201 through 6208 — most apparel — because CBP Dec. 22-25 was never
incorporated into the CFR. The text exists, in the Federal Register, as prose in
a PDF. Other regimes are worse: the EU publishes Annex 22-01 as a document, and
the WCO's rules-of-origin database has no bulk export at all.

The rule this module keeps is that **a hand-fed rule must never be
indistinguishable from one derived from a verified source**. The corpus is worth
using because an answer can be traced back to the law, and an overlay that
quietly merged into it would spend that. So:

* Extraction never writes to the corpus. It writes a staging file for a person
  to read against the source document and correct.
* Every document is hashed, and every rule carries how it arrived, from where,
  and who reviewed it.
* Overlays are stored and loaded separately from the corpus they extend, and a
  consumer can always ask which rules did not come from the primary source.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from . import paths
from .grammar import CodeRange, Rule

STAGING = paths.STAGING
#: Compiled overlays go where the corpus loader looks for them.
OVERLAYS = paths.PACKAGE_DATA / "overlays"

Method = Literal["api", "file"]
Extractor = Literal[
    "ecfr_xml", "pdf_text", "fr_text", "html_table", "csv", "manual"
]


@dataclass
class Provenance:
    """Where a document came from and how its rules were got out of it."""

    method: Method
    #: A URL, or a citation where there is no URL: "87 FR 68356".
    origin: str
    retrieved: str
    #: SHA-256 of the document as received, so the extraction can be re-run
    #: against the same bytes and shown to be the same bytes.
    sha256: str
    extractor: Extractor
    #: Who read the extraction against the source. Unreviewed overlays stay
    #: unreviewed in the record rather than being assumed correct.
    reviewed_by: str | None = None
    note: str | None = None

    @property
    def trusted(self) -> bool:
        return self.method == "api" or self.reviewed_by is not None


@dataclass
class Document:
    """Bytes plus the account of where they came from."""

    content: bytes
    provenance: Provenance

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        origin: str,
        extractor: Extractor,
        note: str | None = None,
    ) -> Document:
        raw = Path(path).read_bytes()
        return cls(
            content=raw,
            provenance=Provenance(
                method="file",
                origin=origin,
                retrieved=date.today().isoformat(),
                sha256=hashlib.sha256(raw).hexdigest(),
                extractor=extractor,
                note=note or f"read from {Path(path).name}",
            ),
        )


# --------------------------------------------------------------------------
# Extraction — into staging, never into a corpus
# --------------------------------------------------------------------------


@dataclass
class StagedRule:
    """One candidate rule, awaiting a person's eyes."""

    htsus: str
    rule_text: str
    page: int | None = None
    note: str = ""


def extract_pdf(doc: Document) -> list[StagedRule]:
    """Pull candidate rules out of a PDF.

    Best effort only. PDF text carries no structure, so this finds lines that
    look like a code followed by rule language and leaves the judgement to the
    reviewer.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency is optional
        raise RuntimeError("extracting from PDF needs pdfplumber installed") from exc

    import io

    key = re.compile(r"^\s*(?P<key>\d{4}(?:\.\d{2,4}){0,2}(?:\s*[-–]\s*\d{4}(?:\.\d{2,4}){0,2})?)\s+(?P<rest>\S.*)$")
    staged: list[StagedRule] = []
    with pdfplumber.open(io.BytesIO(doc.content)) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [c.strip() for c in row if c and c.strip()]
                    if len(cells) >= 2 and re.match(r"^\d{4}", cells[0]):
                        staged.append(
                            StagedRule(cells[0], " ".join(cells[1:]), page=number)
                        )
            if staged:
                continue
            for line in (page.extract_text() or "").splitlines():
                m = key.match(line)
                if m and re.search(r"change|origin", m.group("rest"), re.I):
                    staged.append(
                        StagedRule(m.group("key"), m.group("rest"), page=number)
                    )
    return staged


#: The Federal Register prints rule tables in fixed-width columns, the key
#: padded out with dots and the rule wrapped over continuation lines:
#:
#:     6201-6208............................  (1) If the good consists of two
#:                                             or more component parts, a
_FR_ROW = re.compile(
    r"^(?P<key>\d{4}(?:\.\d{2,4}){0,2}(?:\s*[-–]\s*\d{4}(?:\.\d{2,4}){0,2})?)\.{2,}\s*(?P<rest>\S.*)$"
)
_FR_CONTINUATION = re.compile(r"^\s{20,}(?P<rest>\S.*)$")


def extract_text(doc: Document) -> list[StagedRule]:
    """Pull rule rows out of a fixed-width text table, as the FR prints them."""
    staged: list[StagedRule] = []
    for line in doc.content.decode("utf-8", "replace").splitlines():
        if line.strip().startswith("[[Page") or set(line.strip()) <= {"*", " "}:
            continue
        m = _FR_ROW.match(line)
        if m:
            staged.append(StagedRule(m.group("key"), m.group("rest").strip()))
            continue
        m = _FR_CONTINUATION.match(line)
        if m and staged:
            staged[-1].rule_text += " " + m.group("rest").strip()
    for rule in staged:
        rule.rule_text = re.sub(r"\s+", " ", rule.rule_text).strip()
    return staged


def extract_html(doc: Document) -> list[StagedRule]:
    """Pull two-column rule tables out of an HTML document."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(doc.content, "html.parser")
    staged: list[StagedRule] = []
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) >= 2 and re.match(r"^\d{4}", cells[0]):
            staged.append(StagedRule(cells[0], " ".join(cells[1:])))
    return staged


def stage(
    doc: Document, rules: list[StagedRule], name: str, *, staging_dir: Path | None = None
) -> Path:
    """Write candidate rules out for review, with the document's provenance."""
    staging_dir = staging_dir or STAGING
    staging_dir.mkdir(parents=True, exist_ok=True)
    path = staging_dir / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["htsus", "rule_text", "page", "note"])
        writer.writeheader()
        for rule in rules:
            writer.writerow(asdict(rule))
    (staging_dir / f"{name}.provenance.json").write_text(
        json.dumps(asdict(doc.provenance), indent=1), encoding="utf-8"
    )
    return path


# --------------------------------------------------------------------------
# Compilation — reviewed staging into an overlay
# --------------------------------------------------------------------------


def compile_staged(
    name: str,
    *,
    corpus: str,
    authority: str,
    reviewed_by: str,
    parser: str = "102.21",
    staging_dir: Path | None = None,
    overlay_dir: Path | None = None,
) -> Path:
    """Compile a reviewed staging file into an overlay.

    `reviewed_by` is required and recorded. An overlay that no one has read
    against the source is not something this will produce silently.
    """
    from . import parse_102, parse_102_21

    staging_dir = staging_dir or STAGING
    overlay_dir = overlay_dir or OVERLAYS
    grammar = {"102.20": parse_102, "102.21": parse_102_21}[parser]

    provenance = Provenance(
        **json.loads(
            (staging_dir / f"{name}.provenance.json").read_text(encoding="utf-8")
        )
    )
    provenance.reviewed_by = reviewed_by

    rules: list[Rule] = []
    with (staging_dir / f"{name}.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = row["htsus"].strip()
            if not key or not row["rule_text"].strip():
                continue
            parts = re.split(r"\s*[-–]\s*", key)
            try:
                scope = [
                    CodeRange.parse(parts[0], parts[1] if len(parts) > 1 else None)
                ]
            except (ValueError, IndexError):
                scope = []
            splitter = getattr(grammar, "split_alternatives", None)
            pieces = (
                splitter(row["rule_text"])
                if splitter
                else [p for p in row["rule_text"].split("; or") if p.strip()]
            )
            alternatives = [
                grammar.parse_alternative(piece.strip(), scope) for piece in pieces
            ]
            rules.append(
                Rule(
                    rule_id=f"{authority}/{key}",
                    regime="US",
                    htsus=key,
                    scope=scope,
                    alternatives=alternatives,
                    section=f"{authority} (overlay)",
                    text=row["rule_text"].strip(),
                    vintage="HTSUS-2026",
                    source_url=provenance.origin,
                )
            )

    overlay_dir.mkdir(parents=True, exist_ok=True)
    path = overlay_dir / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "overlay": name,
                "extends": corpus,
                "authority": authority,
                "provenance": asdict(provenance),
                "rules": [r.to_dict() for r in rules],
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    ex = sub.add_parser("extract", help="pull candidate rules into staging for review")
    ex.add_argument("file")
    ex.add_argument("--origin", required=True, help='URL, or a citation: "87 FR 68356"')
    ex.add_argument("--name", required=True, help="name for the staging file")

    co = sub.add_parser("compile", help="turn a reviewed staging file into an overlay")
    co.add_argument("name")
    co.add_argument("--corpus", default="19-CFR-102.21")
    co.add_argument("--authority", default="102.21(e)(1)")
    co.add_argument("--parser", default="102.21", choices=["102.20", "102.21"])
    co.add_argument("--reviewed-by", required=True, help="who checked it")

    args = ap.parse_args()
    if args.command == "extract":
        suffix = Path(args.file).suffix.lower()
        extractor: Extractor = {
            ".pdf": "pdf_text",
            ".txt": "fr_text",
            ".html": "html_table",
            ".htm": "html_table",
        }.get(suffix, "html_table")
        doc = Document.from_file(args.file, origin=args.origin, extractor=extractor)
        rules = {
            "pdf_text": extract_pdf,
            "fr_text": extract_text,
            "html_table": extract_html,
        }[extractor](doc)
        path = stage(doc, rules, args.name)
        print(f"staged {len(rules)} candidate rules -> {path}")
        print(f"  sha256 {doc.provenance.sha256[:16]}…  from {args.origin}")
        print("  Read these against the source and correct them, then:")
        print(f"  python -m originshift.ingest compile {args.name} --reviewed-by '<you>'")
    else:
        path = compile_staged(
            args.name,
            corpus=args.corpus,
            authority=args.authority,
            reviewed_by=args.reviewed_by,
            parser=args.parser,
        )
        print(f"wrote overlay -> {path}")


if __name__ == "__main__":
    main()
