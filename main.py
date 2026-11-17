"""Forecast GTA VI's launch-day Twitch viewers hour by hour (practice + final).

Method (rolling-midnight comparables regression, calibrated on the 4 practice
launches by leave-one-launch-out validation; see scratch/variants*.py):
  - Each comparable launch contributes its release-day hourly curve, expressed
    as log-ratios to its own hour-1 print: lr_h = ln(v_h / v_1), h = 2..24.
  - Reference class: launches whose unlock text says the launch rolled out at
    midnight local time ("rolling" / "midnight local"). Simultaneous global
    unlocks (mostly PC) have a different shape (huge hour 1, fast decay) and
    drag the fit; the rolling subset is far more homogeneous for a game that
    unlocks at rolling midnight local, which GTA VI does (RULES.txt).
  - The shape is driven by the hour-1 level: across the comparables,
    corr(ln(v_1), peak log-ratio) = -0.94. A small hour 1 means most of the
    audience (notably the US) has not unlocked yet, so the day rises steeply;
    a huge hour 1 means the audience is already there, so the day is flat or
    decays. So per hour h we fit an ordinary least squares line
    lr_h = a_h + b_h * ln(v_1) over the rolling comparables and predict at
    the target's ln(hour-1 print). The median forecast is p1 * exp(pred_h).
  - Spread: the per-hour population standard deviation of the OLS residuals
    (the launches' real dispersion around the line), mapped to the five
    levels with standard-normal quantiles. This is a calibrated spread, not
    a guessed one: on the practice it gives ~0.96 mean 90% coverage.
  - Fallbacks keep every case valid: if fewer than 6 rolling comparables are
    usable, all usable comparables are used; if none are usable, the house
    persistence baseline (spread 0.15 * sqrt(h-1)) is emitted instead.

Practice validation (leave-one-launch-out; answers re-fetched from the same
SullyGnome source the kit documents, hour-1 prints match exactly):
  mean pinball loss 0.1615 (house baseline 0.3871):
    p00 Wolverine  0.1867   p01 RDR2  0.1188
    p02 GoW        0.1209   p03 Spider-Man 2  0.2195
  The two large hour-1 launches score 0.119 / 0.121 (near the 0.140 paid
  cut); the misses are the small hour-1 launches. GTA VI's hour 1 will be
  in the large regime, but the practice mean is above the paid cut, so this
  is a BASELINE, not a claim of a paid rank.

Runs offline, standard library only, deterministic: no randomness, no
network, no time dependence. Reads $MAKEFUN_INPUT_DIR (else /input) and
writes $MAKEFUN_OUTPUT_DIR (else /output), one <id>.out per <id>.in.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the scored levels.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817,
     1.6448536269514722]
# House-baseline spread (fallback only), log units per sqrt hour.
BASE_SIGMA = 0.15


def parse_time(text):
    """ISO 8601 UTC timestamp -> aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """Round to 2 decimals, half up (same as the kit starter)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def release_day_curve(comp):
    """A comparable's release-day curve as (v1, {hour: ln(v_h / v_1)}), or None.

    Uses the points on the UTC day of the comparable's day_start. Gaps of up
    to 4 hours are log-linearly interpolated; a curve needs its hour-1 point
    and at least 23 of the 24 hours after interpolation.
    """
    t0 = parse_time(comp["day_start"])
    pts = {}
    for row in comp.get("hourly") or []:
        viewers = row.get("viewers")
        if not viewers or viewers <= 0:
            continue
        dh = (parse_time(row["from"]) - t0).total_seconds() / 3600.0
        if 0 <= dh < 24:
            pts[int(dh) + 1] = float(viewers)
    if 1 not in pts or len(pts) < 20:
        return None
    have = sorted(pts)
    full = {}
    for h in range(1, 25):
        if h in pts:
            full[h] = pts[h]
            continue
        lo = max([x for x in have if x < h], default=None)
        hi = min([x for x in have if x > h], default=None)
        if lo is None or hi is None or hi - lo > 4:
            continue
        full[h] = math.exp(
            math.log(pts[lo])
            + (math.log(pts[hi]) - math.log(pts[lo])) * (h - lo) / (hi - lo)
        )
    if len(full) < 23:
        return None
    v1 = full[1]
    return v1, {h: math.log(full[h] / v1) for h in full}


def is_rolling(comp):
    """True when the unlock text says the launch rolled out at midnight local."""
    text = (comp.get("unlock") or "").lower()
    return "rolling" in text or "midnight local" in text


def ols(xs, ys):
    """Least-squares line y = a + b*x; returns (a, b)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def forecast_case(case, name):
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))

    # Build the usable comparable curves: (hour-1 viewers, log-ratios).
    curves = []
    for comp in case.get("comparables") or []:
        # GTA VI's own pre-release category history is not a launch curve.
        if "category before release" in (comp.get("name") or ""):
            continue
        curve = release_day_curve(comp)
        if curve is None:
            continue
        curves.append((comp, curve[0], curve[1]))
    rolling = [(c, v1, lr) for c, v1, lr in curves if is_rolling(c)]
    # Rolling launches are the reference class; fall back to all launches
    # only if the rolling subset is too small to fit a line.
    pool = rolling if len(rolling) >= 6 else curves

    hours = []
    if pool:
        xs = [math.log(v1) for _, v1, _ in pool]
        # GTA VI's hour 1 will be far above past launches; the log-linear
        # relation is strong (corr -0.94) but do not extrapolate it without
        # bound -- cap the regression input half a log unit past the largest
        # comparable hour 1. The lower end is left unclamped: the smallest
        # practice launch (23,357) already sits just below the rolling
        # subset's smallest hour 1 and scores better unclamped.
        x0 = min(math.log(p1), max(xs) + 0.5)
        for row in case["forecast"]:
            h = row["hour"]
            ys = [lr[h] for _, _, lr in pool if h in lr]
            a, b = ols(xs, ys)
            pred = a + b * x0
            resid = [y - (a + b * x) for x, y in zip(xs, ys)]
            sigma = statistics.pstdev(resid) if len(resid) > 1 else BASE_SIGMA
            if sigma <= 0:
                sigma = BASE_SIGMA
            q = [round2(p1 * math.exp(pred + z * sigma)) for z in Z]
            q = [max(1, min(1_000_000_000, v)) for v in q]
            hours.append({"hour": h, "q": sorted(q)})
    else:
        # No usable comparable at all: house persistence baseline.
        for row in case["forecast"]:
            h = row["hour"]
            q = [round2(p1 * math.exp(z * BASE_SIGMA * math.sqrt(h - 1)))
                 for z in Z]
            q = [max(1, min(1_000_000_000, v)) for v in q]
            hours.append({"hour": h, "q": sorted(q)})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        out = OUTPUT_DIR / f"{path.stem}.out"
        out.write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
