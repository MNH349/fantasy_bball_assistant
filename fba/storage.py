"""Daily snapshot store (SQLite).

The in-season engine re-values every player each morning. Persisting those daily
snapshots is what turns point-in-time projections into *trends*: DARKO DPM
drifting up, minutes jumping after a role change, actual FP/G pulling away from
the preseason prior. One SQLite file, one row per (date, player). The valuation
math lives elsewhere; this module only reads and writes.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Iterator, Sequence

from config import DATA_CACHE_DIR, HISTORY_DB

# One row per player per day, keyed by (snapshot_date, name). Columns mirror an
# in-season valuation record so a snapshot round-trips without transformation.
COLUMNS = (
    "name", "nba_id", "pro_team", "rostered_by", "injury",
    "dpm",          # DARKO DPM — trend signal only, never drives value
    "minutes",      # season-to-date minutes per game (role)
    "usg",          # season-to-date usage (role)
    "actual_fpg",   # season-to-date fantasy points per game, league scoring
    "darko_fpg",    # DARKO rates x current role, league scoring
    "value_fpg",    # blended in-season per-game value (the K=20 hybrid)
    "games_left",   # projected games remaining this season
    "value_ros",    # value_fpg x games_left
    "games_week",   # NBA games in the current scoring period
    "value_week",   # value_fpg x games_week
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS player_snapshots (
    snapshot_date TEXT NOT NULL,
    name          TEXT NOT NULL,
    nba_id        INTEGER,
    pro_team      TEXT,
    rostered_by   TEXT,
    injury        TEXT,
    dpm           REAL,
    minutes       REAL,
    usg           REAL,
    actual_fpg    REAL,
    darko_fpg     REAL,
    value_fpg     REAL,
    games_left    REAL,
    value_ros     REAL,
    games_week    INTEGER,
    value_week    REAL,
    PRIMARY KEY (snapshot_date, name)
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a connection to the history DB, creating the schema if needed."""
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_snapshot(rows: Sequence[dict], snapshot_date: str | None = None) -> str:
    """Upsert a day's player rows. Re-running the same day overwrites it.

    Each row is a dict; any missing column is stored NULL. Returns the date used.
    """
    day = snapshot_date or date.today().isoformat()
    cols = ("snapshot_date", *COLUMNS)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT OR REPLACE INTO player_snapshots ({', '.join(cols)}) VALUES ({placeholders})"
    with connect() as conn:
        conn.executemany(
            sql, [(day, *(r.get(c) for c in COLUMNS)) for r in rows]
        )
    return day


def latest_date() -> str | None:
    """Most recent snapshot date, or None if the store is empty."""
    with connect() as conn:
        row = conn.execute("SELECT MAX(snapshot_date) AS d FROM player_snapshots").fetchone()
    return row["d"] if row and row["d"] else None


def load_snapshot(snapshot_date: str | None = None) -> list[dict]:
    """All player rows for a date (default: the latest snapshot)."""
    day = snapshot_date or latest_date()
    if day is None:
        return []
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM player_snapshots WHERE snapshot_date = ? ORDER BY value_ros DESC",
            (day,),
        ).fetchall()
    return [dict(r) for r in rows]


def player_history(name: str, days: int = 30) -> list[dict]:
    """A single player's recent snapshots, oldest first (for trend plots)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM player_snapshots WHERE name = ? "
            "ORDER BY snapshot_date DESC LIMIT ?",
            (name, days),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def snapshot_dates() -> list[str]:
    """All snapshot dates, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT snapshot_date FROM player_snapshots ORDER BY snapshot_date"
        ).fetchall()
    return [r["snapshot_date"] for r in rows]
