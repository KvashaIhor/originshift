"""Build the versioned defined-term corpora, and the resolution graph over them.

Run as: python -m originshift.build_terms [--issue-date YYYY-MM-DD]

Same contract as the rule corpus: the artifact carries its own provenance, so a
consumer can depend on the corpus without depending on this code. What differs
is the unit. A rule corpus holds rules; this holds what a part defines, where it
uses what it defined, and where it uses a term it never defined.

Every record is checked against the source before it is written. That is not
ceremony — the parser in this module has three times produced a finding that was
an artifact of its own matching, and a term whose definition cannot be found in
the section it claims to come from is exactly what that looks like on disk.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from . import parse_134, parse_323, paths, sources, terms

OUT = paths.PACKAGE_DATA / "corpus" if paths._IN_CHECKOUT else paths.CORPUS_OUT

CORPORA = {
    "134": {
        "title": 19,
        "part": 134,
        "corpus": "19-CFR-134",
        "parser": parse_134,
        "authority": "19 CFR 134",
        "pinned_issue_date": "2026-08-26",
        "name": "Country of origin marking",
        "scope": (
            "Governs how an imported article must be marked with its country of "
            "origin under 19 U.S.C. 1304. It defines country of origin for its "
            "own purposes in § 134.1(b), and that definition turns on a term the "
            "part does not carry."
        ),
    },
    "323": {
        "title": 16,
        "part": 323,
        "corpus": "16-CFR-323",
        "parser": parse_323,
        "authority": "16 CFR 323",
        "pinned_issue_date": "2026-08-26",
        "name": "Made in USA labeling",
        "scope": (
            "Makes an unqualified Made in the United States claim an unfair or "
            "deceptive act unless a three-limb test in § 323.2 is met. The part "
            "states the test and defines none of the terms it turns on."
        ),
    },
}


def _self_check(secs, defined, used) -> dict:
    """Layer 1: every record must be findable in the source it names.

    Exhaustive, no oracle needed, and it proves nothing about accuracy — only
    that the corpus quotes the document it says it quotes. A definition that
    cannot be found in its own section means the parser invented it.
    """
    text_by_section = {s.section_id: s.text for s in secs}
    bad_definitions = [
        t.term
        for t in defined
        if t.definition[:60] not in text_by_section.get(t.defined_in, "")
    ]
    bad_quotes = [
        f"{u.term}@{u.used_in}"
        for u in used
        if u.quote[:60] not in text_by_section.get(u.used_in, "")
    ]
    return {
        "definitions_checked": len(defined),
        "definitions_not_found_in_source": bad_definitions,
        "quotes_checked": len(used),
        "quotes_not_found_in_source": bad_quotes,
        "passed": not bad_definitions and not bad_quotes,
    }


def build(which: str, issue_date: str | None = None) -> dict:
    """Compile one part. Defaults to the PINNED issue date, never to "latest".

    eCFR titles move independently — title 16 advanced to 2026-08-31 while title
    19 stayed at 2026-08-26 — so a build that defaults to latest silently mixes
    vintages and emits a graph whose filename names one issue date and whose
    contents name two. Pinning is what makes a rebuild reproduce the committed
    corpus; moving the pin is a deliberate edit.
    """
    spec = CORPORA[which]
    mod = spec["parser"]
    snap = sources.cfr_part(
        spec["title"], spec["part"], issue_date or spec["pinned_issue_date"]
    )

    secs = mod.sections(snap.text)
    defined = mod.defined_terms(snap.text)
    used = mod.uses(defined, secs)

    # Terms the part turns on and never defines are not discoverable by looking
    # for definitions, so each parser names its own and they are added as uses.
    extra: list[terms.Use] = []
    if which == "134":
        for row in mod.undefined_terms(
            snap.text, {"substantial transformation": "§ 134.1(b) turns on it"}
        ):
            extra += [
                terms.Use(term=row["term"], used_in=s["used_in"], quote=s["quote"])
                for s in row["used_at"]
            ]
    else:
        extra += mod.operative_uses(snap.text)

    # Third limb of the inclusion rule: terms the text itself marks by quoting
    # them. Without it the inventory is only what we went looking for, and
    # § 323.2's own resolution of "commerce" against the FTC Act had no edge —
    # so the graph reported cross_authority = 0 while the counterexample sat
    # inside the quoted span of every unsigned edge.
    already = {d.term.lower() for d in defined} | {u.term.lower() for u in extra}
    extra += [
        terms.Use(term=term, used_in=section, quote=quote,
                  in_definition=section == mod.defined_terms.__defaults__[0])
        for term, section, quote in terms.quoted_terms(secs, already)
    ]

    check = _self_check(secs, defined, used + extra)
    corpus = {
        "corpus": spec["corpus"],
        "regime": "US",
        "title": spec["name"],
        "authority": spec["authority"],
        "applies_to": spec["scope"],
        "licence": "US Government work, public domain (17 U.S.C. 105)",
        "unit": "defined terms and their use sites, not rules",
        "inclusion_rule": terms.INCLUSION_RULE,
        "vintage": f"eCFR-{snap.issue_date}",
        "source_url": snap.url,
        "source_issue_date": snap.issue_date,
        "built_on": datetime.now(timezone.utc).date().isoformat(),
        "counts": {
            "sections": len(secs),
            "defined_terms": len(defined),
            "use_sites": len(used) + len(extra),
            "use_sites_outside_definitions": sum(
                1 for u in used + extra if not u.in_definition
            ),
        },
        "self_check": check,
        "sections": [s.to_dict() for s in secs],
        "terms": [t.to_dict() for t in defined],
        "uses": [u.to_dict() for u in used + extra],
    }
    if which == "323":
        corpus["notes"] = [
            {
                "kind": "test_stated_terms_undefined",
                "detail": (
                    "§ 323.2 states the three-limb test and § 323.1 defines none "
                    "of the terms it turns on. The part does not cite the "
                    "Enforcement Policy Statement where 'all or virtually all' "
                    "acquires content."
                ),
                "content_lives_at": parse_323.POLICY_STATEMENT,
                "part_points_at_it": mod.points_at_the_policy_statement(snap.text),
            }
        ]
    return corpus


def _write_if_changed(path, corpus: dict) -> bool:
    """Write only when something other than the build date differs.

    `built_on` is the day the file was generated, so embedding it makes every
    rebuild dirty the tree with identical inputs. Comparing without it keeps the
    field honest and the tree byte-stable.
    """
    body = json.dumps(corpus, indent=1, ensure_ascii=False)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "built_on"} == {
            k: v for k, v in corpus.items() if k != "built_on"
        }:
            return False
    path.write_text(body, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--issue-date", help="eCFR issue date; defaults to each corpus's pinned date"
    )
    ap.add_argument(
        "--latest",
        action="store_true",
        help="take whatever issue eCFR currently serves, unpinning the corpus",
    )
    ap.add_argument("--corpus", choices=sorted(CORPORA), default=None)
    args = ap.parse_args()
    if args.latest and args.issue_date:
        raise SystemExit("--latest and --issue-date are mutually exclusive")

    built = []
    OUT.mkdir(parents=True, exist_ok=True)
    for which in [args.corpus] if args.corpus else sorted(CORPORA):
        wanted = args.issue_date
        if args.latest:
            wanted = sources.latest_issue_date(CORPORA[which]["title"])
        corpus = build(which, wanted)
        path = OUT / f"{which}-{corpus['source_issue_date']}.json"
        changed = _write_if_changed(path, corpus)
        built.append(corpus)
        c, chk = corpus["counts"], corpus["self_check"]
        print(f"{'wrote' if changed else 'unchanged'} {path.name}  "
              f"({path.stat().st_size / 1024:.0f} KB)")
        print(f"  source     : {corpus['source_url']}")
        print(f"  issue date : {corpus['source_issue_date']}")
        print(f"  sections {c['sections']}   defined terms {c['defined_terms']}   "
              f"use sites {c['use_sites']}")
        print(f"  self-check : {'PASS' if chk['passed'] else 'FAIL'}  "
              f"({chk['definitions_checked']} definitions, {chk['quotes_checked']} quotes)")
        if not chk["passed"]:
            raise SystemExit(
                f"self-check failed: {chk['definitions_not_found_in_source']} "
                f"{chk['quotes_not_found_in_source'][:5]}"
            )

    if len(built) > 1:
        graph = terms.build(built)
        path = OUT / f"terms-graph-{built[0]['source_issue_date']}.json"
        graph_doc = {
                    "built_from": [c["corpus"] for c in built],
                    "source_issue_dates": {
                        c["corpus"]: c["source_issue_date"] for c in built
                    },
                    "built_on": datetime.now(timezone.utc).date().isoformat(),
                    **graph,
        }
        changed = _write_if_changed(path, graph_doc)
        print(f"\n{'wrote' if changed else 'unchanged'} {path.name}")
        for res, n in graph["counts"].items():
            print(f"  {res:<16} {n}")


if __name__ == "__main__":
    main()
