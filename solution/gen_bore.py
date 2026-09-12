#!/usr/bin/env python3
"""Generate a coastal bore's water-level export and the answer key.

Depth to water below the casing top, in metres. Before abstraction starts the level is flat;
from the start of continuous abstraction it deepens at a fixed rate. On top of that the bore
breathes with the estuary: the semidiurnal tide, period 12.4206 h, reaches it at a fraction of
its range. The compliance logger samples every `--interval` hours, which is longer than half the
tidal period, so what it records is the tide folded down to a slow swing. A short high-resolution
file from commissioning is written too, with the tide visible as it is.

    gen_bore.py <out-dir> <key-dir> [--seed N] [--rate MM_PER_DAY] [--interval H] [--hidden]

Standard library only.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import random

T_M2 = 12.4206012   # hours, principal lunar semidiurnal constituent
UTC = dt.timezone.utc  # the export is written in local standard time, with no zone on the stamps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("key_dir")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--rate", type=float, default=8.0, help="drawdown during abstraction, mm/day")
    ap.add_argument("--interval", type=float, default=12.0, help="logger interval, hours")
    ap.add_argument("--hidden", action="store_true")
    ap.add_argument("--third", action="store_true")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    if a.third:
        # A bore whose drawdown rate is comfortably inside the licence but whose water level is
        # already close to the pump intake, so the projection crosses it. The compliance record
        # also ends earlier in the day than abstraction began, which is the ordinary case whenever
        # the logger interval does not divide the day the same way the pump start does.
        bore, start = "MW-22", dt.datetime(2025, 5, 5, 18, 0, tzinfo=UTC)
        pump_start = start + dt.timedelta(days=12)
        span_days, amp, d0, noise = 30.5, 1.00, 6.85, 0.003
        limit_mm_day, intake_m, horizon_days = 6.0, 6.90, 120
        phase = 1.9
        # A tidal creek rather than the open estuary: the bore breathes with a period of its own,
        # so a reader who writes the principal lunar constituent into the source rather than
        # taking the period off the commissioning dump mis-folds the swing here.
        period_h = 12.9014
    elif a.hidden:
        bore, start = "MW-14", dt.datetime(2025, 3, 2, 6, 0, tzinfo=UTC)
        pump_start = start + dt.timedelta(days=12)
        span_days, amp, d0, noise = 30.0, 0.17, 4.62, 0.003
        limit_mm_day, intake_m, horizon_days = 2.4, 7.10, 120
        phase = 0.2
        period_h = 11.8271
    else:
        bore, start = "PB-07", dt.datetime(2025, 7, 20, 0, 0, tzinfo=UTC)
        pump_start = start + dt.timedelta(days=15)
        span_days, amp, d0, noise = 33.0, 0.22, 5.31, 0.003
        limit_mm_day, intake_m, horizon_days = 9.8, 7.80, 90
        phase = 1.8
        period_h = T_M2

    # The contractor runs the 10 minute dump in the days before the compliance record opens, so a
    # tidal term read off it does not have to be carried across months to reach the abstraction.
    hires_start = start - dt.timedelta(days=5)

    rate_m_day = a.rate / 1000.0
    # phase is anchored to a fixed epoch so the high-resolution file and the compliance file agree
    epoch = dt.datetime(2024, 1, 1, tzinfo=UTC)

    def depth(t, with_noise=True):
        h = (t - epoch).total_seconds() / 3600.0
        pump_days = max(0.0, (t - pump_start).total_seconds() / 86400.0)
        v = d0 + rate_m_day * pump_days + amp * math.cos(2 * math.pi * h / period_h + phase)
        return v + (rng.gauss(0.0, noise) if with_noise else 0.0)

    out = pathlib.Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    kd = pathlib.Path(a.key_dir); kd.mkdir(parents=True, exist_ok=True)

    # compliance logger
    n = int(span_days * 24 / a.interval) + 1
    with open(out / "levels.csv", "w") as fh:
        fh.write("timestamp,depth_m\n")
        for i in range(n):
            t = start + dt.timedelta(hours=i * a.interval)
            fh.write(f"{t.strftime('%Y-%m-%dT%H:%M')},{depth(t):.3f}\n")
    # commissioning dump, 10 minute samples over three days, no abstraction
    with open(out / "commissioning_10min.csv", "w") as fh:
        fh.write("timestamp,depth_m\n")
        for i in range(3 * 24 * 6 + 1):
            t = hires_start + dt.timedelta(minutes=10 * i)
            h = (t - epoch).total_seconds() / 3600.0
            v = d0 - 0.04 + amp * math.cos(2 * math.pi * h / period_h + phase) + rng.gauss(0.0, noise)
            fh.write(f"{t.strftime('%Y-%m-%dT%H:%M')},{v:.3f}\n")
    with open(out / "bore.json", "w") as fh:
        json.dump({"bore": bore, "abstraction_start": pump_start.strftime("%Y-%m-%dT%H:%M"),
                   "licence_limit_mm_per_day": limit_mm_day,
                   "pump_intake_depth_m": intake_m, "projection_day": horizon_days}, fh, indent=1)
        fh.write("\n")

    # the licence check as it was actually done: the contractor's 10 minute logger went back on the
    # bore for the day the licence names and stayed on through the abstraction period, and the regulator
    # takes each day's mean, which averages the tide out, and the rate between the two
    rng_check = random.Random(a.seed * 7919 + 1)

    def day_mean(day_start):
        vals = []
        for i in range(144):
            t = day_start + dt.timedelta(minutes=10 * i)
            h = (t - epoch).total_seconds() / 3600.0
            pump_days = max(0.0, (t - pump_start).total_seconds() / 86400.0)
            vals.append(d0 + rate_m_day * pump_days + amp * math.cos(2 * math.pi * h / period_h + phase) + rng_check.gauss(0.0, noise))
        return sum(vals) / len(vals)

    depth_start = day_mean(pump_start)
    depth_check = day_mean(pump_start + dt.timedelta(days=horizon_days))
    rate_checked = 1000.0 * (depth_check - depth_start) / horizon_days
    # the logger stayed on the bore through the abstraction period, so every day of it has a mean
    last = start + dt.timedelta(hours=(n - 1) * a.interval)
    daily = {}
    day = pump_start
    while day.date() <= last.date():
        daily[day.strftime("%Y-%m-%d")] = round(day_mean(day), 4)
        day += dt.timedelta(days=1)
    key = {"daily_depth_m": daily, "projected_depth_m": round(depth_check, 4),
           "within_licence": bool(rate_checked <= limit_mm_day and depth_check < intake_m),
           "drawdown_mm_per_day": round(rate_checked, 3),
           "tidal_period_h": round(period_h, 4)}
    with open(kd / "key.json", "w") as fh:
        json.dump(key, fh, indent=1)
        fh.write("\n")
    print(f"{bore}: {n} samples every {a.interval} h from {start:%Y-%m-%d %H:%M}, abstraction from "
          f"{pump_start:%Y-%m-%d %H:%M}, tide amplitude {amp} m, true rate {a.rate} mm/day; the check found "
          f"{rate_checked:.2f} mm/day and {depth_check:.3f} m at day {horizon_days} (intake {intake_m}), within_licence={key['within_licence']}")


if __name__ == "__main__":
    main()
