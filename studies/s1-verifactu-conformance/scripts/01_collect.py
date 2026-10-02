#!/usr/bin/env python3
"""Fase 1 — recogida de XML de registros Verifactu publicados en GitHub.

Dos vías complementarias, porque cada una ve lo que la otra no:

1. **Búsqueda de código** (`search/code`): encuentra ficheros por contenido, pero solo
   indexa la rama por defecto, ficheros < 384 KB y, en general, no indexa forks.
   Limitada a 10 peticiones/minuto: se respeta con una pausa fija de 7 s.
2. **Búsqueda de repositorios** («verifactu» en nombre, descripción o README) y
   recorrido de su árbol git: encuentra XML que la búsqueda de código no indexó.

Todo lo descargado va a `data/raw/` (gitignorado: los ficheros de terceros NO se
redistribuyen). Las referencias con nombre real de repo van a `private/`
(gitignorado). Lo publicable lo produce `04_stats.py`, ya anonimizado.

Idempotente: lo ya descargado no se vuelve a pedir.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw" / "files"
PRIV = BASE / "private"
RAW.mkdir(parents=True, exist_ok=True)
PRIV.mkdir(parents=True, exist_ok=True)

CODE_QUERIES = [
    "RegistroAlta extension:xml",
    "RegistroAnulacion extension:xml",
    "RegFactuSistemaFacturacion extension:xml",
    "sum1 extension:xml",
    "Huella TipoHuella extension:xml",
    "RegistroEvento extension:xml",
    "IDEmisorFactura extension:xml",
    "NumeroInstalacion IdSistemaInformatico extension:xml",
    "huella RegistroAnterior extension:xml",
]
REPO_QUERIES = [
    "verifactu",
    "veri-factu",
    "verifactu in:readme",
]

# Marcadores de contenido que hacen que un XML entre al corpus.
MARCADOR = re.compile(rb"RegistroAlta|RegistroAnulacion|RegistroEvento|RegFactuSistemaFacturacion")

# Ruido conocido en el recorrido de árboles (vistas Odoo, manifiestos Android, IDEs...).
RUIDO_DIR = {
    "views", "security", "report", "reports", "wizard", "wizards", "i18n", ".idea",
    "node_modules", "res", "layout", "drawable", "values", "mipmap", "vendor", ".vscode",
    "static", "templates_odoo", "menus",
}
RUIDO_FICH = re.compile(
    r"(^pom\.xml$|AndroidManifest\.xml$|\.csproj$|phpunit\.xml(\.dist)?$|^web\.xml$|"
    r"\.wsdl$|^build\.xml$|^checkstyle|^phpcs|^psalm|^infection|^codeception|"
    r"^\.?editorconfig|^nuget|packages\.config$|^app\.config$|^web\.config$)",
    re.I,
)
MAX_XML_POR_REPO = 200
MAX_BYTES = 1_500_000


def gh(path: str, *params: str) -> dict | list:
    cmd = ["gh", "api", "-X", "GET", path, *params]
    for intento in range(4):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        msg = r.stderr + r.stdout
        if "rate limit" in msg.lower() or "403" in msg or "secondary" in msg.lower():
            time.sleep(65)
            continue
        if "404" in msg or "409" in msg:  # repo vacío o borrado
            return {}
        time.sleep(5 * (intento + 1))
    print(f"  ! fallo persistente: {path} {params}", file=sys.stderr)
    return {}


def code_search() -> list[dict]:
    hits: list[dict] = []
    for q in CODE_QUERIES:
        page = 1
        while True:
            res = gh("search/code", "-f", f"q={q}", "-f", "per_page=100", "-f", f"page={page}")
            time.sleep(7)  # 10/min
            items = res.get("items", []) if isinstance(res, dict) else []
            total = res.get("total_count", 0) if isinstance(res, dict) else 0
            print(f"  code q={q!r} p{page}: {len(items)} (total {total})", file=sys.stderr)
            for it in items:
                m = re.search(r"ref=([0-9a-f]{40})", it.get("url", ""))
                hits.append({
                    "repo": it["repository"]["full_name"],
                    "path": it["path"],
                    "blob_sha": it["sha"],
                    "commit": m.group(1) if m else None,
                    "source": f"code:{q}",
                })
            if len(items) < 100 or page * 100 >= min(total, 1000):
                break
            page += 1
    return hits


def repo_search() -> dict[str, dict]:
    repos: dict[str, dict] = {}
    for q in REPO_QUERIES:
        page = 1
        while True:
            res = gh("search/repositories", "-f", f"q={q}", "-f", "per_page=100",
                     "-f", f"page={page}")
            time.sleep(2.5)  # 30/min
            items = res.get("items", []) if isinstance(res, dict) else []
            total = res.get("total_count", 0) if isinstance(res, dict) else 0
            print(f"  repo q={q!r} p{page}: {len(items)} (total {total})", file=sys.stderr)
            for it in items:
                repos[it["full_name"]] = meta_de(it)
            if len(items) < 100 or page * 100 >= min(total, 1000):
                break
            page += 1
    return repos


def meta_de(it: dict) -> dict:
    lic = it.get("license") or {}
    return {
        "full_name": it["full_name"],
        "fork": it.get("fork", False),
        "parent": (it.get("parent") or {}).get("full_name"),
        "license": lic.get("spdx_id") or "NONE",
        "stars": it.get("stargazers_count", 0),
        "language": it.get("language"),
        "created_at": it.get("created_at"),
        "pushed_at": it.get("pushed_at"),
        "archived": it.get("archived", False),
        "default_branch": it.get("default_branch"),
        "size_kb": it.get("size", 0),
    }


def descarga(repo: str, commit: str, path: str) -> bytes | None:
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.request.quote(path)}"
    for intento in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
                return resp.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (intento + 1))
        except Exception:
            time.sleep(2 * (intento + 1))
    return None


def guarda(contenido: bytes) -> str:
    h = hashlib.sha256(contenido).hexdigest()
    destino = RAW / f"{h}.xml"
    if not destino.exists():
        destino.write_bytes(contenido)
    return h


def main() -> None:
    estado_f = PRIV / "collect_state.json"
    estado = json.loads(estado_f.read_text()) if estado_f.exists() else {}

    if "code_hits" not in estado:
        print("[1/4] búsqueda de código", file=sys.stderr)
        estado["code_hits"] = code_search()
        estado_f.write_text(json.dumps(estado))
    if "repos_search" not in estado:
        print("[2/4] búsqueda de repositorios", file=sys.stderr)
        estado["repos_search"] = repo_search()
        estado_f.write_text(json.dumps(estado))

    repos: dict[str, dict] = estado.get("repos", {})
    repos.update({k: v for k, v in estado["repos_search"].items() if k not in repos})
    # Metadatos de los repos que solo vio la búsqueda de código.
    for h in estado["code_hits"]:
        r = h["repo"]
        if r not in repos or repos[r].get("parent") is None and repos[r].get("fork"):
            res = gh(f"repos/{r}")
            if res:
                repos[r] = meta_de(res)
    estado["repos"] = repos
    estado_f.write_text(json.dumps(estado))

    print("[3/4] árboles de los repos", file=sys.stderr)
    arboles: dict[str, dict] = estado.get("arboles", {})

    def arbol(item):
        r, meta = item
        rama = meta.get("default_branch") or "main"
        b = gh(f"repos/{r}/branches/{rama}")
        commit = (b.get("commit") or {}).get("sha") if isinstance(b, dict) else None
        if not commit:
            return r, {"commit": None, "xml": [], "truncated": False}
        t = gh(f"repos/{r}/git/trees/{commit}", "-f", "recursive=1")
        xmls = []
        for e in (t.get("tree", []) if isinstance(t, dict) else []):
            p = e.get("path", "")
            if e.get("type") != "blob" or not p.lower().endswith(".xml"):
                continue
            if e.get("size", 0) > MAX_BYTES:
                continue
            partes = p.split("/")
            if set(x.lower() for x in partes[:-1]) & RUIDO_DIR or RUIDO_FICH.search(partes[-1]):
                continue
            xmls.append({"path": p, "blob_sha": e.get("sha"), "size": e.get("size", 0)})
        return r, {
            "commit": commit,
            "xml": xmls[:MAX_XML_POR_REPO],
            "xml_total": len(xmls),
            "truncated": bool(t.get("truncated")) if isinstance(t, dict) else False,
        }

    pend = [(r, m) for r, m in sorted(repos.items()) if r not in arboles]
    # 6 en paralelo: ~2 llamadas por repo, muy por debajo de 5000/h del API core.
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, (r, a) in enumerate(ex.map(arbol, pend)):
            arboles[r] = a
            if i % 50 == 0:
                estado["arboles"] = arboles
                estado_f.write_text(json.dumps(estado))
                print(f"  árboles {len(arboles)}/{len(repos)}", file=sys.stderr)
    estado["arboles"] = arboles
    estado_f.write_text(json.dumps(estado))

    print("[4/4] descargas", file=sys.stderr)
    tareas: dict[tuple[str, str, str], dict] = {}
    for h in estado["code_hits"]:
        if h["commit"]:
            tareas[(h["repo"], h["commit"], h["path"])] = {"blob_sha": h["blob_sha"],
                                                          "via": {h["source"]}}
    for r, a in arboles.items():
        for x in a["xml"]:
            k = (r, a["commit"], x["path"])
            tareas.setdefault(k, {"blob_sha": x["blob_sha"], "via": set()})["via"].add("tree")

    hechas = {}
    occ_f = PRIV / "occurrences.jsonl"
    if occ_f.exists():
        for line in occ_f.read_text().splitlines():
            o = json.loads(line)
            hechas[(o["repo"], o["commit"], o["path"])] = o

    pendientes = [k for k in tareas if k not in hechas]
    print(f"  {len(tareas)} candidatos, {len(pendientes)} pendientes", file=sys.stderr)

    def trabajo(k):
        return k, descarga(*k)

    with ThreadPoolExecutor(max_workers=8) as ex, occ_f.open("a") as out:
        for n, (k, contenido) in enumerate(ex.map(trabajo, pendientes)):
            repo, commit, path = k
            reg = {"repo": repo, "commit": commit, "path": path,
                   "blob_sha": tareas[k]["blob_sha"], "via": sorted(tareas[k]["via"])}
            if contenido is None:
                reg.update(status="no_descargado")
            elif len(contenido) > MAX_BYTES:
                reg.update(status="demasiado_grande")
            elif not MARCADOR.search(contenido):
                reg.update(status="sin_marcador", size=len(contenido))
            else:
                reg.update(status="ok", size=len(contenido), sha256=guarda(contenido))
            out.write(json.dumps(reg) + "\n")
            if n % 200 == 0:
                print(f"  descargas {n}/{len(pendientes)}", file=sys.stderr)
    print("hecho", file=sys.stderr)


if __name__ == "__main__":
    main()
