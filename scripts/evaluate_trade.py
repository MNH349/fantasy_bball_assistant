"""Evaluate a proposed trade against the latest in-season valuation.

Reads the most recent daily snapshot (run scripts/daily_update.py first), so it
is instant and consistent with the board. Compares rest-of-season and this-week
value on both sides, flags the best asset and any quantity imbalance, and gives
a value verdict — the positional/fit judgment is left to you.

Run:  python scripts/evaluate_trade.py --give "Deni Avdija, Naz Reid" --get "Bam Adebayo"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import names, storage  # noqa: E402

# Verdict bands on the ROS-value gap, as a fraction of the larger side.
FAIR_BAND = 0.05     # within 5% either way = roughly even
CLEAR_BAND = 0.15    # beyond 15% = a clear win/loss


def _split(arg: str) -> list[str]:
    return [p.strip() for p in arg.split(",") if p.strip()]


def _lookup(matcher, raw_names):
    hits, misses = [], []
    for n in raw_names:
        row = matcher.get(n)
        (hits if row else misses).append(row if row else n)
    return hits, misses


def _side_table(label, rows):
    print(f"\n{label}")
    print(f"  {'Player':<24}{'Tm':<4}{'ROS':>7}{'Week':>7}{'DPM':>7}  inj")
    for r in rows:
        inj = "" if (r.get("injury") in (None, "ACTIVE")) else r["injury"]
        print(f"  {r['name']:<24}{(r.get('pro_team') or ''):<4}"
              f"{r['value_ros']:>7.0f}{r['value_week']:>7.0f}{(r.get('dpm') or 0):>7.1f}  {inj}")
    print(f"  {'— total —':<24}{'':<4}{sum(r['value_ros'] for r in rows):>7.0f}"
          f"{sum(r['value_week'] for r in rows):>7.0f}")


def _verdict(give, get):
    give_ros = sum(r["value_ros"] for r in give)
    get_ros = sum(r["value_ros"] for r in get)
    net = get_ros - give_ros
    larger = max(give_ros, get_ros) or 1.0
    frac = net / larger

    if frac > CLEAR_BAND:
        call = "ACCEPT — a clear rest-of-season value gain."
    elif frac > FAIR_BAND:
        call = "LEAN ACCEPT — modest value gain."
    elif frac >= -FAIR_BAND:
        call = "ROUGHLY EVEN on value — decide on positional fit and need."
    elif frac >= -CLEAR_BAND:
        call = "LEAN DECLINE — you give up modest value (justify it with fit/need)."
    else:
        call = "DECLINE — you give up clear rest-of-season value."

    print(f"\nNet ROS value: {net:+.0f}  ({frac:+.0%} of the larger side)")
    best = max(give + get, key=lambda r: r["value_ros"])
    side = "you GET" if best in get else "you GIVE"
    print(f"Best asset in the deal: {best['name']} (ROS {best['value_ros']:.0f}) — {side}.")
    if len(give) != len(get):
        more, fewer = ("give", "get") if len(give) > len(get) else ("get", "give")
        print(f"Quantity: you {more} {abs(len(give) - len(get))} more player(s) than you "
              f"{fewer} — consolidating value into fewer, better players"
              + (" (needs an open roster spot)." if more == "get" else "."))
    print(f"\nVerdict: {call}")
    print("Note: value only — weigh your own positional needs and the DPM trend on top.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate a proposed fantasy trade.")
    ap.add_argument("--give", required=True, help="comma-separated players you'd send")
    ap.add_argument("--get", required=True, help="comma-separated players you'd receive")
    args = ap.parse_args()

    snapshot = storage.load_snapshot()
    if not snapshot:
        raise SystemExit("No snapshot found — run scripts/daily_update.py first.")
    matcher = names.Matcher({names.normalize(r["name"]): r for r in snapshot})

    give, give_miss = _lookup(matcher, _split(args.give))
    get, get_miss = _lookup(matcher, _split(args.get))
    for miss in give_miss + get_miss:
        print(f"⚠ no match for '{miss}' — check spelling (skipped).")
    if not give or not get:
        raise SystemExit("Need at least one matched player on each side.")

    print(f"\nTrade evaluation (as of snapshot {snapshot[0]['snapshot_date'] if 'snapshot_date' in snapshot[0] else storage.latest_date()}):")
    _side_table("YOU GIVE:", give)
    _side_table("YOU GET:", get)
    _verdict(give, get)


if __name__ == "__main__":
    main()
