"""Download the legal texts in force from Cellar (Publications Office) for literal quotation.
Kept in data/raw/sources/legal/ (not published)."""
import sys, re, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher
f = Fetcher(Path("work/requests.log"))
out = Path("data/raw/sources/legal"); out.mkdir(parents=True, exist_ok=True)
H = {"Accept": "application/xhtml+xml, text/html;q=0.9", "Accept-Language": "eng"}
for celex in ["02023R1114-20240109", "32023R1114", "32024R2984", "32023R2869", "32025R0421"]:
    r = f.get(f"https://publications.europa.eu/resource/celex/{celex}", headers=H)
    b = (r["body"] or b"").decode("utf-8", "replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", b, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)); t = re.sub(r"[ \t\r\f\v]+", " ", t); t = re.sub(r"\n\s*\n+", "\n", t)
    (out / f"{celex}.txt").write_text(t)
    print(celex, r["status"], r["final_url"], r["size"], r["sha256"][:16] if r["sha256"] else None, r["reason"])
