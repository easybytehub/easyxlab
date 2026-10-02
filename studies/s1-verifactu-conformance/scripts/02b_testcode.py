#!/usr/bin/env python3
"""Fase 2b — ¿el código de test del repo espera que este XML falle?

Para cada XML provisionalmente en clase (a) que vive bajo un directorio de tests o
fixtures, se descarga el código fuente de test del mismo repo (en el mismo commit) y
se busca el nombre del fichero. Si aparece dentro de un caso de test que contiene una
aserción de error, la
ocurrencia pasa a (b) con motivo `testcode`.

Es una heurística deliberadamente conservadora hacia (b): ante la duda, un fichero se
excluye del numerador de incumplimientos. METHOD.md §3.3 explica el sesgo que eso
introduce (subestima la tasa de incumplimiento, no la sobreestima).
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parent.parent
PRIV = BASE / "private"
CACHE = BASE / "data" / "raw" / "testsrc"
CACHE.mkdir(parents=True, exist_ok=True)

TESTDIR = re.compile(r"(^|/)(tests?|spec|specs|__tests__|fixtures?|testdata|test-data|"
                     r"resources/test|src/test)(/|$)", re.I)
SRC_EXT = (".py", ".js", ".ts", ".mjs", ".cjs", ".php", ".java", ".cs", ".go", ".rb",
           ".kt", ".rs", ".ex", ".exs", ".dart", ".swift", ".scala")
NEG_ASSERT = re.compile(
    r"(assertRaises|pytest\.raises|toThrow|rejects\.|expectException|assertThrows|"
    r"Assert\.Throws|ThrowsException|should_raise|raise_error|assert_raise|"
    r"assertFalse|toBe\(false\)|toBeFalse|is_valid\W*(==|is)\s*False|\.isValid\(\)\)\s*"
    r"\.toBe\(false|assertNotEmpty\([^)]*err|assertCount\([1-9]|toHaveLength\([1-9]|"
    r"errors?\W*\)?\s*\.?\s*(toHaveLength|length)\s*[>(]\s*[1-9]?|invalid|incorrect|"
    r"should\s+(fail|reject)|debe\s+fallar|Rechaz|expectedError|ExpectedException)",
    re.I,
)


# Inicio de un caso de test. La ventana de búsqueda de aserciones es el caso que
# contiene la referencia, no ±N líneas: la primera versión usaba ±12 líneas y la
# revisión manual encontró 3 de 3 falsos (b) — el `toThrow` era del test de encima.
TEST_START = re.compile(
    r"^\s*(it|test|describe|context)\s*[\(.]|^\s*(async\s+)?def\s+test|function\s+test|"
    r"@Test\b|\[(Fact|Test|TestMethod|Theory)\]|^\s*func\s+Test|^\s*it\s+['\"]|"
    r"^\s*#\[test\]|^\s*test\s+['\"]"
)


# Señal positiva en el mismo caso: el fichero se usa como «golden» o se valida como
# correcto. La revisión manual encontró un golden file cuyo caso, además, comprobaba que
# una versión MANIPULADA en memoria lanzaba error: el fichero en sí es positivo.
POS_ASSERT = re.compile(r"golden|assertValid|is_valid\(\)\s*$|matches_its_own|"
                        r"toMatchSnapshot|assertXmlStringEqualsXmlFile|_is_valid\b", re.I)


def bloque(lineas: list[str], i: int) -> str:
    """El caso de test que contiene la línea i (o, fuera de un caso, solo esa línea)."""
    ini = next((j for j in range(i, -1, -1) if TEST_START.search(lineas[j])), None)
    if ini is None:
        return lineas[i]
    fin = next((j for j in range(i + 1, len(lineas)) if TEST_START.search(lineas[j])),
               len(lineas))
    return "\n".join(lineas[ini:fin])


def gh(path: str, *params: str):
    r = subprocess.run(["gh", "api", "-X", "GET", path, *params], capture_output=True,
                       text=True)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def bajar(repo: str, commit: str, path: str) -> str:
    dest = CACHE / repo.replace("/", "__") / path
    if dest.exists():
        return dest.read_text(errors="ignore")
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.request.quote(path)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310
            data = r.read(400_000)
    except Exception:
        return ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data.decode("utf-8", "ignore")


def main() -> None:
    filas = list(csv.DictReader((PRIV / "classified.csv").open()))
    objetivo = [f for f in filas if f["clase"] == "a" and TESTDIR.search(f["path"])]
    por_repo: dict[tuple[str, str], list[dict]] = {}
    for f in objetivo:
        por_repo.setdefault((f["repo"], f["commit"]), []).append(f)

    resultado: dict[str, dict] = {}
    for (repo, commit), ficheros in por_repo.items():
        t = gh(f"repos/{repo}/git/trees/{commit}", "-f", "recursive=1")
        fuentes = [e["path"] for e in t.get("tree", [])
                   if e.get("type") == "blob" and e["path"].endswith(SRC_EXT)
                   and TESTDIR.search(e["path"]) and e.get("size", 0) < 400_000][:300]
        with ThreadPoolExecutor(8) as ex:
            textos = dict(zip(fuentes, ex.map(lambda p: bajar(repo, commit, p), fuentes)))
        for f in ficheros:
            nombre = PurePosixPath(f["path"]).name
            stem = PurePosixPath(f["path"]).stem
            # Un stem corto («alta», «f1») casaría con cualquier cosa: entonces se
            # exige el nombre completo con extensión.
            raiz = stem if len(stem) >= 8 else nombre
            evidencias = []
            for src, txt in textos.items():
                if raiz not in txt:
                    continue
                lineas = txt.splitlines()
                for i, ln in enumerate(lineas):
                    if raiz in ln:
                        ventana = bloque(lineas, i)
                        m = None if POS_ASSERT.search(ventana) else NEG_ASSERT.search(ventana)
                        evidencias.append({"src": src, "linea": i + 1,
                                           "negativo": bool(m),
                                           "match": m.group(0) if m else None})
            resultado[f'{repo}|{f["path"]}'] = {
                "referenciado": bool(evidencias),
                "negativo": any(e["negativo"] for e in evidencias),
                "evidencias": evidencias[:6],
                "nombre": nombre,
            }
    (PRIV / "testcode.json").write_text(json.dumps(resultado, indent=1, ensure_ascii=False))
    n_ref = sum(v["referenciado"] for v in resultado.values())
    n_neg = sum(v["negativo"] for v in resultado.values())
    print(f"{len(resultado)} ficheros en dirs de test; {n_ref} referenciados por código; "
          f"{n_neg} junto a aserción de error")


if __name__ == "__main__":
    main()
