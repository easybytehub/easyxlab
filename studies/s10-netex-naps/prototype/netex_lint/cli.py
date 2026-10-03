"""netex-lint command line.

    python -m netex_lint FILE [FILE ...] [--xsd PATH.xsd] [--profile auto|fr|nordic|epip|nl|none]
                         [--today YYYY-MM-DD] [--json]

FILE may be a .zip of NeTEx documents, a .xml.gz or a plain .xml. All documents of one FILE
are treated as one dataset (references are resolved across them).
Exit status: 0 = no error-level finding, 1 = at least one error, 2 = usage problem.
"""
import argparse, datetime, json, sys
from collections import Counter
from .core import iter_members, scan_member, check_dataset, load_schema, xsd_validate


def lint(path, today, profile="auto", schema=None):
    members = list(iter_members(path))
    scans = [scan_member(n, o) for n, _, o in members]
    summary, findings = check_dataset(scans, today, profile)
    if schema is not None:
        cats, msgs, bad, total = Counter(), Counter(), 0, 0
        for name, _, opener in members:
            try:
                ok, c, m, n = xsd_validate(opener, schema)
            except Exception as e:
                ok, c, m, n = False, Counter({"not-well-formed": 1}), Counter({str(e)[:200]: 1}), 1
            bad += not ok; cats.update(c); msgs.update(m); total += n
        if bad:
            findings.append({"rule": "XSD-INVALID", "severity": "error", "count": total,
                             "message": f"{bad} of {len(members)} documents fail the XSD; {total} errors; categories "
                                        f"of the first 20,000 per document: {dict(cats)}",
                             "source": "open NeTEx XSD (GPL-3.0) or archived EPIP XSD",
                             "examples": [k for k, _ in msgs.most_common(5)]})
    return {"file": path, "summary": summary, "findings": findings}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="netex-lint", description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--xsd", help="path to NeTEx_publication.xsd (open NeTEx XSD) or an EPIP XSD")
    ap.add_argument("--profile", default="auto", choices=["auto", "fr", "nordic", "epip", "nl", "none"])
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    schema = load_schema(a.xsd) if a.xsd else None
    worst = 0
    for f in a.files:
        r = lint(f, a.today, a.profile, schema)
        worst = max(worst, 1 if any(x["severity"] == "error" for x in r["findings"]) else 0)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
            continue
        s = r["summary"]
        print(f"{f}: profile={s['profile']} documents={s['members']} ids={s['ids']} refs={s['refs']} "
              f"validity_to={s['validity_to_max']} calendar_max={s['calendar_max']}")
        for x in r["findings"]:
            print(f"  {x['severity'].upper():7} {x['rule']} x{x['count']}: {x['message']}")
            for e in x["examples"][:3]:
                print(f"           e.g. {e}")
        if not r["findings"]:
            print("  no findings")
    return worst


if __name__ == "__main__":
    sys.exit(main())
