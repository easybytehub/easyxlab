#!/usr/bin/env python3
"""Reusable logic for S13: registry numbers, day types, run-up excess against a day-type
baseline, placebo windows, ratio confidence intervals, number gaps and processing-order lags.
Standard library only. Unit tests: tests/test_s13lib.py."""
import datetime as dt
import math
import re
import statistics

SIG_RX = re.compile(r"^CV-VUT(\d+)-(A|CS|V)$")
HIST_RX = re.compile(r"^VT-(\d+)(A|CS|V|BM)$")
ALICANTE_NEW_COUNTER = 490000      # Alicante restarted its counter at 490000 in May 2022


UNIT_RX = re.compile(r"\b(ES|PL|PT):\s*([^\s,]*)")


def unit_kind(direccion):
    """whole_parcel | in_building | unknown, from the cadastral-style unit part of the address
    ("ES:<stair> PL:<floor> PT:<door>"). "PL:OD PT:OS" marks a property not divided into units.
    Called at ingest only; the address itself is never stored."""
    kv = dict(UNIT_RX.findall((direccion or "").upper()))
    pl, pt = kv.get("PL"), kv.get("PT")
    if pl == "OD" and pt == "OS":
        return "whole_parcel"
    if pl or pt:
        return "in_building"
    return "unknown"


def building_text(direccion):
    """Street and first street number of the address (the building), ignoring the unit part,
    punctuation and any later text: two dwellings with the same building_text in the same
    municipality are taken to be in the same building. Used at ingest only, through a salted
    hash; the text itself is never stored."""
    a = re.sub(r"\b[A-Z]{1,4}:\S*", " ", (direccion or "").upper())
    m = re.match(r"\s*([^0-9]*?)[\s,]*(\d+)", a)
    if not m:
        return re.sub(r"[^A-Z0-9ÁÉÍÓÚÑÇÀÈÒÏÜ]+", " ", a).strip()
    street = re.sub(r"[^A-ZÁÉÍÓÚÑÇÀÈÒÏÜ]+", " ", m.group(1)).strip()
    return f"{street} {int(m.group(2))}"


def parse_signatura(s):
    """'CV-VUT0999901-A' -> (999901, 'A') (synthetic example); None if the form is not recognised."""
    m = SIG_RX.match((s or "").strip())
    return (int(m.group(1)), m.group(2)) if m else None


def parse_hist_signatura(s):
    """Historical form 'VT-999904A' -> (999904, 'A') (synthetic example); 'BM' (an older Benidorm series) is
    returned as such because it does not map onto the current numbers."""
    m = HIST_RX.match((s or "").strip())
    return (int(m.group(1)), m.group(2)) if m else None


def counter_of(num, suffix):
    """Number counter a registration belongs to: each province numbers its own dwellings."""
    if suffix == "A":
        return "A" if num >= ALICANTE_NEW_COUNTER else "A-old"
    return suffix


def d(s):
    return dt.date.fromisoformat(s)


def days(a, b):
    """Inclusive range of dates from a to b."""
    out, x = [], a
    while x <= b:
        out.append(x)
        x += dt.timedelta(days=1)
    return out


def nonworking(day, holidays):
    return day.weekday() >= 5 or day in holidays


def excess(series, end, holidays, w_len=14, b_from=87, b_to=34):
    """Observed and expected counts in the window end-(w_len-1) .. end.

    Expected = sum over the window's days of the baseline mean for that day type (working /
    non-working), baseline = end-b_from .. end-b_to. series: dict date -> count (missing = 0).
    Returns dict(O, E, B, ratio) where B is the baseline total count."""
    win = days(end - dt.timedelta(days=w_len - 1), end)
    base = days(end - dt.timedelta(days=b_from), end - dt.timedelta(days=b_to))
    tot = {True: 0, False: 0}
    cnt = {True: 0, False: 0}
    for x in base:
        k = nonworking(x, holidays)
        tot[k] += series.get(x, 0)
        cnt[k] += 1
    mean = {k: (tot[k] / cnt[k] if cnt[k] else 0.0) for k in tot}
    O = sum(series.get(x, 0) for x in win)
    E = sum(mean[nonworking(x, holidays)] for x in win)
    return {"O": O, "E": E, "B": tot[True] + tot[False], "ratio": (O / E if E > 0 else float("nan"))}


def contrast_ci(a, b, scaled=True, w_len=14, b_len=54, z=1.96):
    """Ratio of two O/E ratios (a over b) with a Poisson approximate CI on the log scale.

    scaled=True is the frozen-plan variance (1/O + 1/B', B' = baseline count scaled to the
    window length; conservative). scaled=False uses the delta-method variance of log E,
    1/B (B = baseline count)."""
    def v(x):
        bb = x["B"] * (w_len / b_len) if scaled else x["B"]
        return 1 / x["O"] + 1 / bb
    lr = math.log(a["ratio"]) - math.log(b["ratio"])
    se = math.sqrt(v(a) + v(b))
    return math.exp(lr), math.exp(lr - z * se), math.exp(lr + z * se)


def ratio_of_means(post, pre, z=1.96):
    """Ratio mean(post)/mean(pre) of monthly counts, with a delta-method CI using the
    month-to-month sample variance of each period."""
    mx, my = statistics.mean(post), statistics.mean(pre)
    vx = statistics.variance(post) / (len(post) * mx * mx) if len(post) > 1 and mx > 0 else 0
    vy = statistics.variance(pre) / (len(pre) * my * my) if len(pre) > 1 and my > 0 else 0
    r = mx / my
    se = math.sqrt(vx + vy)
    return {"ratio": r, "lo": r * math.exp(-z * se), "hi": r * math.exp(z * se), "var_log": vx + vy}


def ratio_of_ratios(a, b, z=1.96):
    """(ratio a)/(ratio b) for two ratio_of_means results, variances added on the log scale."""
    r = a["ratio"] / b["ratio"]
    se = math.sqrt(a["var_log"] + b["var_log"])
    return {"ratio": r, "lo": r * math.exp(-z * se), "hi": r * math.exp(z * se)}


def gaps(entries, start):
    """entries: list of (number, date) of one counter. Every integer between two consecutive
    present numbers (>= start) is a gap; it is assigned to the date of its lower neighbour.
    Returns list of (lower_neighbour_date, n_gaps) with n_gaps > 0."""
    by_num = {}
    for n, day in entries:
        if n >= start and (n not in by_num or day < by_num[n]):
            by_num[n] = day
    nums = sorted(by_num)
    out = []
    for a, b in zip(nums, nums[1:]):
        if b - a > 1:
            out.append((by_num[a], b - a - 1))
    return out


def order_lags(entries, since):
    """Processing-order lag in days for each entry dated >= since: the latest date among
    entries with a lower number in the same counter, minus the entry's own date (0 if none
    later). entries: list of (number, date). Returns list of (number, date, lag)."""
    out, run = [], None
    for n, day in sorted(entries):
        if run is None or day > run:
            run = day
        if day >= since:
            out.append((n, day, (run - day).days))
    return out


def rank_desc(values, x):
    """1 + number of values strictly greater than x."""
    return 1 + sum(1 for v in values if v > x)
