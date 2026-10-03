#!/usr/bin/env python3
"""Stream each Inside Airbnb snapshot (data/raw/insideairbnb/*.csv.gz) and write one private,
row-level extract per snapshot to work/extract/ (git-ignored, never published): the listing's
area, municipality, activity fields and the parsed licence field. Host names, URLs,
descriptions, coordinates and every other column are not copied.

    python3 scripts/extract_listings.py
"""
import csv, gzip, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from snapshots import SNAPSHOTS, REGION, raw_path
from strnum import split_license, parse_regional, parse_national, looks_national, is_exempt, exempt_reason, norm_text
csv.field_size_limit(10**9)
OUT = "work/extract"
os.makedirs(OUT, exist_ok=True)

CITY_MUNI = {"barcelona": "Barcelona", "valencia": "València", "malaga": "Málaga", "sevilla": "Sevilla",
             "madrid": "Madrid"}
FIELDS = ["id", "host_id", "area", "region", "snapshot", "municipality", "district", "room_type",
          "minimum_nights", "reviews_ltm", "reviews_per_month", "availability_365", "active",
          "lic_labelled", "nat_in_reg", "nat_status", "nat_kind", "nat_exempt_reason",
          "reg_source", "reg_label", "reg_status", "reg_key", "reg_kind", "reg_tourist", "reg_open",
          "reg_province", "reg_extra", "reg_note", "reg_exempt_reason", "emb_status", "emb_key", "emb_kind",
          "license_raw"]


def embedded_regional(nat_value, region):
    """The regional number a national TU number carries at its end (after the digits)."""
    v = norm_text(nat_value).replace(" ", "")[6:]
    i = next((k for k, ch in enumerate(v) if ch.isalpha()), None)
    if i is None:
        return None
    return parse_regional(v[i:], region)


def extract(area, date):
    region = REGION[area]
    src = raw_path(area, date)
    out = f"{OUT}/{area}_{date}.csv"
    n = 0
    with gzip.open(src, "rt", encoding="utf-8", newline="") as f, open(out, "w", newline="", encoding="utf-8") as g:
        w = csv.DictWriter(g, FIELDS)
        w.writeheader()
        for row in csv.DictReader(f):
            n += 1
            lic = row.get("license") or ""
            s = split_license(lic)
            nat_val, reg_val, reg_src = s["national"], s["regional"], "labelled" if s["regional"] is not None else ""
            # unlabelled values (NYC; a few old Spanish entries): national-looking ones are national
            for u in s["unlabelled"]:
                if looks_national(u) and nat_val is None:
                    nat_val = u
                elif reg_val is None:
                    reg_val, reg_src = u, "unlabelled"
            nat_in_reg = 0
            if reg_val is not None and looks_national(reg_val):
                # a national number typed into the regional field: it is not a regional number
                nat_in_reg = 1
                if nat_val is None:
                    nat_val = reg_val
                reg_val = None
            nat = parse_national(nat_val) if nat_val is not None else None
            reg = parse_regional(reg_val, region) if reg_val is not None else None
            emb = embedded_regional(nat_val, region) if (nat and nat.status == "ok" and nat.kind == "national-TU") else None
            muni = CITY_MUNI.get(area) or (row["neighbourhood_group_cleansed"] if area == "nyc" else row["neighbourhood_cleansed"])
            try:
                ltm = int(row["number_of_reviews_ltm"] or 0)
            except ValueError:
                ltm = 0
            w.writerow({
                "id": row["id"], "host_id": row["host_id"], "area": area, "region": region, "snapshot": date,
                "municipality": muni,
                "district": row["neighbourhood_group_cleansed"] or row["neighbourhood_cleansed"],
                "room_type": row["room_type"], "minimum_nights": row["minimum_nights"],
                "reviews_ltm": ltm, "reviews_per_month": row["reviews_per_month"],
                "availability_365": row["availability_365"], "active": int(ltm >= 1),
                "lic_labelled": int(s["labelled"]), "nat_in_reg": nat_in_reg,
                "nat_status": nat.status if nat else "absent", "nat_kind": nat.kind if nat else "",
                "nat_exempt_reason": nat.note if (nat and nat.status == "exempt") else "",
                "reg_source": reg_src if reg else "", "reg_label": s["regional_label"] or "",
                "reg_status": reg.status if reg else "absent", "reg_key": reg.key if reg else "",
                "reg_kind": reg.kind if reg else "", "reg_tourist": int(bool(reg and reg.tourist_dwelling)),
                "reg_open": int(bool(reg and reg.registry_open)), "reg_province": reg.province if reg else "",
                "reg_extra": reg.extra if reg else "", "reg_note": reg.note if reg else "",
                "reg_exempt_reason": reg.note if (reg and reg.status == "exempt") else "",
                "emb_status": emb.status if emb else "", "emb_key": emb.key if emb else "",
                "emb_kind": emb.kind if emb else "",
                "license_raw": lic,
            })
    print(area, date, n)


if __name__ == "__main__":
    for area, path, before, after in SNAPSHOTS:
        for d in (before, after):
            extract(area, d)
