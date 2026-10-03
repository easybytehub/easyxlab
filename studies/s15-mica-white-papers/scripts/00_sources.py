"""Download the register CSVs, Wayback CDX lists, the ESMA taxonomy package and ESMA documents used in the study
(data/raw/, never published). The register changes weekly: compare with the hashes in data/sources.csv."""
import hashlib, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher

ROOT = Path(__file__).resolve().parent.parent
S, T = ROOT / "data/raw/sources", ROOT / "data/raw/taxonomy"
S.mkdir(parents=True, exist_ok=True); T.mkdir(parents=True, exist_ok=True)
TAX_SHA = "19921398b16cb2521f808965e5d058be8f68591c8f9d77d24eb9df2c14aae033"
f = Fetcher(ROOT / "work/requests.log")
E = "https://www.esma.europa.eu/sites/default/files/"
for n in ["OTHER.csv", "ARTZZ.csv", "EMTWP.csv", "CASPS.csv", "NCASP.csv", "Description_of_the_fields_in_the_interim_MiCA_register.csv"]:
    print(n, f.get(E + "2024-12/" + n, dest=S / n)["sha256"])
for n in ["OTHER.csv", "EMTWP.csv", "ARTZZ.csv"]:
    r = f.get("https://web.archive.org/cdx/search/cdx?url=esma.europa.eu/sites/default/files/2024-12/"
              f"{n}&output=json&filter=statuscode:200&collapse=digest", dest=S / f"cdx_{n}.json")
for url, dest in [(E + "2025-08/mica_taxonomy_2025.zip", T / "mica_taxonomy_2025.zip"),
                  (E + "2025-08/mica_taxonomy_formulas_202507.xlsx", T / "mica_taxonomy_formulas_202507.xlsx"),
                  (E + "2025-11/ESMA75-1303207761-6284_Statement_to_support_the_smooth_implementation_of_MiCA_standards_and_format.pdf", S / "statement_2025-11.pdf"),
                  (E + "2025-08/mica_taxonomy_reporting_manual_v1.0.pdf", S / "reporting_manual_v1.0.pdf")]:
    print(dest.name, f.get(url, dest=dest)["sha256"])
assert hashlib.sha256((T / "mica_taxonomy_2025.zip").read_bytes()).hexdigest() == TAX_SHA, "taxonomy package changed"
