"""Fetch every ESMA Q&A filed under MiCA (ESMA Q&A tool) and keep their text for the legal baseline.
Output: data/raw/sources/qa/<id>.txt (not published; ESMA texts are quoted in the paper)."""
import html, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch import Fetcher
f = Fetcher(Path("work/requests.log"))
out = Path("data/raw/sources/qa"); out.mkdir(parents=True, exist_ok=True)
ids = []
for page in range(0, 40):
    r = f.get(f"https://www.esma.europa.eu/esma-qa-search-page/all?field_qa_level1_target_id%5B%5D=20011&page={page}")
    b = (r["body"] or b"").decode("utf-8", "replace")
    new = [i for i in re.findall(r'/publications-data/questions-answers/(\d+)', b) if i not in ids]
    if not new: break
    ids += list(dict.fromkeys(new))
print(len(ids), "MiCA Q&As")
def text(b):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", b, flags=re.S)
    i = t.find("<main"); t = t[i:] if i > 0 else t
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t)); return re.sub(r"\n\s*\n+", "\n", t)
for i in ids:
    p = out / f"{i}.txt"
    if p.exists(): continue
    r = f.get(f"https://www.esma.europa.eu/publications-data/questions-answers/{i}")
    p.write_text(text((r["body"] or b"").decode("utf-8", "replace")))
