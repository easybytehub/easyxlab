#!/usr/bin/env python3
"""S21 library: territories, quarters, window sums and the small statistics the study needs.

Standard library only. Every function here is pure (no I/O) so that tests/test_s21lib.py can
exercise it on synthetic numbers.
"""
import math
import random
import statistics
import unicodedata

# INE code, label used in our tables, aliases as written in the MIVAU workbooks
PROVINCES = [
    ("04", "Almería", ["Almería"]), ("11", "Cádiz", ["Cádiz"]), ("14", "Córdoba", ["Córdoba"]),
    ("18", "Granada", ["Granada"]), ("21", "Huelva", ["Huelva"]), ("23", "Jaén", ["Jaén"]),
    ("29", "Málaga", ["Málaga"]), ("41", "Sevilla", ["Sevilla"]),
    ("22", "Huesca", ["Huesca"]), ("44", "Teruel", ["Teruel"]), ("50", "Zaragoza", ["Zaragoza"]),
    ("33", "Asturias", ["Asturias (Principado de)", "Asturias (Principado de )", "Asturias"]),
    ("07", "Illes Balears", ["Balears (Illes)", "Baleares"]),
    ("35", "Las Palmas", ["Palmas (Las)", "Las Palmas"]),
    ("38", "Santa Cruz de Tenerife", ["Santa Cruz de Tenerife", "Tenerife"]),
    ("39", "Cantabria", ["Cantabria"]),
    ("05", "Ávila", ["Ávila"]), ("09", "Burgos", ["Burgos"]), ("24", "León", ["León"]),
    ("34", "Palencia", ["Palencia"]), ("37", "Salamanca", ["Salamanca"]), ("40", "Segovia", ["Segovia"]),
    ("42", "Soria", ["Soria"]), ("47", "Valladolid", ["Valladolid"]), ("49", "Zamora", ["Zamora"]),
    ("02", "Albacete", ["Albacete"]), ("13", "Ciudad Real", ["Ciudad Real"]), ("16", "Cuenca", ["Cuenca"]),
    ("19", "Guadalajara", ["Guadalajara"]), ("45", "Toledo", ["Toledo"]),
    ("08", "Barcelona", ["Barcelona"]), ("17", "Girona", ["Girona"]), ("25", "Lleida", ["Lleida"]),
    ("43", "Tarragona", ["Tarragona"]),
    ("03", "Alicante", ["Alicante/Alacant", "Alicante"]), ("12", "Castellón", ["Castellón/Castelló", "Castellón"]),
    ("46", "Valencia", ["Valencia/València", "Valencia"]),
    ("06", "Badajoz", ["Badajoz"]), ("10", "Cáceres", ["Cáceres"]),
    ("15", "A Coruña", ["Coruña (A)", "A Coruña"]), ("27", "Lugo", ["Lugo"]), ("32", "Ourense", ["Ourense"]),
    ("36", "Pontevedra", ["Pontevedra"]),
    ("28", "Madrid", ["Madrid (Comunidad de)", "Madrid"]), ("30", "Murcia", ["Murcia (Región de)", "Murcia"]),
    ("31", "Navarra", ["Navarra (Comunidad Foral de)", "Navarra"]),
    ("01", "Araba/Álava", ["Araba/Alava", "Álava"]), ("20", "Gipuzkoa", ["Gipuzkoa", "Guipúzcoa"]),
    ("48", "Bizkaia", ["Bizkaia", "Vizcaya"]), ("26", "La Rioja", ["Rioja (La)", "La Rioja"]),
    ("51", "Ceuta", ["Ceuta"]), ("52", "Melilla", ["Melilla"]),
]
CODE_LABEL = {c: l for c, l, _ in PROVINCES}

# The six provinces that, according to the Council of Ministers of 9 April 2024, concentrated 90%
# of real-estate investor authorisations (Barcelona, Madrid, Málaga, Alicante, Baleares, Valencia).
OFFICIAL_SIX = ["08", "28", "29", "03", "07", "46"]
CORE_TWO = ["28", "08"]  # Madrid, Barcelona

# buyer groups of MIVAU table 1.6
GROUPS = ["total", "res_total", "res_es", "res_fx", "res_nc", "nres_total", "nres_es", "nres_fx",
          "nres_nc", "nc"]
GROUP_LABEL = {
    "nres_fx": "foreign non-residents", "res_fx": "foreign residents",
    "nres_es": "Spanish non-residents", "res_es": "Spanish residents", "total": "all buyers",
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("/", " / ").split())


_ALIAS = {}
for _c, _l, _al in PROVINCES:
    for _a in _al + [_l]:
        _ALIAS[norm(_a)] = _c


def province_code(name):
    """INE code for a territory name as printed by the MIVAU, or None (regions, totals)."""
    return _ALIAS.get(norm(name))


# ---- quarters --------------------------------------------------------------------------------

def qid(year, q):
    return f"{year}Q{q}"


def qparse(s):
    y, q = s.split("Q")
    return int(y), int(q)


def qindex(s):
    y, q = qparse(s)
    return y * 4 + (q - 1)


def qfrom(i):
    return qid(i // 4, i % 4 + 1)


def qrange(a, b):
    """Inclusive list of quarter ids from a to b."""
    return [qfrom(i) for i in range(qindex(a), qindex(b) + 1)]


def qshift(s, k):
    return qfrom(qindex(s) + k)


def sheet_quarter(name):
    """'2t 2026' -> '2026Q2'."""
    t, y = name.strip().split()
    return qid(int(y), int(t[0]))


# ---- windows ---------------------------------------------------------------------------------

def window_sum(series, quarters):
    """Sum of series[q] over quarters; None if any quarter is missing."""
    tot = 0
    for q in quarters:
        if q not in series:
            return None
        tot += series[q]
    return tot


def pct(a, b):
    """Percentage change from b to a."""
    return 100.0 * (a / b - 1.0)


def log_ratio(a, b):
    return math.log(a) - math.log(b)


def rel_change(y_post, y_pre, c_post, c_pre):
    """Change of a treated series relative to a comparison series, as a percentage:
    100 * [ (y_post/y_pre) / (c_post/c_pre) - 1 ]."""
    return 100.0 * (math.exp(log_ratio(y_post, y_pre) - log_ratio(c_post, c_pre)) - 1.0)


# ---- inference helpers -----------------------------------------------------------------------

def rank_p(value, placebo, side="lower"):
    """Share of placebo values at least as extreme as value (value itself included in the count
    and in the denominator, so the smallest attainable p is 1/(n+1))."""
    if side == "lower":
        k = sum(1 for v in placebo if v <= value)
    elif side == "upper":
        k = sum(1 for v in placebo if v >= value)
    else:
        k = sum(1 for v in placebo if abs(v) >= abs(value))
    return (k + 1) / (len(placebo) + 1)


def quantile(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    h = (len(xs) - 1) * p
    lo = math.floor(h)
    hi = math.ceil(h)
    return xs[lo] + (xs[hi] - xs[lo]) * (h - lo)


def poisson_ratio_ci(a, b, z=1.959964):
    """Wald interval for the ratio of two independent Poisson counts a/b, on the log scale.
    Only sampling noise: the placebo-date distributions carry the rest."""
    r = a / b
    se = math.sqrt(1.0 / a + 1.0 / b)
    return r, r * math.exp(-z * se), r * math.exp(z * se)


# ---- weighted least squares with absorbed fixed effects ---------------------------------------

def demean(values, groups_list, weights, tol=1e-10, maxit=500):
    """Alternating projections: remove weighted means within each grouping in groups_list
    (each a list of hashable keys, one per observation) until convergence."""
    v = list(values)
    n = len(v)
    for _ in range(maxit):
        delta = 0.0
        for g in groups_list:
            s, w = {}, {}
            for i in range(n):
                s[g[i]] = s.get(g[i], 0.0) + weights[i] * v[i]
                w[g[i]] = w.get(g[i], 0.0) + weights[i]
            for i in range(n):
                m = s[g[i]] / w[g[i]]
                v[i] -= m
                delta = max(delta, abs(m))
        if delta < tol:
            break
    return v


def solve(A, b):
    """Gaussian elimination with partial pivoting (small dense systems)."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-14:
            raise ValueError("singular matrix")
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def inv(A):
    n = len(A)
    cols = [solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def wls_fe(y, X, fe, w, cluster=None):
    """Weighted OLS of y on the columns of X after absorbing the fixed effects in fe.
    Returns (beta, se) with cluster-robust (CR1) standard errors if cluster is given,
    else heteroskedasticity-robust (HC1)."""
    n, k = len(y), len(X[0])
    yd = demean(y, fe, w)
    Xd_cols = [demean([X[i][j] for i in range(n)], fe, w) for j in range(k)]
    Xd = [[Xd_cols[j][i] for j in range(k)] for i in range(n)]
    XtX = [[sum(w[i] * Xd[i][a] * Xd[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(w[i] * Xd[i][a] * yd[i] for i in range(n)) for a in range(k)]
    beta = solve(XtX, Xty)
    e = [yd[i] - sum(Xd[i][j] * beta[j] for j in range(k)) for i in range(n)]
    B = inv(XtX)
    meat = [[0.0] * k for _ in range(k)]
    if cluster is None:
        cluster = list(range(n))
    sc = {}
    for i in range(n):
        g = sc.setdefault(cluster[i], [0.0] * k)
        for j in range(k):
            g[j] += w[i] * Xd[i][j] * e[i]
    for g in sc.values():
        for a in range(k):
            for b in range(k):
                meat[a][b] += g[a] * g[b]
    G = len(sc)
    adj = G / (G - 1) if G > 1 else 1.0
    V = [[adj * sum(B[a][c] * sum(meat[c][d] * B[d][b] for d in range(k)) for c in range(k))
          for b in range(k)] for a in range(k)]
    return beta, [math.sqrt(max(V[j][j], 0.0)) for j in range(k)]


def corr(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy)


def wslope(xs, ys, ws):
    """Weighted least-squares slope of ys on xs (with intercept)."""
    W = sum(ws)
    mx = sum(w * x for w, x in zip(ws, xs)) / W
    my = sum(w * y for w, y in zip(ws, ys)) / W
    sxy = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys))
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
    return sxy / sxx


def permute_slopes(xs, ys, ws, n=9999, seed=21):
    """Slopes after randomly permuting the exposure across units (Fisher-style)."""
    rng = random.Random(seed)
    out = []
    xs = list(xs)
    for _ in range(n):
        rng.shuffle(xs)
        out.append(wslope(xs, ys, ws))
    return out
