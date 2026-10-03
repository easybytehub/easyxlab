"""Step 2b: fetch the open-access PDFs / pages of the closest prior work and extract the passages
about pinning, SHAs and tags. Needs `pypdf` (only for this step). PDFs stay in data/raw/prior/;
passages go to work/prior_passages.txt for reading (the quotes used are in paper.md, Prior work).
"""
from __future__ import annotations

import io
import re
import sys

from common import RAW, WORK, RobotsRefused, fetch

PAPERS = {
    "koishybayev_usenix22": "https://www.usenix.org/system/files/sec22-koishybayev.pdf",
    "icpc25_revisiting": "https://repository.ubn.ru.nl//bitstream/handle/2066/320622/320622.pdf",
    "decan_icsme22": "https://orbi.umons.ac.be/bitstream/20.500.12907/43043/1/ICSME-2022.pdf",
    "ndss26_action_required": "https://doi.org/10.14722/ndss.2026.240483",
    "wiz_2025": "https://www.wiz.io/reports/state-of-code-security-2025",
}
PAT = re.compile(r"[^.]*\b(pin|pinned|pinning|SHA|commit hash|hash|tag|tags|immutable|mutable|version reference)\b[^.]*\d[^.]*\.", re.I)


def text_from(body: bytes, ctype: str) -> str:
    if body[:4] == b"%PDF":
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(body))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    t = body.decode("utf-8", "replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def main(keys: list[str]) -> None:
    (RAW / "prior").mkdir(parents=True, exist_ok=True)
    out = open(WORK / "prior_passages.txt", "a", encoding="utf-8")
    for k, url in PAPERS.items():
        if keys and k not in keys:
            continue
        try:
            s, h, b = fetch(url)
        except RobotsRefused as e:
            print(k, "ROBOTS REFUSED", e)
            out.write(f"\n##### {k} ROBOTS REFUSED {e}\n")
            continue
        ctype = h.get("Content-Type", "")
        print(k, s, ctype, len(b))
        if s != 200:
            continue
        (RAW / "prior" / f"{k}.bin").write_bytes(b)
        t = text_from(b, ctype)
        (RAW / "prior" / f"{k}.txt").write_text(t, encoding="utf-8")
        t1 = re.sub(r"\s+", " ", t)
        out.write(f"\n##### {k} {url} chars={len(t1)}\n")
        for m in PAT.finditer(t1):
            out.write("- " + m.group(0).strip()[:600] + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
