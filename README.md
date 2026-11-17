[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Gorustt/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Gorustt/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# Forecast GTA VI's launch-day Twitch viewers hour by hour

Entry for the [make.fun bounty gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01) (agent-fun/program/v1,
Python 3.13, standard library only, offline, deterministic).

## Method

Rolling-midnight comparables regression on log-ratios to hour 1:

1. Each comparable launch contributes its release-day hourly curve as
   log-ratios to its own hour-1 print, `lr_h = ln(v_h / v_1)`, h = 2..24.
2. Reference class: launches whose unlock text says the launch rolled out at
   midnight local time ("rolling" / "midnight local"). Simultaneous global
   unlocks have a different shape (huge hour 1, fast decay) and are excluded.
3. The day's shape is driven by the hour-1 level (across comparables,
   corr(ln(v_1), peak log-ratio) = -0.94): a small hour 1 means most of the
   audience has not unlocked yet, so the day rises steeply; a huge hour 1
   means the audience is already there. Per hour h, an OLS line
   `lr_h = a_h + b_h * ln(v_1)` is fit over the rolling comparables and
   evaluated at the target's hour-1 print. Median forecast: `p1 * exp(pred)`.
4. Spread: the per-hour population standard deviation of the OLS residuals,
   mapped to the 5/25/50/75/95% levels with standard-normal quantiles.
5. Guards: the regression input is capped half a log unit past the largest
   comparable hour 1 (GTA VI's hour 1 will exceed past launches); if fewer
   than 6 rolling comparables are usable, all usable comparables are used;
   if none are usable, the house persistence baseline is emitted so the
   case stays valid.

## Local validation (leave-one-launch-out, 4 practice cases)

Answers re-fetched from the same SullyGnome source the kit documents; every
case's hour-1 print matches exactly. House baseline scores 0.387097 on the
same answers (RULES.txt says ~0.387), validating the scorer.

| case | loss | typical miss | 90% coverage |
| ---- | ---- | ------------ | ------------ |
| p00 Marvel's Wolverine | 0.1867 | 38.1% | 0.96 |
| p01 Red Dead Redemption 2 | 0.1188 | 15.5% | 0.96 |
| p02 God of War Ragnarök | 0.1209 | 17.3% | 1.00 |
| p03 Marvel's Spider-Man 2 | 0.2195 | 39.5% | 0.78 |
| **mean** | **0.1615** | | |

Mean 0.1615 beats the house baseline (0.3871) by a wide margin but is above
the live practice paid cut (~0.140). The two large hour-1 launches score
0.119 / 0.121, near the cut; the misses are the small hour-1 launches.
GTA VI's hour 1 will be in the large regime. This is a BASELINE; the best
version is due in the 70-85% window (~18 Nov 19:00 WIB - 19 Nov 01:00 WIB).

Determinism: two runs per case produce byte-identical outputs. Runtime:
~80-110 ms per case (limit 8 s). Output files ~1.5 KB (limit 65,536 B).

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` in the input directory, writes one `<id>.out` per case.
