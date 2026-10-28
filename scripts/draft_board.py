"""Build the 2026-27 draft board.

Run:  python scripts/draft_board.py

Pipeline: DARKO talent projections (per-100 rates x last-season minutes) ->
team-context crowding adjustment -> career-availability season value -> a
reliability-scaled blend with ESPN's projection (vets 0.7, sophomores 0.3,
rookies ESPN-only) -> ESPN-only rookies added with an ADP downward cap + bust
discount -> ranked by projected season value. Retired/inactive players (no ESPN
projection) are dropped, but an above-replacement player with no ESPN match is
flagged rather than silently deleted.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import REPORTS_DIR, load_config  # noqa: E402
from fba import (  # noqa: E402
    adp as adp_mod, blend, draft, espn_client, names, projections, report,
    scoring, stats_nba, team_context,
)

# A DARKO player above this projected season value with no ESPN match is flagged
# (likely a name-mismatched active), not silently dropped.
REPLACEMENT_VALUE = 1100.0


def resolve_scoring(cfg) -> dict:
    if cfg.has_credentials:
        print("Reading live league scoring formula ...")
        return espn_client.fetch_scoring_formula(cfg)
    print("No credentials set; using DEFAULT_SCORING (connect to use your league's).")
    return dict(scoring.DEFAULT_SCORING)


def build_records(baseline, darko, current_teams, gp_history) -> list[dict]:
    """DARKO projection records with team, usage, and career games history."""
    baseline_by_id = {rec["player_id"]: rec for rec in baseline}
    records = []
    for nba_id, d in darko.items():
        base = baseline_by_id.get(nba_id)
        minutes = base["line"].get("MIN", 0.0) if base else 0.0
        if not minutes:
            minutes = d["darko_minutes"]
        records.append(
            {
                "name": d["name"],
                "age": d["age"],
                "team": current_teams.get(d["name"]),
                "usg": d["rates"].get("usg_pct", 0.0),
                "gp_history": gp_history.get(nba_id, []),
                "proj_line": projections.darko_line(d["rates"], minutes),
            }
        )
    return records


def _apply_team_context(records: list[dict], formula: dict) -> None:
    before = {r["name"]: scoring.fantasy_points(r["proj_line"], formula) for r in records}
    team_context.adjust(records)
    movers = sorted(
        (
            (scoring.fantasy_points(r["proj_line"], formula) - before[r["name"]], r["name"], r.get("team"))
            for r in records
        )
    )
    faded = [m for m in movers if m[0] < -0.05]
    print(f"  Team-context: {len(faded)} faded. Biggest: "
          + ", ".join(f"{n} ({t},{d:.0f})" for d, n, t in faded[:5]))


def _index_espn(espn: dict[str, dict]) -> dict[str, dict]:
    """Index ESPN projections by normalized name, with overall ESPN rank added."""
    by_norm = {}
    for name, payload in espn.items():
        if not payload.get("espn_proj_total"):
            continue
        norm = names.normalize(name)
        by_norm.setdefault(norm, {**payload, "name": name, "norm": norm})
    ranked = sorted(by_norm.values(), key=lambda p: p["espn_proj_total"], reverse=True)
    for i, p in enumerate(ranked, start=1):
        p["espn_rank"] = i
    return by_norm


def blend_board(darko_rows, espn_by_norm, adp_index, nba_history):
    """Blend DARKO rows with ESPN, add ESPN-only players, return (rows, flagged).

    An ESPN-only player is a true 2026 rookie only if he has NO NBA history;
    one who *does* (e.g. a star who missed last season injured, so DARKO dropped
    him) is a returning veteran and must not take the rookie bust discount.
    """
    espn_matcher = names.Matcher(espn_by_norm)
    adp_matcher = names.Matcher(adp_index)
    rows, flagged, consumed = [], [], set()

    for r in darko_rows:
        hit = espn_matcher.get(r["name"])
        if hit is None:
            if r["darko_value"] >= REPLACEMENT_VALUE:
                flagged.append(r)  # above replacement + no ESPN match -> flag, don't delete
            continue  # no ESPN projection -> retired / not rostered
        consumed.add(hit["norm"])
        w = blend.darko_weight(r["seasons"])
        value = blend.blend_value(r["darko_value"], hit["espn_proj_total"], w)
        adp_hit = adp_matcher.get(r["name"])
        rows.append(_row(r["name"], hit.get("team") or r.get("team"),
                         "S" if r["seasons"] == 1 else "V", value, r["games"],
                         hit["espn_rank"], adp_hit))

    # ESPN-projected players DARKO never covered: true rookies vs returning vets.
    for norm, p in espn_by_norm.items():
        if norm in consumed:
            continue
        adp_hit = adp_matcher.get(p["name"])
        adp_rank = adp_hit["adp_rank"] if adp_hit else None
        if norm in nba_history:
            value = round(p["espn_proj_total"], 1)  # returning vet: ESPN as-is, no discount
            cls = "V"
        else:
            value = blend.rookie_value(p["espn_proj_total"], p["espn_rank"], adp_rank)
            cls = "R"
        avg = p.get("espn_proj_avg") or 0.0
        games = round(p["espn_proj_total"] / avg, 1) if avg else 65.0
        rows.append(_row(p["name"], p.get("team"), cls, value, games, p["espn_rank"], adp_hit))

    return rows, flagged


def _row(name, team, cls, value, games, espn_rank, adp_hit):
    return {
        "name": name,
        "team": team,
        "cls": cls,
        "positions": adp_hit["positions"] if adp_hit else "",
        "value": value,
        "games": games,
        "fpg": round(value / games, 1) if games else 0.0,
        "espn_rank": espn_rank,
        "adp_rank": adp_hit["adp_rank"] if adp_hit else None,
    }


def main() -> None:
    cfg = load_config()
    formula = resolve_scoring(cfg)

    print(f"Loading 2025-26 stats + {len(stats_nba.CAREER_SEASONS)}-season games history ...")
    baseline = stats_nba.fetch_player_stats()
    gp_history = stats_nba.games_history()
    # Normalized names of everyone who has played an NBA game recently — lets us
    # tell a true rookie from a veteran DARKO happens to be missing.
    nba_history = {
        names.normalize(rec["name"])
        for season in stats_nba.CAREER_SEASONS
        for rec in stats_nba.fetch_player_stats(season=season)
    }

    print("Fetching DARKO, ESPN projections, and FantasyPros ADP ...")
    darko = projections.load_darko_preseason()
    if not (darko and cfg.has_credentials):
        raise SystemExit("Need DARKO + league credentials for the full blended board.")
    espn = espn_client.fetch_espn_player_data(cfg)  # one league pass
    current_teams = {name: v.get("team") for name, v in espn.items()}
    adp_index = adp_mod.fetch_adp()
    espn_by_norm = _index_espn(espn)
    print(f"  DARKO {len(darko)}, ESPN {len(espn_by_norm)}, ADP {len(adp_index)}")

    records = build_records(baseline, darko, current_teams, gp_history)
    _apply_team_context(records, formula)
    darko_rows = draft.compute_darko_rows(records, formula)

    rows, flagged = blend_board(darko_rows, espn_by_norm, adp_index, nba_history)
    board = draft.finalize(rows)

    csv_path, md_path = report.write_draft_board(board, REPORTS_DIR)
    print(f"\nDraft board written:\n  {csv_path}\n  {md_path}")

    if flagged:
        print(f"\n⚠ {len(flagged)} above-replacement players had NO ESPN match "
              "(possible name mismatch — review, not dropped blindly):")
        for r in sorted(flagged, key=lambda r: -r["darko_value"])[:10]:
            print(f"    {r['name']:<24} DARKO value {r['darko_value']:.0f}")

    print("\nTop 20 (ranked by projected season value):")
    for r in board[:20]:
        erk = f"E#{r['espn_rank']}" if r.get("espn_rank") else "E—"
        adp = f"A#{r['adp_rank']}" if r.get("adp_rank") else "A—"
        print(f"  {r['rank']:>3}. [{r['cls']}] {r['name']:<23} {r.get('team') or '':<4} "
              f"{r['positions']:<9} {r['value']:>6.0f}  ({erk} {adp})")


if __name__ == "__main__":
    main()
