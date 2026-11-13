# Fantasy Basketball Assistant

Diagnostics, projections, and reports for an ESPN **H2H Points** fantasy basketball
league (league `349026539`, 2026-27 season). Helps with the draft, waiver pickups,
drop candidates, and trade targets — short-term (this/next week) and rest-of-season.

## Status

- ✅ **Phase 1 — Connect & scoring**: read the league, resolve its Points formula.
- ✅ **Phase 2 — Draft board**: rank players by projected 26-27 fantasy points
  (2025-26 stats + projected growth).
- ✅ **Phase 3 — In-season valuation**: DARKO talent blended with season-to-date
  production (K=5 confidence ramp), split into rest-of-season and this-week
  values (schedule-aware game counts).
- ✅ **Phase 4 — Daily report**: a week-long streaming plan within the 7-adds
  limit, core ROS upgrades, a trade finder + evaluator, and a weekly top 100.
- ✅ **Phase 5 — Dashboard**: always-on Streamlit app on this Mac, reachable from
  your phone through Tailscale.

Only players on **standard NBA contracts** are considered (no two-way, 10-day,
G-League or unsigned players), and lists focus on the **top 120** by
rest-of-season value plus a **watch list** of fast climbers just below it.

## Setup

```bash
cd fantasy_bball_assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configure your league (auth cookies)

Your ESPN league is private, so the tool needs two login cookies. **These are
secrets — they go only in `.env`, which is git-ignored.**

1. Copy the template: `cp .env.example .env`
2. Log into [fantasy.espn.com](https://fantasy.espn.com) in your browser.
3. Open DevTools (F12) → **Application/Storage → Cookies → https://fantasy.espn.com**.
4. Copy the **values** of `espn_s2` (a long string) and `SWID` (`{....}`) into `.env`.

> `espn_s2` expires roughly once a year. If the tool stops connecting, refresh
> these two values first — it's the most common breakage.

## Run

Everything below runs automatically; these are for doing it by hand.

```bash
# Daily update -> reports/inseason_latest.md, the snapshot, and (Mondays) the top 100
venv/bin/python scripts/daily_update.py

# Grade any trade (same two-way check as the trade finder)
venv/bin/python scripts/evaluate_trade.py --give "Zion Williamson" --get "AJ Dybantsa"

# Dashboard by hand (normally the launchd agent keeps it running)
venv/bin/streamlit run dashboard.py

# Preseason tools
venv/bin/python scripts/diagnostics.py      # check the league connection
venv/bin/python scripts/draft_board.py      # draft cheat sheet

# Tests (no credentials needed)
venv/bin/python -m pytest
```

### What runs on its own (macOS launchd)

| Agent | What it does |
|---|---|
| `com.tftaddict.fba-daily` | 08:00 every day: values everyone, plans the week's streaming moves, finds trades, writes reports. Logs to `daily_update.log`. |
| `com.tftaddict.fba-dashboard` | Keeps the dashboard running at <http://127.0.0.1:8501> (this Mac only). Logs to `dashboard.log`. |

Install (or reinstall after moving the project):

```bash
cp launchd/*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tftaddict.fba-daily.plist
launchctl load ~/Library/LaunchAgents/com.tftaddict.fba-dashboard.plist
```

If the Mac is shut down at 08:00 that day's run is skipped; the dashboard runs it
automatically the next time you open it (or click **Refresh now**).

### Untouchables

To keep players out of trade suggestions, list them one per line in
`untouchables.txt` at the project root. It's gitignored — this repo is public and
the list is strategy.

### Dashboard on your phone (Tailscale)

The dashboard only listens on this Mac. Tailscale connects your own signed-in
devices privately, so your phone can open it from anywhere without exposing it to
the internet or your Wi-Fi network.

1. Install **Tailscale** on the Mac (Mac App Store or tailscale.com/download) and
   sign in. In its menu-bar settings, turn on the command-line tool.
2. Install **Tailscale** on your phone and sign in with the **same account**.
3. On the Mac, run once:
   ```bash
   tailscale serve --bg 8501
   ```
   The first time, it may print a link to turn on HTTPS for your tailnet — open
   it, approve, and run the command again. It prints your dashboard address,
   like `https://<mac-name>.<tailnet>.ts.net`.
4. On the phone (Tailscale on), open that address and **Add to Home Screen**.

Check it with `tailscale serve status`; turn it off with `tailscale serve reset`.
The Mac has to be on and awake for the phone to reach it.

## Layout

- `config.py` — loads `.env`; paths (reports, cache, `history.db`).
- `fba/scoring.py` — the Points scoring engine (the backbone).
- `fba/espn_client.py` — league connection, rosters, snapshots, injuries.
- `fba/stats_nba.py` — nba_api stats + games history + team tricodes (cached).
- `fba/projections.py` — DARKO talent ingest + age-curve fallback.
- `fba/draft.py` / `fba/report.py` — the preseason ranked draft board.
- `fba/inseason.py` — in-season valuation (DARKO × role + production blend).
- `fba/schedule.py` — NBA schedule → games per period / remaining.
- `fba/availability.py` — career-based games-played (durability) model.
- `fba/storage.py` — SQLite daily snapshot store (`data_cache/history.db`).
- `fba/contracts.py` — who's on a standard NBA contract (all 30 rosters, daily).
- `fba/ranking.py` — weekly top 100, watch list and fallers.
- `fba/tonight.py` — single-game projections (teammates out, form, pace).
- `fba/planner.py` — the week's streaming plan within the adds limit.
- `fba/trades.py` — two-way trade assessment and the trade finder.
- `fba/inseason_report.py` — the daily report and the weekly top 100.
- `dashboard.py` — the Streamlit dashboard.
- `scripts/` — runnable entry points (`diagnostics`, `draft_board`,
  `daily_update`, `evaluate_trade`).

## How in-season value is computed

`value_fpg = (1 − w)·DARKO_fpg + w·actual_fpg`, where `w = games / (games + 5)`.
DARKO (re-pulled daily) anchors the estimate while the sample is small; actual
production earns weight as games pile up. DARKO's rates run on each player's role:
minutes regress toward last season on a short 5-game ramp, so role changes show up
within a couple of weeks. Rookies (no DARKO) use ESPN's preseason projection as
the prior on the same K=5 ramp. Two horizons come out: **ROS** (per-game
× games left = durability × team games remaining, with durability counted at half
strength so injury history can't outweigh per-game production) and **Week** (per-game × games
in the current Mon–Sun period; zeroed for players who are OUT). DARKO's **DPM** is
shown as a trend signal only — it never drives the fantasy-points value.

**Streaming plan.** Your 2 lowest players (average rank of FP/G and ROS) are
streamer spots; core spots only change for ROS upgrades. Each night is projected
per player (FP/G adjusted for half of injured teammates' minutes and for opponent
pace). The planner maps your open starting slots night by night and picks the
pickups that add the most lineup points through Sunday within the 7 adds per
matchup, each worth at least +8 points. OUT core players go to IR first.

**Trades.** Each trade is judged on our ROS value for you (+3% to +15%) and on
ESPN's season averages for them (no worse than −2%). An open roster spot counts
as the lesser of the best free agent and whoever you'd otherwise cut for him.

## Data sources & caveats

- **ESPN**: unofficial `espn-api` library (undocumented endpoints — no SLA).
- **NBA stats & schedule**: `nba_api` (official NBA.com data, cached to disk).
- **Projections**: DARKO talent sheet (free, updates daily).
- Early-season values lean heavily on DARKO by design — a hot/cold first week is
  mostly noise, and the blend tightens toward reality as games accumulate.
