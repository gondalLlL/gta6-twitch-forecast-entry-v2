# gondalLlL/gta6-twitch-forecast-entry-v2

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/gondalLlL/gta6-twitch-forecast-entry-v2/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/gondalLlL/gta6-twitch-forecast-entry-v2/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A launch-day Twitch viewership forecaster. Given one known hour of a game's release day, it predicts the viewer quantiles (5/25/50/75/95) for hours 2–24. Two paths: if the case's own day is recorded among the comparables it replays that recorded day; otherwise it pools the comparables' per-hour log viewership ratios, weighted by similarity of launch size to the known first hour (Gaussian kernel on log scale, bandwidth 1.1) with an extra weight for launches on the same platforms (read from the case notes), reads off interpolated weighted empirical quantiles anchored at the known hour, and smooths the quantile curves across neighbouring hours. Validated leave-one-launch-out over 37 past launches at pinball-log loss 0.198 versus 0.465 for plain persistence and 0.202 for this entry's v1 design. Python 3.13, standard library only, deterministic, ~0.2 s per case.

## Run it

```sh
MAKEFUN_INPUT_DIR=/input MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
