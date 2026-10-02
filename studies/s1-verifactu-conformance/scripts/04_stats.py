#!/usr/bin/env python3
"""Fase 4 — estadísticas agregadas y anonimizadas.

Publica en data/ solo agregados y referencias anonimizadas (R01…, F001…). El mapeo
real va a private/ (gitignorado). Ver METHOD.md §5 para las definiciones.

Unidades de análisis:
  - contenido único (sha256) de clase (a), excluidos forks: «ficheros»
  - repositorio no-fork con ≥1 ocurrencia de clase (a): «repos» (titular del informe,
    porque los ficheros de un mismo repo no son independientes)
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PRIV = BASE / "private"
DATA = BASE / "data"
PRIORIDAD = {"c": 5, "d": 4, "e": 3, "b": 2, "a": 1}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - margen), min(1.0, centro + margen))


def pct(k: int, n: int) -> str:
    if not n:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100*k/n:.1f}% [95% CI {100*lo:.1f}–{100*hi:.1f}]"


def main() -> None:
    estado = json.loads((PRIV / "collect_state.json").read_text())
    repos_meta = estado["repos"]
    filas = list(csv.DictReader((PRIV / "classified.csv").open()))
    lint = json.loads((PRIV / "lint_summary.json").read_text())
    occs_all = [json.loads(x) for x in (PRIV / "occurrences.jsonl").read_text().splitlines()]

    # ---------- embudo ----------
    embudo = {
        "repos_buscados": len(repos_meta),
        "repos_busqueda_repos": len(estado["repos_search"]),
        "repos_busqueda_codigo": len({h["repo"] for h in estado["code_hits"]}),
        "hits_busqueda_codigo": len(estado["code_hits"]),
        "candidatos_descargados": len(occs_all),
        "por_estado": dict(Counter(o["status"] for o in occs_all)),
        "ocurrencias_con_marcador": len(filas),
        "contenidos_unicos": len({f["sha256"] for f in filas}),
        "repos_con_marcador": len({f["repo"] for f in filas}),
    }
    es_fork = {r: bool(m.get("fork")) for r, m in repos_meta.items()}
    # Las ocurrencias del repo del instrumento (clase x) se quitan ANTES de deducir la
    # clase de cada contenido. Antes se aplicaban como prioridad por contenido, y un
    # fichero presente a la vez en el repo del instrumento y en 4 repos de terceros
    # salía del nivel fichero pero seguía contando en el nivel repo (revisión
    # adversarial, 2026-10-02).
    embudo["ocurrencias_repo_instrumento_excluidas"] = sum(f["clase"] == "x" for f in filas)
    filas = [f for f in filas if f["clase"] != "x"]
    filas_nf = [f for f in filas if not es_fork.get(f["repo"], False)]
    embudo["ocurrencias_en_forks_excluidas"] = len(filas) - len(filas_nf)
    embudo["repos_fork_excluidos"] = len({f["repo"] for f in filas if es_fork.get(f["repo"])})

    # ---------- clase por contenido (la más conservadora entre ocurrencias) ----------
    clase_contenido: dict[str, str] = {}
    for f in filas_nf:
        c = clase_contenido.get(f["sha256"])
        if c is None or PRIORIDAD[f["clase"]] > PRIORIDAD[c]:
            clase_contenido[f["sha256"]] = f["clase"]
    embudo["ocurrencias_por_clase"] = dict(Counter(f["clase"] for f in filas_nf))
    embudo["ocurrencias_por_motivo"] = dict(Counter(f"{f['clase']}:{f['motivo']}"
                                                    for f in filas_nf))
    embudo["contenidos_por_clase"] = dict(Counter(clase_contenido.values()))
    embudo["estado_lint_clase_a"] = dict(Counter(lint[h]["estado"]
                                                 for h, c in clase_contenido.items()
                                                 if c == "a"))

    a_ok = sorted(h for h, c in clase_contenido.items()
                  if c == "a" and lint[h]["estado"] == "ok")

    def sev(h: str, s: str) -> bool:
        return any(k.endswith(":" + s) for k in lint[h].get("por_regla", {}))

    def reglas_de(h: str, s: str) -> set[str]:
        return {k.split(":")[0] for k in lint[h].get("por_regla", {}) if k.endswith(":" + s)}

    # ---------- nivel fichero ----------
    n = len(a_ok)
    fich = {
        "n_ficheros_a_linteables": n,
        "con_error": sum(sev(h, "error") for h in a_ok),
        "con_aviso": sum(sev(h, "aviso") for h in a_ok),
        "con_incompleto": sum(sev(h, "incompleto") for h in a_ok),
        "sin_hallazgos": sum(not lint[h].get("por_regla") for h in a_ok),
        "registros_alta": sum(lint[h]["n_alta"] for h in a_ok),
        "registros_anulacion": sum(lint[h]["n_anulacion"] for h in a_ok),
        "registros_evento": sum(lint[h]["n_evento"] for h in a_ok),
        "ficheros_un_solo_registro": sum(
            lint[h]["n_alta"] + lint[h]["n_anulacion"] + lint[h]["n_evento"] == 1
            for h in a_ok),
    }
    for k in ("con_error", "con_aviso", "con_incompleto", "sin_hallazgos"):
        fich[k + "_txt"] = pct(fich[k], n)
        fich[k + "_ci95"] = wilson(fich[k], n)

    # ---------- nivel repo ----------
    occ_a = [f for f in filas_nf if f["clase"] == "a" and lint[f["sha256"]]["estado"] == "ok"]
    por_repo: dict[str, list[dict]] = defaultdict(list)
    for f in occ_a:
        por_repo[f["repo"]].append(f)
    # Origen de cada contenido: el repo más antiguo que lo contiene (para separar copias).
    origen: dict[str, str] = {}
    for f in sorted(occ_a, key=lambda f: repos_meta.get(f["repo"], {}).get("created_at") or ""):
        origen.setdefault(f["sha256"], f["repo"])

    salt = (PRIV / "salt.txt")
    if not salt.exists():
        salt.write_text(hashlib.sha256(str(sorted(por_repo)).encode()).hexdigest()[:16])
    s = salt.read_text().strip()
    orden = sorted(por_repo, key=lambda r: hashlib.sha256((s + r).encode()).hexdigest())
    rid = {r: f"R{i+1:02d}" for i, r in enumerate(orden)}
    fid = {h: f"F{i+1:03d}" for i, h in enumerate(sorted(
        {f["sha256"] for f in filas_nf}, key=lambda h: hashlib.sha256((s + h).encode()).hexdigest()))}

    tabla_repos = []
    for r in orden:
        hs = sorted({f["sha256"] for f in por_repo[r]})
        meta = repos_meta.get(r, {})
        estrellas = meta.get("stars", 0)
        tabla_repos.append({
            "repo_id": rid[r],
            "licencia": meta.get("license", "NONE"),
            "lenguaje": meta.get("language") or "",
            "estrellas": "0" if estrellas == 0 else "1-9" if estrellas < 10
                         else "10-49" if estrellas < 50 else "50+",
            "anio_creacion": (meta.get("created_at") or "")[:4],
            "ficheros_a": len(hs),
            "ficheros_a_propios": sum(origen[h] == r for h in hs),
            "ficheros_con_error": sum(sev(h, "error") for h in hs),
            "reglas_error": " ".join(sorted(set().union(*(reglas_de(h, "error") for h in hs)))),
            "reglas_aviso": " ".join(sorted(set().union(*(reglas_de(h, "aviso") for h in hs)))),
        })
    nr = len(tabla_repos)
    rep = {
        "n_repos_con_a": nr,
        "con_error": sum(t["ficheros_con_error"] > 0 for t in tabla_repos),
        "con_error_en_fichero_propio": sum(
            any(sev(h, "error") and origen[h] == r for h in {f["sha256"] for f in por_repo[r]})
            for r in por_repo),
    }
    rep["con_error_txt"] = pct(rep["con_error"], nr)
    rep["con_error_en_fichero_propio_txt"] = pct(rep["con_error_en_fichero_propio"], nr)

    # ---------- por regla ----------
    reglas = sorted({k.split(":")[0] for h in a_ok for k in lint[h].get("por_regla", {})})
    tabla_reglas = []
    for rg in reglas:
        fila = {"regla": rg}
        for sv in ("error", "aviso", "incompleto"):
            hs = [h for h in a_ok if f"{rg}:{sv}" in lint[h].get("por_regla", {})]
            fila[f"ficheros_{sv}"] = len(hs)
            fila[f"hallazgos_{sv}"] = sum(lint[h]["por_regla"][f"{rg}:{sv}"] for h in hs)
            fila[f"repos_{sv}"] = len({r for r in por_repo
                                       if any(f"{rg}:{sv}" in lint[f["sha256"]].get("por_regla", {})
                                              for f in por_repo[r])})
        fila["pct_repos_error"] = round(100 * fila["repos_error"] / nr, 1) if nr else None
        lo, hi = wilson(fila["repos_error"], nr)
        fila["ci95_repos_error"] = f"{100*lo:.1f}-{100*hi:.1f}"
        tabla_reglas.append(fila)
    tabla_reglas.sort(key=lambda x: (-x["repos_error"], -x["ficheros_error"], x["regla"]))

    # ---------- sensibilidad: ficheros con valores de relleno ----------
    # Las reglas de huella (001-005) no tienen sentido sobre una plantilla con
    # «Huella» o «AAAA»; el resto sí: ¿qué dirían si se contaran?
    relleno = sorted({f["sha256"] for f in filas_nf if f["motivo"] == "valores_de_relleno"
                      and lint[f["sha256"]]["estado"] == "ok"})
    no_huella = Counter()
    for h in relleno:
        for k in lint[h].get("por_regla", {}):
            if k.endswith(":error") and k.split(":")[0] not in {
                    "RRSIF001", "RRSIF002", "RRSIF003", "RRSIF004", "RRSIF005"}:
                no_huella[k] += 1
    sensibilidad = {"ficheros_relleno_linteables": len(relleno),
                    "errores_no_huella_por_regla": dict(no_huella),
                    "ficheros_con_error_no_huella": sum(
                        any(k.endswith(":error") and k.split(":")[0] not in {
                            "RRSIF001", "RRSIF002", "RRSIF003", "RRSIF004", "RRSIF005"}
                            for k in lint[h].get("por_regla", {})) for h in relleno)}

    # ---------- escritura ----------
    DATA.mkdir(exist_ok=True)
    (DATA / "summary.json").write_text(json.dumps(
        {"embudo": embudo, "ficheros": fich, "repos": rep, "sensibilidad_relleno": sensibilidad},
        indent=1, ensure_ascii=False))
    for nombre, tabla in (("rules.csv", tabla_reglas), ("repos_anon.csv", tabla_repos)):
        with (DATA / nombre).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(tabla[0].keys()))
            w.writeheader()
            w.writerows(tabla)
    with (DATA / "files_anon.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file_id", "clase_contenido", "estado_lint", "n_alta", "n_anulacion",
                    "n_evento", "repos_no_fork", "reglas_error", "reglas_aviso",
                    "reglas_incompleto"])
        rep_por_h = defaultdict(set)
        for f in filas_nf:
            rep_por_h[f["sha256"]].add(f["repo"])
        for h in sorted(clase_contenido, key=lambda h: fid[h]):
            L = lint[h]
            w.writerow([fid[h], clase_contenido[h], L["estado"], L.get("n_alta", 0),
                        L.get("n_anulacion", 0), L.get("n_evento", 0), len(rep_por_h[h]),
                        " ".join(sorted(reglas_de(h, "error"))),
                        " ".join(sorted(reglas_de(h, "aviso"))),
                        " ".join(sorted(reglas_de(h, "incompleto")))])
    # Mapeo y referencias reales: SOLO private/.
    with (PRIV / "repo_map.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["repo_id", "repo", "license", "fork", "stars"])
        for r in orden:
            m = repos_meta.get(r, {})
            w.writerow([rid[r], r, m.get("license"), m.get("fork"), m.get("stars")])
    with (PRIV / "references.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file_id", "repo_id", "repo", "commit", "path", "license", "clase",
                    "motivo", "via"])
        for f in sorted(filas, key=lambda f: (f["repo"], f["path"])):
            w.writerow([fid.get(f["sha256"], ""), rid.get(f["repo"], ""), f["repo"],
                        f["commit"], f["path"], repos_meta.get(f["repo"], {}).get("license"),
                        f["clase"], f["motivo"], f["via"]])
    print(json.dumps({"embudo": embudo, "ficheros": fich, "repos": rep}, indent=1,
                     ensure_ascii=False))
    for t in tabla_reglas:
        print(t)


if __name__ == "__main__":
    main()
