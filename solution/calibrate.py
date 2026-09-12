#!/usr/bin/env python3
"""Where the bars sit, measured rather than chosen.

Generates bores with gen_bore.py across seeds and tidal phases and scores, on each, the routes an
agent is likely to take: a straight line through the readings taken during abstraction, which is
how the previous return was done; the first and last readings of the period; and a line plus one
sinusoid whose period is searched on the sampled series itself, which is the honest route without
knowing the tide; and the honest fit on the readings as written, with the measuring point move
that bore.json records never applied. The reference, which reads the period off the commissioning
dump, corrects the move and fits the tide at the sample times, is scored beside them when a
compiled class is given.

    calibrate.py [--java-out DIR] [--seeds N]
"""
import argparse
import csv
import datetime as dt
import json
import math
import pathlib
import statistics as st
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
T_M2 = 12.4206012


def lstsq(x, y):
    n, p = len(x), len(x[0])
    a = [[sum(x[i][j] * x[i][k] for i in range(n)) for k in range(p)] + [sum(x[i][j] * y[i] for i in range(n))] for j in range(p)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(a[r][c]))
        a[c], a[piv] = a[piv], a[c]
        for r in range(c + 1, p):
            f = a[r][c] / a[c][c]
            for k in range(c, p + 1):
                a[r][k] -= f * a[c][k]
    b = [0.0] * p
    for c in range(p - 1, -1, -1):
        b[c] = (a[c][p] - sum(a[c][k] * b[k] for k in range(c + 1, p))) / a[c][c]
    return b


def load(d, correct_move=True):
    """The readings, brought back onto the casing top: the export is written as measured, and from
    the stamp in bore.json the measuring point sits the offset above the casing top. With
    correct_move off the readings are taken as written, which is the route that ignores the move."""
    with open(d / "levels.csv") as fh:
        rows = [(dt.datetime.fromisoformat(r["timestamp"]), float(r["depth_m"])) for r in csv.DictReader(fh)]
    with open(d / "bore.json") as fh:
        meta = json.load(fh)
    if correct_move:
        moved = dt.datetime.fromisoformat(meta["measuring_point_moved_at"])
        off = meta["measuring_point_offset_m"]
        rows = [(t, v - (off if t >= moved else 0.0)) for t, v in rows]
    return rows, meta


def routes(d):
    rows, meta = load(d)
    ps = dt.datetime.fromisoformat(meta["abstraction_start"])
    t0 = rows[0][0]
    hrs = [(t - t0).total_seconds() / 3600 for t, _ in rows]
    pdays = [max(0.0, (t - ps).total_seconds() / 86400) for t, _ in rows]
    y = [v for _, v in rows]
    post = [i for i, (t, _) in enumerate(rows) if t >= ps]
    H = meta["projection_day"]
    # A day's figure is the mean over that day, which for a steadily falling level is the level at
    # its middle, so every projection below is taken at H + 0.5 days of abstraction.
    out = {}
    b = lstsq([[1, pdays[i]] for i in post], [y[i] for i in post])
    out["straight_line"] = (b[1] * 1000, b[0] + b[1] * (H + 0.5))
    fl = (y[post[-1]] - y[post[0]]) / (pdays[post[-1]] - pdays[post[0]])
    out["first_to_last"] = (fl * 1000, y[post[0]] + fl * (H + 0.5))
    best = None
    for tenths in range(30, 600):
        T = tenths / 10 * 24
        X = [[1, pdays[i], math.cos(2 * math.pi * hrs[i] / T), math.sin(2 * math.pi * hrs[i] / T)] for i in range(len(rows))]
        c = lstsq(X, y)
        r = sum((y[i] - sum(X[i][j] * c[j] for j in range(4))) ** 2 for i in range(len(rows)))
        if best is None or r < best[0]:
            best = (r, c)
    out["line_plus_searched_period"] = (best[1][1] * 1000, best[1][0] + best[1][1] * (H + 0.5))
    X = [[1, pdays[i], math.cos(2 * math.pi * hrs[i] / T_M2), math.sin(2 * math.pi * hrs[i] / T_M2)] for i in range(len(rows))]
    c = lstsq(X, y)
    out["line_plus_known_tide"] = (c[1] * 1000, c[0] + c[1] * (H + 0.5))
    # The same fit on the readings as written, the measuring point move in bore.json never applied:
    # the offset the later readings carry goes into the fit as a change of rate.
    raw, _ = load(d, correct_move=False)
    yr = [v for _, v in raw]
    cr = lstsq(X, yr)
    out["ignores_move"] = (cr[1] * 1000, cr[0] + cr[1] * (H + 0.5))
    # The tail-slope route: the same fit, but taking the rate from the trailing third of the
    # abstraction record instead of all of it, and carrying that rate out to the projection day.
    # The README now states the fall is steady for as long as abstraction runs, which is what
    # rules this reading out; it is scored here to show what it costs when that is ignored.
    tail = post[len(post) * 2 // 3:]
    if len(tail) >= 3:
        Xt = [[1, pdays[i], math.cos(2 * math.pi * hrs[i] / T_M2), math.sin(2 * math.pi * hrs[i] / T_M2)] for i in tail]
        ct = lstsq(Xt, [y[i] for i in tail])
        base = c[0] + c[1] * pdays[tail[0]]
        out["tail_third_slope"] = (ct[1] * 1000, base + ct[1] * (H + 0.5 - pdays[tail[0]]))
    return out, meta


def verdict(rate, depth, meta):
    return rate <= meta["licence_limit_mm_per_day"] and depth < meta["pump_intake_depth_m"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--java-out", help="directory holding a compiled Drawdown.class")
    ap.add_argument("--seeds", type=int, default=12)
    a = ap.parse_args()
    for label, extra in [("shipped bore, 12 h logger, 8 mm/day", ["--rate", "8", "--interval", "12"]),
                         ("hidden bore, daily dips, 4 mm/day", ["--rate", "4", "--interval", "24", "--hidden"]),
                         ("third bore, crosses the intake, 4 mm/day", ["--rate", "4", "--interval", "12", "--third"])]:
        res = {}
        with tempfile.TemporaryDirectory() as tmp:
            for seed in range(a.seeds):
                d = pathlib.Path(tmp) / f"s{seed}"
                subprocess.run([sys.executable, str(HERE / "gen_bore.py"), str(d / "data"), str(d), "--seed", str(seed)] + extra,
                               check=True, capture_output=True)
                with open(d / "key.json") as fh:
                    key = json.load(fh)
                rs, meta = routes(d / "data")
                if a.java_out:
                    subprocess.run(["java", "-cp", a.java_out, "Drawdown", str(d / "data"), str(d / "out.json")], check=True, capture_output=True)
                    with open(d / "out.json") as fh:
                        o = json.load(fh)
                    # The report carries no rate of its own: the contract's rate is the drawdown from
                    # the first day of abstraction to the projected depth, per day, so derive it.
                    daily = o["daily_depth_m"]
                    first = daily[min(daily)]
                    rate_out = 1000.0 * (o["projected_depth_m"] - first) / meta["projection_day"]
                    rs = {"reference": (rate_out, o["projected_depth_m"]), **rs}
                for name, (rate, depth) in rs.items():
                    res.setdefault(name, []).append((rate - key["drawdown_mm_per_day"], depth - key["projected_depth_m"],
                                                     verdict(rate, depth, meta) == key["within_licence"]))
        print(f"== {label}, {a.seeds} seeds (phase fixed, noise varies)")
        fmt = lambda v: f"{st.mean(v):7.2f} [{min(v):7.2f},{max(v):7.2f}]"
        for name, v in res.items():
            c = list(zip(*v))
            print(f"   {name:26s} rate err mm/day {fmt(c[0])}   depth err m {fmt(c[1])}   verdict right {sum(c[2])}/{len(c[2])}")


if __name__ == "__main__":
    main()
