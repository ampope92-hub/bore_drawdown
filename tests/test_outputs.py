"""Verifier for the bore's daily levels and licence projection.

test.sh compiles the agent's Java itself, runs the class once on the export that shipped and once
on each of two other bores' exports it has never seen, and captures each report root-only. This
module only reads those captures and the keys under /opt, which are what the licence check's own
10 minute logger recorded: a mean for every day of the abstraction period and for the day the
licence names. It never runs agent code.

Every bar here is stated in instruction.md, and the same bars apply to all three runs.
"""
import csv
import datetime as dt
import hashlib
import json
import math
import os
import pathlib

import pytest

SHIPPED_RUN = pathlib.Path("/opt/run_shipped.json")
HIDDEN_RUN = pathlib.Path("/opt/run_hidden.json")
THIRD_RUN = pathlib.Path("/opt/run_third.json")
SHIPPED_KEY = pathlib.Path("/opt/golden/key.json")
HIDDEN_KEY = pathlib.Path("/opt/hidden/key.json")
THIRD_KEY = pathlib.Path("/opt/third/key.json")
SHIPPED_DATA = pathlib.Path("/app/data")

# The bars from the instruction. Measured with solution/calibrate.py: a fit that carries the tide at
# the reading times is within 9 mm of every day's mean on both bores; a straight line through the
# abstraction readings, which is how the last return was done, is up to 85 mm out on the shipped
# bore and 51 mm on the other, and gets the verdict wrong on both.
DAILY_BAR_M = 0.03
DEPTH_BAR_M = 0.10

SHIPPED_SHA = {
    "levels.csv": "17b5b2c397326e440c69f78f1be90c6abf16668103ca8cb8308114ac18ca8f70",
    "commissioning_10min.csv": "1c604aabe3974c14d0897c377fea80cf0afdd538d1e5a18df06f477e28719298",
    "bore.json": "dd681b24bbbd3a1834c3f7b67e20526fbec52040083628d6f18dd4a7dab8a013",
    "README.md": "9cdc0a57ef3ecf0455aab35242a8f23ab5183fc2b119a3202ab9b5fee8e4f67f",
}

# Each key beside the export it was computed from, for the checks that read the licence settings.
KEY_TO_DATA = {
    SHIPPED_KEY: SHIPPED_DATA,
    HIDDEN_KEY: pathlib.Path("/opt/hidden/data"),
    THIRD_KEY: pathlib.Path("/opt/third/data"),
}

RUNS = [
    pytest.param(SHIPPED_RUN, SHIPPED_KEY, id="shipped"),
    pytest.param(HIDDEN_RUN, HIDDEN_KEY, id="hidden"),
    pytest.param(THIRD_RUN, THIRD_KEY, id="third"),
]


def _open(path, mode="r"):
    """Open without following a final symlink, so a read can never be redirected into /opt."""
    return os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), mode)


def _sha(path):
    with _open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _load(path):
    assert path.exists() and path.stat().st_size > 0, (
        f"{path.name}: no drawdown.json was written for this run"
    )
    with _open(path) as fh:
        text = fh.read()
    def _no_repeats(pairs):
        seen = [k for k, _ in pairs]
        dupes = sorted({k for k in seen if seen.count(k) > 1})
        if dupes:
            pytest.fail(f"{path.name}: the report names {dupes} more than once in one object")
        return dict(pairs)

    try:
        return json.loads(text, object_pairs_hook=_no_repeats)
    except json.JSONDecodeError as e:
        pytest.fail(f"{path.name}: not valid JSON ({e}): {text[:200]!r}")


def _key(path):
    with open(path) as fh:
        return json.load(fh)


def _number(v):
    """A finite JSON number; a bool is not one."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def test_shipped_export_unmodified():
    """The four files in /app/data are byte-identical to what shipped."""
    for name, sha in SHIPPED_SHA.items():
        assert _sha(SHIPPED_DATA / name) == sha, f"{name} was altered"


@pytest.mark.parametrize("run_path,key_path", RUNS)
def test_report_shape(run_path, key_path):
    """One object with exactly the five keys: daily_depth_m keyed by every day of the abstraction
    period in the record and no others, a finite projected depth, a drawdown rate, a tidal period,
    and a boolean verdict."""
    r = _load(run_path)
    key = _key(key_path)
    assert isinstance(r, dict) and set(r) == {
        "daily_depth_m", "projected_depth_m", "drawdown_mm_per_day", "tidal_period_h", "within_licence"
    }, (
        f"{run_path.name}: expected exactly the keys daily_depth_m, projected_depth_m, "
        f"drawdown_mm_per_day, tidal_period_h, within_licence"
    )
    assert isinstance(r["daily_depth_m"], dict), f"{run_path.name}: daily_depth_m is not an object"
    missing = sorted(set(key["daily_depth_m"]) - set(r["daily_depth_m"]))
    extra = sorted(set(r["daily_depth_m"]) - set(key["daily_depth_m"]))
    assert not missing, f"{run_path.name}: {len(missing)} days of the abstraction period have no level, e.g. {missing[:4]}"
    assert not extra, f"{run_path.name}: {len(extra)} days are outside the abstraction period in the record, e.g. {extra[:4]}"
    for day, v in r["daily_depth_m"].items():
        assert _number(v), f"{run_path.name}: daily_depth_m for {day} is not a finite number"
    assert _number(r["projected_depth_m"]), f"{run_path.name}: projected_depth_m is not a finite number"
    assert _number(r["drawdown_mm_per_day"]), f"{run_path.name}: drawdown_mm_per_day is not a finite number"
    assert _number(r["tidal_period_h"]) and r["tidal_period_h"] > 0, (
        f"{run_path.name}: tidal_period_h is not a positive finite number"
    )
    assert isinstance(r["within_licence"], bool), f"{run_path.name}: within_licence is not true or false"


@pytest.mark.parametrize("run_path,key_path", RUNS)
def test_daily_levels(run_path, key_path):
    """Every day's level is within 0.03 m of the mean the licence logger recorded for that day."""
    got = _load(run_path)["daily_depth_m"]
    truth = _key(key_path)["daily_depth_m"]
    worst = max(truth, key=lambda d: abs(got[d] - truth[d]))
    err = abs(got[worst] - truth[worst])
    assert err <= DAILY_BAR_M, (
        f"{run_path.name}: on {worst} the level is {got[worst]:.3f} against the logger's day mean of "
        f"{truth[worst]:.3f}, {err:.3f} m out, more than {DAILY_BAR_M:.2f}. The readings carry the tide"
    )


@pytest.mark.parametrize("run_path,key_path", RUNS)
def test_projected_depth(run_path, key_path):
    """The projected depth on the licence's day is within 0.10 m of that day's mean."""
    got = _load(run_path)["projected_depth_m"]
    truth = _key(key_path)["projected_depth_m"]
    assert abs(got - truth) <= DEPTH_BAR_M, (
        f"{run_path.name}: projected_depth_m is {got:.3f}, more than {DEPTH_BAR_M:.2f} m from the "
        f"{truth:.3f} the logger recorded that day"
    )


@pytest.mark.parametrize("run_path,key_path", RUNS)
def test_verdict(run_path, key_path):
    """The licence verdict agrees with the check."""
    got = _load(run_path)["within_licence"]
    truth = _key(key_path)["within_licence"]
    assert got == truth, (
        f"{run_path.name}: within_licence is {got}, the check found the bore "
        f"{'inside' if truth else 'outside'} its licence"
    )


# The verdict is graded against the check's own, and every bore is kept clear of both licence
# limits by more than the rate and depth bars above, so a report inside every bar lands on the
# same side of the licence as the check did: no in-tolerance estimate can flip it, and the
# instruction states the same fact.
# How far the reported tidal period may sit from the one the verifier reads off the same
# commissioning dump. Two independent fits of that dump agree to 0.0006 h on all three bores, so
# this is about eighty times the disagreement between honest implementations, while still refusing
# a period written into the source: the principal lunar period is 0.48 h from the third bore's and
# 0.59 h from the second bore's.
TIDAL_PERIOD_BAR_H = 0.15


def _period_from_dump(data_dir):
    """Read the tidal period off that export's commissioning dump, independently of the agent.

    This is deliberately not compared against anything held back. The dump ships in the export the
    run was handed, so the period is fixed by bytes the candidate can read, and the check is that
    the reported figure is the one those bytes carry rather than one carried in from elsewhere.
    """
    with open(data_dir / "commissioning_10min.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    t0 = dt.datetime.fromisoformat(rows[0]["timestamp"])
    hours = [(dt.datetime.fromisoformat(r["timestamp"]) - t0).total_seconds() / 3600.0 for r in rows]
    depth = [float(r["depth_m"]) for r in rows]
    n = len(depth)

    def rss(period):
        cos = [math.cos(2 * math.pi * h / period) for h in hours]
        sin = [math.sin(2 * math.pi * h / period) for h in hours]
        cols = [[1.0] * n, cos, sin]
        a = [[sum(cols[i][k] * cols[j][k] for k in range(n)) for j in range(3)] for i in range(3)]
        rhs = [sum(cols[i][k] * depth[k] for k in range(n)) for i in range(3)]
        m = [a[i] + [rhs[i]] for i in range(3)]
        for i in range(3):
            piv = max(range(i, 3), key=lambda r: abs(m[r][i]))
            m[i], m[piv] = m[piv], m[i]
            for r in range(3):
                if r != i and m[i][i]:
                    f = m[r][i] / m[i][i]
                    for c in range(i, 4):
                        m[r][c] -= f * m[i][c]
        co = [m[i][3] / m[i][i] if m[i][i] else 0.0 for i in range(3)]
        return sum((depth[k] - (co[0] + co[1] * cos[k] + co[2] * sin[k])) ** 2 for k in range(n))

    step = hours[1] - hours[0]
    lo, hi = 4 * step, hours[-1] / 2
    best, best_r = lo, float("inf")
    t = lo
    while t <= hi:
        r = rss(t)
        if r < best_r:
            best_r, best = r, t
        t += 0.002
    t = best - 0.002
    stop = best + 0.002
    while t <= stop:
        r = rss(t)
        if r < best_r:
            best_r, best = r, t
        t += 0.00002
    return best


@pytest.mark.parametrize("run_path,key_path", RUNS)
def test_tidal_period_is_the_one_the_dump_carries(run_path, key_path):
    """The reported tidal period matches the one the verifier reads off that export's own
    commissioning dump, so the period has to come from the bore in front of the program."""
    got = _load(run_path)["tidal_period_h"]
    expected = _period_from_dump(KEY_TO_DATA[key_path])
    assert abs(got - expected) <= TIDAL_PERIOD_BAR_H, (
        f"{run_path.name}: tidal_period_h is {got:.4f} h, {abs(got - expected):.4f} h from the "
        f"{expected:.4f} h this bore's commissioning dump carries, more than {TIDAL_PERIOD_BAR_H}. "
        f"Each bore breathes at its own period and the dump is where it is read off"
    )


@pytest.mark.parametrize("run_path,key_path", RUNS)
def test_drawdown_rate(run_path, key_path):
    """The reported drawdown rate matches the licence check's, within what the depth bars allow
    over the projection."""
    got = _load(run_path)["drawdown_mm_per_day"]
    key = _key(key_path)
    truth = key["drawdown_mm_per_day"]
    with open(KEY_TO_DATA[key_path] / "bore.json") as fh:
        horizon = json.load(fh)["projection_day"]
    bar = _rate_clearance_needed(horizon)
    assert abs(got - truth) <= bar, (
        f"{run_path.name}: drawdown_mm_per_day is {got:.3f} against the check's {truth:.3f}, "
        f"{abs(got - truth):.3f} mm/day out, more than the {bar:.3f} the depth bars allow over "
        f"{horizon} days"
    )


# The rate is the drop over the projection, so an implementation sitting on both depth bars can be
# out by (DAILY_BAR_M + DEPTH_BAR_M) metres over projection_day days. Anything less than that
# between the audit rate and the licence limit would let a report inside every stated bar be graded
# wrong on the verdict, so the clearance each bore needs is worked out from the bars themselves.
def _rate_clearance_needed(projection_day):
    return 1000.0 * (DAILY_BAR_M + DEPTH_BAR_M) / projection_day


