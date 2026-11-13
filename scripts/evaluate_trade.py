"""Evaluate a proposed trade against the latest daily snapshot.

Judged the same two ways as the trade finder: your side on our rest-of-season
value, their side on what they see in ESPN. Uneven trades count the roster spot
they open or force. Run scripts/daily_update.py first (the 8 AM job does).

Run:  python scripts/evaluate_trade.py --give "Zion Williamson" --get "AJ Dybantsa"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import storage, trades  # noqa: E402


def _split(arg: str) -> list[str]:
    return [p.strip() for p in arg.split(",") if p.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate a proposed fantasy trade.")
    ap.add_argument("--give", required=True, help="comma-separated players you'd send")
    ap.add_argument("--get", required=True, help="comma-separated players you'd receive")
    args = ap.parse_args()

    rows, extras = storage.load_snapshot(), storage.load_extras()
    if not rows or not extras:
        raise SystemExit("No snapshot yet — run scripts/daily_update.py first.")
    t = trades.evaluate_named(rows, extras["my_team"], _split(args.give), _split(args.get))
    if "error" in t:
        raise SystemExit(t["error"])

    print(f"\nTrade with {t['team']} (snapshot {storage.latest_date()})")
    print(f"  You give: {', '.join(t['give'])}")
    print(f"  You get:  {', '.join(t['get'])}")
    for label, names in (("You add from FA (open spot)", t["my_fill"]), ("You must drop", t["my_drop"]),
                         ("They must drop", t["their_drop"]), ("They add from FA", t["their_fill"])):
        if names:
            print(f"  {label}: {', '.join(names)}")
    print(f"\nYour side (our ROS):   {t['my_give']:.0f} out, {t['my_get']:.0f} in  -> {t['my_gain']:+.0f} ({t['my_pct']:+.0%})")
    print(f"Their side (ESPN):     {t['their_give']:.0f} out, {t['their_get']:.0f} in  -> {t['their_gain']:+.0f} ({t['their_pct']:+.0%})")
    print(f"\nVerdict: {trades.verdict(t)}")
    if t["their_pct"] < trades.THEIR_MIN:
        print("They'll likely see this as a loss on ESPN's numbers — expect a no.")


if __name__ == "__main__":
    main()
