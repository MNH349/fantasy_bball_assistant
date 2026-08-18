# Fantasy Basketball Assistant

Diagnostics, projections, and reports for an ESPN **H2H Points** fantasy basketball
league (league `349026539`, 2026-27 season). Helps with the draft, waiver pickups,
drop candidates, and trade targets — short-term (this/next week) and rest-of-season.

## Status

- ✅ **Phase 1 — Connect & scoring**: read the league, resolve its Points formula.
- ✅ **Phase 2 — Draft board**: rank players by projected 26-27 fantasy points
  (2025-26 stats + projected growth). *Time-critical: draft is ~Sept 2026.*
- 🔜 **Phase 3 — In-season projections** (DARKO ROS/next-game + games-per-week).
- 🔜 **Phase 4 — Pickups / drops / trade targets** reports.
- 🔜 **Phase 5 — Web dashboard + weekly scheduled run.**

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

# Tests (no credentials needed)
pytest
```

The draft board builds even **without** credentials (it uses a default scoring
formula and public NBA stats); connecting just swaps in your league's exact
Points values.

## Layout

- `config.py` — loads `.env`.
- `fba/scoring.py` — the Points scoring engine (the backbone).
- `fba/espn_client.py` — league connection + snapshots.
- `fba/stats_nba.py` — 2025-26 baseline stats (nba_api, cached to `data_cache/`).
- `fba/projections.py` — growth model + (later) DARKO ingest.
- `fba/draft.py` — the ranked draft board.
- `fba/recommend.py`, `fba/report.py` — in-season logic (Phases 3–4).
- `scripts/` — runnable entry points.

## Data sources & caveats

- **ESPN**: unofficial `espn-api` library (undocumented endpoints — no SLA).
- **NBA stats**: `nba_api` (official NBA.com data, cached to disk).
- **Projections**: DARKO (free) once wired; age-curve baseline until then.
