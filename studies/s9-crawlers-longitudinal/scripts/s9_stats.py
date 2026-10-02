"""Small, dependency-free statistics for S9 (PROTOCOL.md §9). Standard library only.

- wilson(k, n): Wilson score 95% interval for a proportion.
- zero_event_upper(n): exact one-sided 95% upper bound for a probability when 0 events in n trials.
- mann_kendall(xs): S, Kendall's tau, exact p-values when there are no ties (Mahonian distribution of
  inversions), normal approximation with tie correction and continuity correction otherwise.
- sens_slope(xs): median of pairwise slopes (per step).
- fisher_exact(a, b, c, d): one- and two-sided p-values for the 2x2 table [[a, b], [c, d]].
"""
from __future__ import annotations

import math
from fractions import Fraction

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def zero_event_upper(n: int, alpha: float = 0.05) -> float:
    return 1.0 if n <= 0 else 1 - alpha ** (1 / n)


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _mahonian(n: int) -> list[int]:
    """Number of permutations of n items with k inversions, k = 0..n(n-1)/2."""
    counts = [1]
    for m in range(2, n + 1):
        new = [0] * (len(counts) + m - 1)
        for k, c in enumerate(counts):
            if c:
                for j in range(m):
                    new[k + j] += c
        counts = new
    return counts


def mann_kendall(xs: list[float]) -> dict:
    n = len(xs)
    if n < 3:
        return {"n": n, "S": 0, "tau": float("nan"), "p_two": float("nan"), "p_increase": float("nan"),
                "p_decrease": float("nan"), "method": "too-short"}
    s = sum(_sign(xs[j] - xs[i]) for i in range(n) for j in range(i + 1, n))
    pairs = n * (n - 1) // 2
    ties = {}
    for x in xs:
        ties[x] = ties.get(x, 0) + 1
    has_ties = any(t > 1 for t in ties.values())
    if not has_ties and n <= 50:
        dist = _mahonian(n)            # dist[k] permutations with k inversions; S = pairs - 2k
        total = math.factorial(n)
        # P(S >= s) = P(k <= (pairs - s) / 2)
        def p_ge(sv):
            kmax = math.floor((pairs - sv) / 2)
            return Fraction(sum(dist[: kmax + 1]), total) if kmax >= 0 else Fraction(0)
        def p_le(sv):
            kmin = math.ceil((pairs - sv) / 2)
            return Fraction(sum(dist[kmin:]), total) if kmin <= pairs else Fraction(0)
        p_inc, p_dec = float(p_ge(s)), float(p_le(s))
        p_two = min(1.0, 2 * min(p_inc, p_dec))
        method = "exact"
    else:
        var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties.values())) / 18
        z = 0.0 if s == 0 or var <= 0 else (s - _sign(s)) / math.sqrt(var)
        phi = lambda v: 0.5 * (1 + math.erf(v / math.sqrt(2)))  # noqa: E731
        p_inc, p_dec = 1 - phi(z), phi(z)
        p_two = min(1.0, 2 * min(p_inc, p_dec))
        method = "normal-ties" if has_ties else "normal"
    return {"n": n, "S": s, "tau": s / pairs, "p_two": p_two, "p_increase": p_inc, "p_decrease": p_dec,
            "method": method}


def sens_slope(xs: list[float]) -> float:
    sl = sorted((xs[j] - xs[i]) / (j - i) for i in range(len(xs)) for j in range(i + 1, len(xs)))
    if not sl:
        return float("nan")
    m = len(sl) // 2
    return sl[m] if len(sl) % 2 else (sl[m - 1] + sl[m]) / 2


def _hyper(a: int, r1: int, c1: int, n: int) -> float:
    return math.comb(r1, a) * math.comb(n - r1, c1 - a) / math.comb(n, c1)


def fisher_exact(a: int, b: int, c: int, d: int) -> dict:
    """Table [[a, b], [c, d]]. p_greater: P(A >= a) (row 1 has MORE in column 1 than chance);
    p_less: P(A <= a); p_two: sum of tables no more likely than the observed one."""
    r1, c1, n = a + b, a + c, a + b + c + d
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    probs = {x: _hyper(x, r1, c1, n) for x in range(lo, hi + 1)}
    p_obs = probs[a]
    p_two = sum(p for p in probs.values() if p <= p_obs * (1 + 1e-7))
    return {"p_two": min(1.0, p_two), "p_greater": min(1.0, sum(p for x, p in probs.items() if x >= a)),
            "p_less": min(1.0, sum(p for x, p in probs.items() if x <= a))}
