#!/usr/bin/env python3
"""S23: assert every headline number of README.md (and of paper.md, when present) against data/.

The expected strings are computed here from the published CSVs and data/summary.json. Each
must occur in the documents (whitespace, including line breaks, is collapsed first).
paper.md is optional: when it is absent only README.md is checked. Exit 1 on any mismatch."""
import csv, json, re, sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
D = R / "data"
PAPER_URL = "https://easybyte.es/lab/studies/s23/paper/"


def rows(name):
    return list(csv.DictReader(open(D / name, encoding="utf-8")))


def flat(s):
    return re.sub(r"\s+", " ", s)


docs = {"README.md": flat((R / "README.md").read_text(encoding="utf-8"))}
if (R / "paper.md").exists():
    docs["paper.md"] = flat((R / "paper.md").read_text(encoding="utf-8"))
else:
    print(f"paper.md is not in the public package: the paper is at {PAPER_URL}")
bad = []
# The study's row in the repository's README (the headline the site shows), when the study sits in it.
ROOT = R.parent.parent / "README.md"
if ROOT.exists():
    row = [ln for ln in ROOT.read_text(encoding="utf-8").splitlines() if ln.startswith("| [S23](")]
    if len(row) != 1:
        bad.append(f"repository README: {len(row)} rows for S23")
    else:
        docs["root row"] = flat(row[0])
else:
    print("not inside the studies repository: the root-table row is not checked")
ROW = ("root row",)


def need(label, text, where=("README.md", "paper.md")):
    print(f"{label}: {text}")
    for w in where:
        if w in docs and text not in docs[w]:
            bad.append(f"{w} does not contain «{text}» ({label})")


def n(x):
    return f"{x:,}"


S = json.load(open(D / "summary.json", encoding="utf-8"))
F, E = rows("figures.csv"), rows("eu_averages.csv")
fid = {r["id"]: r for r in F}
eid = {r["id"]: r for r in E}

# 1. the corpus
need("Spain figure rows", f"{len(F)} figures for Spain")
need("comparison rows", f"{len(E)} comparison figures")
# a comparison row is an average when its scope names the EU, Europe or the OECD; otherwise it is
# a share for named countries (EU-13, EU-14). Two averages sit in documents with no Spain row.
avg = [r for r in E if re.search(r"\bEU\b|OECD|europe", r["scope"], re.I)]
need("average rows", f"{len(avg)} averages for the EU or Europe")
need("named-country rows", f"{len(E) - len(avg)} shares for named countries")
alone = [r["id"] for r in E if r["url"] not in {f["url"] for f in F}]
need("averages without a Spain figure", "Two of the averages come from EU housing texts in which we found no figure for Spain's public housing stock",
     where=("paper.md",))
assert len(alone) == 2 and all(r["id"] in {a["id"] for a in avg} for r in E if r["id"] in alone), alone
assert len(F) == S["n_spain_rows"] and len(E) == S["n_eu_rows"]
assert len(avg) == S["n_eu_rows_averages"] and len(E) - len(avg) == S["n_eu_rows_named_countries"]
assert len(alone) == S["n_eu_rows_no_spain_figure"]
need("quotations verified", f"{S['n_quotes_verified']} quotations")
need("documents", f"{S['n_documents']} documents")
st = S["reconciliation_status"]
need("differences explained", f"{st['explained']} are explained")
need("differences partly explained", f"{st['partly explained']} partly")
need("errors in a source", f"{st['error in a source']} are errors in a")
need("differences not explained", f"{st['not explained']} are not explained")
assert sum(st.values()) == S["n_reconciliation_rows"]
assert S["n_quotes_verified"] == len(F) + len(E)

# 2. the two survey counts and their shares (from the figures table)
assert fid["ES-03"]["value"] == "290,000" and fid["ES-06"]["value"] == "318,000"
need("2019 count", "290,000")
need("2023 count", "318,000")
assert fid["ES-02"]["value"] == "1.6" and fid["ES-09"]["value"] == "318,000"
need("share of households, 2019", "1.6%")
need("share of households, 2023 (plan)", "1.7%")
need("OECD share of all dwellings", f"{S['oecd_spain_pct']}%", ("paper.md",))
need("318,000 over all dwellings 2024", f"{S['share_318k_total_2024']}%")
need("ECV below-market rent 2025", f"{S['ecv_below_market']['2025']}%")
need("root row: the 2023 survey count", f"Spain's regions and municipalities let {fid['ES-06']['value']} dwellings in the Ministry's 2023 survey, {S['share_318k_census_households']:.1f}% of households", ROW)
ecv = S["ecv_below_market"]
lo, hi = ecv["2016"], ecv["2025"]  # 2.5% (every year 2012-2016) and 3.5% (2025), the ends of the quoted shares
assert all(ecv[y] == lo for y in ("2012", "2013", "2014", "2015")) and min(ecv.values()) == lo and max(ecv.values()) == hi
need("root row: the quoted shares", f"Official texts' {lo}–{hi}% shares equal the share of households renting below market price, whoever the landlord", ROW)
need("root row: the State's own stock", "no legally required inventory of the State's own stock was found by any route open to us", ROW)
need("abstract: the search for it", "We found no such report or inventory by any route open to us", ("README.md",))
need("ECV below-market rent 2023", f"{S['ecv_below_market']['2023']}%")
need("EU-SILC Spain reduced or free 2025", f"{S['silc_es_rent_fr']['2025']}%", ("paper.md",))
need("EU-SILC EU-27 reduced or free 2025", f"{S['silc_eu_rent_fr']['2025']}%", ("paper.md",))
need("ECV 2.5 years", f"{S['ecv_25_years'][0]}–{S['ecv_25_years'][-1]}")
assert S["ecv_below_market"]["2024"] == 3.4 and fid["ES-23"]["value"] == "2.5-3.4"

# 3. EU averages
need("OVS 2020 EU-28", f"{S['ovs2020_eu28_pct']}%")
need("OVS 2024 EU-27", f"{S['ovs2024_eu27_pct']}%")
need("OVS 2020 without UK", f"{S['ovs2020_eu_without_uk_pct']}%", ("paper.md",))
need("OECD EU unweighted", f"{S['oecd_eu_unweighted']}", ("paper.md",))
need("OECD EU weighted", f"{S['oecd_eu_weighted']}%")
need("OECD plotted countries", f"{S['oecd_oecd_n']} countries")
need("OECD EU members", f"{S['oecd_eu_n']} EU members")
assert S["oecd_eu_exact"] and S["oecd_oecd_exact"]
need("OECD OECD unweighted", f"{S['oecd_oecd_unweighted']}", ("paper.md",))
need("OECD sum of dwellings", f"{S['oecd_sum_dwellings_million']} million", ("paper.md",))
assert eid["EU-07"]["value"] == "9" and eid["EU-11"]["value"] == "about 7"

# 4. the Ministry's 2024 bulletin: arithmetic and method
need("regional rental 2019", n(S["regional_rental_2019"]))
need("regional rental 2023", n(S["regional_rental_2023"]))
need("printed regional total", n(S["t23_printed_rental_2023"]))
need("public-ownership change", f"{abs(S['regional_rental_public_growth_pct'])}%")
need("municipal carry-over", f"{S['mun_with_data_2019_carryover']}")
need("municipal scaled on the bulletin's base", n(S["mun_scaled_bulletin_base"]), ("paper.md",))
need("Ceuta and Melilla scaled", n(S["ceuta_melilla_scaled"]), ("paper.md",))
need("regional growth recomputed", f"{S['regional_rental_growth_pct']}%")
need("municipal observed", n(S["mun_rental_observed"]))
need("municipalities with data", f"{S['mun_with_data']} municipalities")
need("municipal scaled", n(S["mun_scaled_by_population"]), ("paper.md",))
# the extrapolated part: scaled minus observed, about half of the municipal component and about a
# fifth of the national count (on either base)
for scaled in (S["mun_scaled_by_population"], S["mun_scaled_bulletin_base"]):
    ext = scaled - S["mun_rental_observed"]
    if not (0.45 <= ext / scaled <= 0.55 and 0.17 <= ext / 318_000 <= 0.23):
        bad.append(f"extrapolated: {ext / scaled:.1%} of the municipal component, {ext / 318_000:.1%} of 318,000")
need("extrapolated part (README)", "About a fifth of the count is extrapolated by population", ("README.md",))
need("extrapolated part (paper)", "About a fifth of the national count, half of its municipal component", ("paper.md",))
need("Ceuta and Melilla", n(S["ceuta_melilla_in_regional_table"]), ("paper.md",))
need("PPP dwellings", n(S["regional_rental_ppp_2023"]))

# 5. art. 32
need("BOE issues read", f"{n(S['boe_issues'])} issues")
need("BOE days", f"{n(S['boe_days'])} days", ("paper.md",))
need("BOE items read", f"{n(S['boe_items'])} item", ("paper.md",))
need("publication titles", f"{S['pub_titles']} titles", ("paper.md",))
need("art. 32 in force", "26 May 2023")
assert S["boe_memoria_hits"] == 0 and S["pub_memoria_titles"] == 0
a32 = rows("art32_search.csv")
assert any(r["route"].startswith("Ministry electronic office (mivau.sede.gob.es)") for r in a32)
assert any("STC 190/2025" in r["what_was_checked"] for r in a32)
need("Constitutional Court ruling", "STC 190/2025")
need("electronic office", "mivau.sede.gob.es")
for i in ("ES-29", "ES-30", "ES-31"):
    v = fid[i]["value"].split(" ")[0]
    need(f"State-side partial figure {i}", v)

# 6. reconciliation table size
rec = rows("reconciliation.csv")
need("reconciliation rows", f"{len(rec)} differences", ("paper.md",))

if bad:
    print("\nMISMATCHES:")
    for b in bad:
        print(" -", b)
    sys.exit(1)
print("\nall headline numbers found")
