"""Disclosure control for S19's published tables.

Every published number belongs to a *group* (one table cell, which may hold several variables:
buildings with dwellings 'b', dwellings 'd', all buildings 'a'). Groups are linked by linear
equations per variable (a municipal total is the sum of its cells, a province cell the sum over
municipalities, 'either' = 'copernicus' + 'gva' - 'both', ...). A group may be *hidden*: an
intermediate sum that is not published (always unknown, never a disclosure target).

Rules:
1. Primary: a group is suppressed when it represents 1-4 buildings (all buildings 'a' when the
   group has it; buildings with dwellings 'b' otherwise).
2. Complementary, in two steps:
   a. while some equation has exactly one suppressed value, suppress one more term of that
      equation: the lowest level (cells before municipal totals before province totals), then the
      smallest;
   b. a value x_j is still determined when the unit vector e_j lies in the row space of the
      equations restricted to the unknown values (every null-space vector has a zero j-th entry).
      While some value is determined, suppress the cheapest published group connected to it and
      test again.
scripts/check_disclosure.py repeats the test independently on the files as published."""
import os

import numpy as np

LEVEL = {"c": 0, "m": 1, "mct": 1, "g": 1, "p": 2, "u": 2, "zo": 2, "ut": 3}


def level(gid):
    return LEVEL.get(gid[0], 4)


class Registry:
    def __init__(self, k=5):
        self.k = k
        self.groups = {}       # gid -> {"vals": {var: n}, "supp": bool, "hidden": bool}
        self.eqs = []          # (var, [(gid, coef), ...]) meaning sum coef * value(gid, var) = 0

    def add(self, gid, hidden=False, **vals):
        if gid in self.groups:
            g = self.groups[gid]["vals"]
            for v, n in vals.items():
                if v in g and g[v] != n:
                    raise ValueError(f"{gid}: {v} registered as {g[v]} and {n}")
                g[v] = n
        else:
            self.groups[gid] = {"vals": dict(vals), "supp": False, "hidden": hidden}
        return gid

    def total(self, gid, parts, vars=("b", "d"), signs=None):
        """gid = sum of parts (for each variable in vars)."""
        signs = signs or [1] * len(parts)
        for v in vars:
            self.eqs.append((v, [(gid, -1)] + [(p, s) for p, s in zip(parts, signs)]))

    def value(self, gid, var):
        return self.groups[gid]["vals"].get(var, 0)

    def unknown(self, gid):
        g = self.groups[gid]
        return g["supp"] or g["hidden"]

    def published(self, gid):
        return not self.unknown(gid)

    def fmt(self, gid, var):
        return "<5" if self.unknown(gid) else self.value(gid, var)

    def _size(self, gid):
        v = self.groups[gid]["vals"]
        return v.get("a", v.get("b", 0))

    def _key(self, gid):
        return (level(gid), self._size(gid), str(gid))

    # ---------------------------------------------------------------- rules
    def primary(self):
        for gid, g in self.groups.items():
            v = g["vals"]
            n = v["a"] if "a" in v else v.get("b", 0)
            if 0 < n < self.k or ("b" in v and 0 < v["b"] < self.k):
                g["supp"] = True

    def singletons(self):
        added = 0
        changed = True
        while changed:
            changed = False
            for v, terms in self.eqs:
                ids = [g for g, _ in terms]
                unk = [g for g in ids if self.unknown(g)]
                if len(unk) != 1 or self.groups[unk[0]]["hidden"]:
                    continue
                cand = [g for g in ids if not self.unknown(g)]
                if not cand:
                    continue
                g = min(cand, key=self._key)
                self.groups[g]["supp"] = True
                added += 1
                changed = True
        return added

    def determined(self):
        """Suppressed (not hidden) groups with at least one variable fixed by the published values."""
        out = set()
        for var in sorted({v for v, _ in self.eqs}):
            eqs = [terms for v, terms in self.eqs if v == var]
            unknown = sorted({gid for terms in eqs for gid, _ in terms if self.unknown(gid)}, key=str)
            if not unknown:
                continue
            col = {gid: j for j, gid in enumerate(unknown)}
            rows = []
            for terms in eqs:
                r = np.zeros(len(unknown))
                for gid, c in terms:
                    if gid in col:
                        r[col[gid]] += c
                if r.any():
                    rows.append(r)
            if not rows:
                continue
            A = np.array(rows)
            _, s, vt = np.linalg.svd(A, full_matrices=True)
            rank = int((s > 1e-9 * max(1.0, s.max())).sum())
            ns = vt[rank:]
            for gid, j in col.items():
                if self.groups[gid]["hidden"]:
                    continue
                if ns.shape[0] == 0 or np.abs(ns[:, j]).max() < 1e-9:
                    out.add(gid)
        return out

    def _candidate(self, gid, depth=3):
        """A published group to suppress so that gid is no longer determined: among the groups
        that share an equation with gid, one of the same municipality if there is any (a cell's
        determination usually comes from its own municipality's totals), else any; the lowest level
        first, then the smallest (zeros cost nothing). If no published group shares an equation with
        gid, search outwards through unknown groups."""
        seen, frontier = {gid}, [gid]
        local = gid[0] in ("c", "m", "mct", "g")
        for _ in range(depth):
            cands, nxt = [], []
            for g0 in frontier:
                for e in self._index.get(g0, ()):
                    for g, _ in self.eqs[e][1]:
                        if g in seen:
                            continue
                        seen.add(g)
                        (nxt if self.unknown(g) else cands).append(g)
            if cands:
                same = [g for g in cands if local and len(g) > 1 and g[1] == gid[1] and g[0] in ("c", "m", "mct", "g")]
                return min(same or cands, key=self._key)
            frontier = nxt
            if not frontier:
                break
        return None

    def run(self, max_rounds=200):
        from collections import defaultdict
        self._index = defaultdict(list)
        for e, (_, terms) in enumerate(self.eqs):
            for g, _ in terms:
                self._index[g].append(e)
        self.primary()
        n1 = sum(g["supp"] for g in self.groups.values())
        self.singletons()
        for _ in range(max_rounds):
            det = self.determined()
            if not det:
                break
            # one complement per determined group, then re-test (a complement often protects several)
            added = {self._candidate(g) for g in sorted(det, key=self._key)} - {None}
            if os.environ.get("S19_DEBUG"):
                print("round", _, "determined", len(det), sorted(det, key=str)[:6], "added", sorted(added, key=str)[:6], flush=True)
            if not added:
                raise RuntimeError(f"cannot protect {sorted(det, key=str)[:5]}")
            for g in added:
                self.groups[g]["supp"] = True
            self.singletons()
        else:
            raise RuntimeError("complementary suppression did not converge")
        n2 = sum(g["supp"] for g in self.groups.values()) - n1
        return n1, n2
