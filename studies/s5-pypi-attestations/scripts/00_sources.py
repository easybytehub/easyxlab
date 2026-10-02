"""Fetch the normative/descriptive sources and print the literal sentences this study relies on.
Raw pages go to data/raw/src/ (not published); matched excerpts go to data/sources/excerpts.json."""
import html, json, os, re, time
from common import http_get, RAW, DATA

SOURCES = {
    "pep740": "https://peps.python.org/pep-0740/",
    "pep691": "https://peps.python.org/pep-0691/",
    "pep700": "https://peps.python.org/pep-0700/",
    "pypi_attestations": "https://docs.pypi.org/attestations/",
    "pypi_producing": "https://docs.pypi.org/attestations/producing-attestations/",
    "pypi_integrity_api": "https://docs.pypi.org/api/integrity/",
    "npm_generating_provenance": "https://docs.npmjs.com/generating-provenance-statements",
    "npm_trusted_publishers": "https://docs.npmjs.com/trusted-publishers",
    "tob_are_we_pep740_yet": "https://trailofbits.github.io/are-we-pep740-yet/",
    "gh_action_pypi_publish_readme": "https://raw.githubusercontent.com/pypa/gh-action-pypi-publish/unstable/v1/README.md",
    "uv_publish_guide": "https://docs.astral.sh/uv/guides/package/",
}
PATTERNS = {
    "pep740": [r"[^.]{0,200}\bprovenance\b[^.]{0,200}\.", r"[^.]{0,200}data-provenance[^.]{0,200}\."],
    "pep691": [r"[^.]{0,200}application/vnd\.pypi\.simple\.v1\+json[^.]{0,200}\."],
    "pep700": [r"[^.]{0,200}upload-time[^.]{0,200}\."],
    "pypi_attestations": [r"[^.]{0,250}attestation[^.]{0,250}\."],
    "pypi_producing": [r"[^.]{0,250}(by default|default)[^.]{0,250}\.", r"[^.]{0,250}Trusted Publish[^.]{0,250}\."],
    "pypi_integrity_api": [r"[^.]{0,250}(provenance|publisher)[^.]{0,250}\."],
    "npm_generating_provenance": [r"[^.]{0,250}provenance[^.]{0,250}\."],
    "npm_trusted_publishers": [r"[^.]{0,250}provenance[^.]{0,250}\."],
    "tob_are_we_pep740_yet": [r"[^.]{0,300}(attestation|packages)[^.]{0,300}\."],
    "gh_action_pypi_publish_readme": [r"[^.]{0,300}attestations?[^.]{0,300}\."],
    "uv_publish_guide": [r"[^.]{0,300}(attestation|Trusted Publish)[^.]{0,300}\."],
}

def text(b):
    t = b.decode("utf-8", "replace")
    t = re.sub(r"(?s)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))

if __name__ == "__main__":
    # Default: reuse the saved pages in data/raw/src/ (snapshot of 2026-10-02) and never touch the network.
    # REFRESH_SOURCES=1 re-downloads them (a new snapshot). If a page is neither cached nor fetchable, the
    # published data/sources/excerpts.json is left untouched.
    os.makedirs(os.path.join(RAW, "src"), exist_ok=True)
    target = os.path.join(DATA, "sources", "excerpts.json")
    refresh = os.environ.get("REFRESH_SOURCES") == "1"
    if not refresh and not all(os.path.exists(os.path.join(RAW, "src", k + ".txt")) for k in SOURCES):
        print("00_sources: saved pages not available; keeping", target); raise SystemExit(0)
    old = json.load(open(target)) if os.path.exists(target) else {}
    out = {"fetched_at": old.get("fetched_at") if not refresh else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sources": {}}
    for k, url in SOURCES.items():
        if not refresh:
            t = open(os.path.join(RAW, "src", k + ".txt")).read()
            prev = old.get("sources", {}).get(k, {})
            rec = {"url": url, "final_url": prev.get("final_url", url), "status": prev.get("status", 200), "excerpts": []}
            seen = set()
            for p in PATTERNS.get(k, []):
                for m in re.finditer(p, t, flags=re.I):
                    s_ = m.group(0).strip()
                    if s_ not in seen:
                        seen.add(s_); rec["excerpts"].append(s_)
            out["sources"][k] = rec; print(k, "cached", len(rec["excerpts"])); continue
        st, body, final = http_get(url, rate=2)
        rec = {"url": url, "final_url": final, "status": st, "excerpts": []}
        if body:
            t = text(body)
            open(os.path.join(RAW, "src", k + ".txt"), "w").write(t)
            seen = set()
            for p in PATTERNS.get(k, []):
                for m in re.finditer(p, t, flags=re.I):
                    s = m.group(0).strip()
                    if s not in seen:
                        seen.add(s); rec["excerpts"].append(s)
        out["sources"][k] = rec
        print(k, st, len(rec["excerpts"]))
    if sum(len(r["excerpts"]) for r in out["sources"].values()) == 0:
        print("00_sources: no excerpts obtained; keeping", target); raise SystemExit(0)
    os.makedirs(os.path.join(DATA, "sources"), exist_ok=True)
    json.dump(out, open(target, "w"), indent=1, ensure_ascii=False)
