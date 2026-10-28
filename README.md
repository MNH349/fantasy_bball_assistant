# Fantasy Basketball Assistant

Diagnostics, projections, and reports for an ESPN **H2H Points** fantasy basketball
league (league `349026539`, 2026-27 season). Helps with the draft, waiver pickups,
drop candidates, and trade targets — short-term (this/next week) and rest-of-season.

## Status

- ✅ **Phase 1 — Connect & scoring**: read the league, resolve its Points formula.
- ✅ **Phase 2 — Draft board**: rank players by projected 26-27 fantasy points
  (2025-26 stats + projected growth).
- ✅ **Phase 3 — In-season valuation**: DARKO talent blended with season-to-date
  production (K=20 confidence ramp), split into rest-of-season and this-week
  values (schedule-aware game counts).
- ✅ **Phase 4 — Daily report**: waiver upgrades (protected drops), streaming,
  risers/fallers, and a CLI trade evaluator; a daily snapshot builds history.
- 🔜 **Phase 5 — Web dashboard** over the snapshot history (daily run already live
  via launchd).

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

```bash
# Phase 1 — verify the connection and see your league snapshot + scoring formula
python scripts/diagnostics.py

# Phase 2 — build the draft cheat sheet -> reports/draft_board.{csv,md}
python scripts/draft_board.py

# Phase 3/4 — daily in-season update -> reports/inseason_latest.md (+ snapshot)
python scripts/daily_update.py

# Evaluate a proposed trade against the latest snapshot
python scripts/evaluate_trade.py \
    --give "Deni Avdija, Naz Reid, Darryn Peterson" \
    --get  "Jaden McDaniels, Anthony Black, Bam Adebayo"

# Tests (no credentials needed)
pytest
```

The draft board builds even **without** credentials (it uses a default scoring
formula and public NBA stats); connecting just swaps in your league's exact
Points values. The in-season update needs credentials (it reads your rosters).

### Run it daily (macOS launchd)

`scripts/daily_update.py` is meant to run every morning so the snapshot history
(and the trend/riser columns) fill in. A ready-made agent is in `launchd/`:

```bash
cp launchd/com.tftaddict.fba-daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tftaddict.fba-daily.plist
launchctl start com.tftaddict.fba-daily   # run once now to verify
```

It runs at 08:00 local (captures the prior night's box scores + DARKO's daily
refresh) and logs to `daily_update.log`. Your cookies never leave the machine.

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
- `fba/inseason_report.py` — the daily Markdown report.
- `scripts/` — runnable entry points (`diagnostics`, `draft_board`,
  `daily_update`, `evaluate_trade`).

## How in-season value is computed

`value_fpg = (1 − w)·DARKO_fpg + w·actual_fpg`, where `w = games / (games + 20)`.
DARKO (re-pulled daily) anchors the estimate while the sample is small; actual
production earns weight as games pile up. DARKO's rates run on each player's role
(minutes regressed from last season early on, toward season-to-date as it grows),
so role changes flow through immediately. Two horizons come out: **ROS** (per-game
× games left = durability × team games remaining) and **Week** (per-game × games
in the current Mon–Sun period; zeroed for players who are OUT). DARKO's **DPM** is
shown as a trend signal only — it never drives the fantasy-points value.

## Data sources & caveats

- **ESPN**: unofficial `espn-api` library (undocumented endpoints — no SLA).
- **NBA stats & schedule**: `nba_api` (official NBA.com data, cached to disk).
- **Projections**: DARKO talent sheet (free, updates daily).
- Early-season values lean heavily on DARKO by design — a hot/cold first week is
  mostly noise, and the blend tightens toward reality as games accumulate.
