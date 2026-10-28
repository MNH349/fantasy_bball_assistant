"""FantasyPros Average Draft Position (ADP) — market consensus cross-reference.

ADP is the market's aggregate view of where each player is drafted. We use it to
temper ESPN's rookie optimism (a raw prospect falls in ADP no matter his draft
slot) and to source position eligibility, which DARKO/nba_api don't provide.
"""
from __future__ import annotations

import io

import requests

from fba.names import normalize

ADP_URL = "https://www.fantasypros.com/nba/adp/overall.php"
# FantasyPros serves the table only to browser-like clients.
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def fetch_adp(url: str = ADP_URL, timeout: int = 30) -> dict[str, dict]:
    """Return {normalized_name: {adp, adp_rank, positions}}.

    `adp_rank` is the 1-based row order (overall consensus rank); `adp` is the
    average pick number. Returns {} on any failure so the board still builds.
    """
    import pandas as pd

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        # html5lib is pure-Python (no lxml build needed on this platform).
        tables = pd.read_html(io.StringIO(resp.text), flavor="html5lib")
    except Exception as exc:  # noqa: BLE001
        print(f"[adp] fetch/parse failed ({exc}); skipping ADP cross-check.")
        return {}

    # The player table is the widest one with a 'Player Team (Pos)' style column.
    table = max(tables, key=lambda t: t.shape[0])
    # Find the player-name column and the average column.
    name_col = next((c for c in table.columns if "player" in str(c).lower()), table.columns[1])
    avg_col = next((c for c in table.columns if str(c).lower() in ("avg", "adp")), None)

    out: dict[str, dict] = {}
    for rank, (_, row) in enumerate(table.iterrows(), start=1):
        raw = str(row[name_col])
        name, positions = _split_name_positions(raw)
        if not name:
            continue
        try:
            adp = float(row[avg_col]) if avg_col is not None else float(rank)
        except (TypeError, ValueError):
            adp = float(rank)
        out[normalize(name)] = {"adp": adp, "adp_rank": rank, "positions": positions}
    return out


def _split_name_positions(raw: str) -> tuple[str, str]:
    """Parse 'Nikola Jokic (DEN - C)' -> ('Nikola Jokic', 'C')."""
    raw = raw.strip()
    if "(" not in raw:
        return raw, ""
    name, _, tail = raw.partition("(")
    tail = tail.rstrip(") ")
    # tail looks like 'DEN - C' or 'LAL - PG,SG'
    positions = tail.split("-")[-1].strip() if "-" in tail else ""
    return name.strip(), positions
