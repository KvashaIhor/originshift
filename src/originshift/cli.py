"""Command line, for people who work in spreadsheets rather than Python.

    originshift resolve --good 8708.29 --inputs 7208.10,8708.99 --country VN
    originshift resolve --csv entries.csv --out results.csv
    originshift bom assembly.json
    originshift rule 6203.42 --corpus 102.21

The batch path is the one that matters. The question an adopter actually has is
"what does this say about last quarter's entries", not "what about this one
good", so `--csv` reads a file of entries and writes a file of determinations
with the rule cited on every row.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .corpus import Corpus
from .resolve import Material, OriginResult, resolve

#: Columns a batch file may carry. Only `good` and `country` are required.
INPUT_COLUMNS = (
    "id",
    "good",
    "country",
    "materials",
    "material_countries",
    "material_values",
    "good_value",
    "wholly_obtained",
    "is_set",
    "operation",
    "corpus",
)

OUTPUT_COLUMNS = (
    "id",
    "good",
    "country",
    "status",
    "origin",
    "basis",
    "rule_id",
    "reason",
    "needed",
    "rule_text",
    "vintage",
    "source",
)


def _split(value: str | None) -> list[str]:
    return [p.strip() for p in (value or "").replace(";", ",").split(",") if p.strip()]


def _flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _materials(row: dict) -> list[Material]:
    codes = _split(row.get("materials"))
    countries = _split(row.get("material_countries"))
    values = _split(row.get("material_values"))
    out: list[Material] = []
    for i, code in enumerate(codes):
        out.append(
            Material(
                code=code,
                country=countries[i] if i < len(countries) else None,
                value=float(values[i]) if i < len(values) and values[i] else None,
            )
        )
    return out


def _corpora(names: list[str]) -> dict[str, Corpus]:
    return {name: Corpus.load(which=name) for name in names}


def _row_out(row: dict, result: OriginResult, corpus: Corpus) -> dict:
    return {
        "id": row.get("id", ""),
        "good": row.get("good", ""),
        "country": row.get("country", ""),
        "status": result.status,
        "origin": result.origin or "",
        "basis": result.basis or "",
        "rule_id": result.rule_id or "",
        "reason": result.reason or "",
        "needed": result.needed or "",
        "rule_text": result.rule_text or "",
        "vintage": result.vintage or "",
        # An answer resting on a hand-fed document must be tellable from one
        # resting on the eCFR, in the output file as much as in the API.
        "source": (
            (corpus.provenance_of(result.rule_id) or {}).get("origin", "eCFR")
            if result.rule_id
            else ""
        ),
    }


def _resolve_row(row: dict, corpora: dict[str, Corpus]) -> tuple[OriginResult, Corpus]:
    which = (row.get("corpus") or "").strip() or None
    corpus = corpora[which] if which in corpora else None
    if corpus is None:
        # No corpus named: try each, and prefer one that finds a rule at all.
        for candidate in corpora.values():
            if candidate.candidates(row["good"]):
                corpus = candidate
                break
        corpus = corpus or next(iter(corpora.values()))
    result = resolve(
        good=row["good"].strip(),
        inputs=_materials(row),
        country=(row.get("country") or "").strip(),
        good_value=float(row["good_value"]) if row.get("good_value") else None,
        wholly_obtained=_flag(row.get("wholly_obtained")),
        is_set=_flag(row.get("is_set")),
        operation=(row.get("operation") or "").strip() or None,
        corpus=corpus,
    )
    return result, corpus


def cmd_resolve(args: argparse.Namespace) -> int:
    corpora = _corpora(["102.20", "102.21"])

    if args.csv:
        rows = list(csv.DictReader(Path(args.csv).open(encoding="utf-8-sig")))
        if not rows:
            print(f"{args.csv} has no rows", file=sys.stderr)
            return 1
        missing = {"good"} - set(rows[0])
        if missing:
            print(
                f"{args.csv} needs a 'good' column; found {list(rows[0])}",
                file=sys.stderr,
            )
            return 1

        out_path = Path(args.out) if args.out else None
        handle = out_path.open("w", newline="", encoding="utf-8") if out_path else sys.stdout
        try:
            writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_COLUMNS))
            writer.writeheader()
            tally: dict[str, int] = {}
            for row in rows:
                if not (row.get("good") or "").strip():
                    continue
                result, corpus = _resolve_row(row, corpora)
                writer.writerow(_row_out(row, result, corpus))
                tally[result.status] = tally.get(result.status, 0) + 1
        finally:
            if out_path:
                handle.close()

        if out_path:
            print(f"wrote {out_path}  ({sum(tally.values())} entries)", file=sys.stderr)
        for status in ("resolved", "unresolved", "ambiguous"):
            if tally.get(status):
                print(f"  {tally[status]:>6}  {status}", file=sys.stderr)
        if tally.get("unresolved"):
            print(
                "\n  unresolved is not an error: the rules do not decide it on what\n"
                "  was given. The 'needed' column says what to supply.",
                file=sys.stderr,
            )
        return 0

    if not args.good:
        print("give --good, or --csv for a batch", file=sys.stderr)
        return 1

    row = {
        "good": args.good,
        "country": args.country or "",
        "materials": ",".join(args.inputs or []),
        "material_countries": ",".join(args.material_countries or []),
        "material_values": ",".join(args.material_values or []),
        "good_value": args.good_value or "",
        "wholly_obtained": str(args.wholly_obtained),
        "is_set": str(args.is_set),
        "operation": args.operation or "",
        "corpus": args.corpus or "",
    }
    result, corpus = _resolve_row(row, corpora)
    _print(result, corpus, args.good)
    return 0 if result.status == "resolved" else 2


def _print(result: OriginResult, corpus: Corpus, good: str) -> None:
    print(f"{good}  →  {result.status.upper()}")
    if result.origin:
        print(f"  origin    {result.origin}   ({result.basis})")
    if result.rule_id:
        origin = (corpus.provenance_of(result.rule_id) or {}).get("origin", "eCFR")
        print(f"  rule      {result.rule_id}   [{origin}]")
    if result.rule_text:
        print(f"  text      {result.rule_text}")
    if result.reason:
        print(f"  reason    {result.reason}")
    if result.needed:
        print(f"  needed    {result.needed}")
    for finding in result.trace:
        for check in finding.checks:
            print(f"    · {check.material}: {check.outcome} — {check.detail}")
        if finding.checks:
            break
    print(f"  vintage   {result.vintage}")


def cmd_bom(args: argparse.Namespace) -> int:
    """Walk a bill of materials, determining origin at each node."""
    import json

    from .bom import Node, render, resolve_bom

    tree = Node.from_dict(json.loads(Path(args.file).read_text(encoding="utf-8")))
    corpus = Corpus.load(which=args.corpus) if args.corpus else None
    root = resolve_bom(tree, corpus=corpus)

    if args.json:
        def pack(node):
            return {
                "good": node.good,
                "label": node.label,
                "origin": node.origin,
                "stated": node.stated,
                "status": node.result.status if node.result else "given",
                "basis": node.result.basis if node.result else None,
                "rule_id": node.result.rule_id if node.result else None,
                "rule_text": node.result.rule_text if node.result else None,
                "needed": node.result.needed if node.result else None,
                "blocked_by": node.blocked_by,
                "components": [pack(c) for c in node.children],
            }

        print(json.dumps(pack(root), indent=1))
    else:
        print(render(root))
        print()
        settled = sum(1 for n in root.walk() if n.determined)
        total = sum(1 for _ in root.walk())
        print(f"{settled}/{total} nodes settled", file=sys.stderr)
        if not root.determined:
            print(
                "  The finished good is unresolved: the rules do not decide it"
                " on what the BOM gives. Each node above says what it needs.",
                file=sys.stderr,
            )
    return 0 if root.determined else 2


def cmd_rule(args: argparse.Namespace) -> int:
    corpus = Corpus.load(which=args.corpus)
    found = corpus.candidates(args.code)
    if not found:
        print(f"no rule in {args.corpus} covers {args.code}", file=sys.stderr)
        return 1
    for rule, alt in found:
        origin = (corpus.provenance_of(rule.rule_id) or {}).get("origin", "eCFR")
        print(f"{rule.rule_id}   [{origin}]")
        if alt.condition:
            print(f"  applies if: {alt.condition}")
        print(f"  {alt.text}")
        if not alt.structured:
            print(f"  (not decidable from codes alone: {alt.unparsed_reason})")
        print()
    return 0


def cmd_corpora(args: argparse.Namespace) -> int:
    for name in ("102.20", "102.21"):
        try:
            corpus = Corpus.load(which=name)
        except FileNotFoundError:
            print(f"{name}: not built")
            continue
        alts = [a for r in corpus.rules for a in r.alternatives]
        decidable = sum(a.structured for a in alts)
        print(f"{corpus.name}")
        print(f"  rules        {len(corpus.rules)}   alternatives {len(alts)}")
        print(f"  from codes   {decidable} ({decidable / len(alts):.1%})")
        print(f"  vintage      {corpus.vintage}   issued {corpus.source_issue_date}")
        if corpus.overlaid:
            print(f"  overlaid     {len(corpus.overlaid)} rule(s) not from the eCFR:")
            for rule_id, prov in corpus.overlaid.items():
                print(f"     {rule_id}  ←  {prov['origin']}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="originshift", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    r = sub.add_parser("resolve", help="determine origin for one good or a CSV of them")
    r.add_argument("--good", help="HS code of the finished article")
    r.add_argument("--inputs", type=lambda v: _split(v), help="material HS codes")
    r.add_argument("--country", help="where the operation happened")
    r.add_argument("--material-countries", type=lambda v: _split(v))
    r.add_argument("--material-values", type=lambda v: _split(v))
    r.add_argument("--good-value")
    r.add_argument("--wholly-obtained", action="store_true")
    r.add_argument("--is-set", action="store_true")
    r.add_argument("--operation", help="a 102.17 operation, e.g. simple_packing")
    r.add_argument("--corpus", choices=["102.20", "102.21"])
    r.add_argument("--csv", help="a file of entries; needs a 'good' column")
    r.add_argument("--out", help="write results here instead of stdout")
    r.set_defaults(func=cmd_resolve)

    b = sub.add_parser(
        "bom",
        help="walk a bill of materials, citing the rule at each node",
        description=(
            "Produces a determination, not a certificate of origin, and does no "
            "preferential or FTA qualification. Nothing is stored between calls."
        ),
    )
    b.add_argument("file", help="a JSON bill of materials")
    b.add_argument("--corpus", choices=["102.20", "102.21"])
    b.add_argument("--json", action="store_true", help="machine-readable output")
    b.set_defaults(func=cmd_bom)

    q = sub.add_parser("rule", help="show the rule covering a code")
    q.add_argument("code")
    q.add_argument("--corpus", default="102.20", choices=["102.20", "102.21"])
    q.set_defaults(func=cmd_rule)

    c = sub.add_parser("corpora", help="what is built, and where it came from")
    c.set_defaults(func=cmd_corpora)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
