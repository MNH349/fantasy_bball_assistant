"""Central configuration. Loads settings from a git-ignored `.env` file.

Nothing sensitive is hard-coded here — auth cookies live only in `.env`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    league_id: int
    season: int
    espn_s2: str | None
    swid: str | None

    @property
    def has_credentials(self) -> bool:
        return bool(self.espn_s2) and bool(self.swid)


def load_config() -> Config:
    return Config(
        league_id=int(os.getenv("LEAGUE_ID", "349026539")),
        season=int(os.getenv("SEASON", "2027")),
        espn_s2=os.getenv("ESPN_S2") or None,
        swid=os.getenv("SWID") or None,
    )


def require_credentials(cfg: Config) -> None:
    """Raise a friendly error if the private-league cookies are missing."""
    if not cfg.has_credentials:
        raise SystemExit(
            "Missing ESPN credentials.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Fill in ESPN_S2 and SWID (see the comments in .env.example)\n"
            "These are required to read a private league."
        )
