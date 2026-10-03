"""Download the Wayback Machine snapshots of the register that bracket 23-12-2025 (raw 'id_' captures)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher
f = Fetcher(Path("work/requests.log"))
S = Path("data/raw/sources/wayback"); S.mkdir(parents=True, exist_ok=True)
SNAPS = {"OTHER.csv": ["20251215171738", "20251223101326", "20260106094748"]}
for n in ["EMTWP.csv", "ARTZZ.csv"]:
    rows = json.load(open(f"data/raw/sources/cdx_{n}.json"))[1:]
    before = [r[1] for r in rows if r[1] < "20251224"]
    SNAPS[n] = before[-1:]
for n, ts in SNAPS.items():
    for t in ts:
        u = f"https://web.archive.org/web/{t}id_/https://www.esma.europa.eu/sites/default/files/2024-12/{n}"
        r = f.get(u, dest=S / f"{t}_{n}")
        print(n, t, r["status"], r["size"], r["sha256"])
