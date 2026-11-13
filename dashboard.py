"""Streamlit dashboard over the daily snapshots.

Run:  venv/bin/streamlit run dashboard.py
Reads what the 8 AM job saved (snapshot DB + the day's plan/trades file), so it
opens instantly. "Refresh now" re-runs the daily job; if this morning's run was
missed (Mac off at 8), it runs automatically the first time the page opens.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import HISTORY_DB  # noqa: E402
from fba import ranking, storage, trades  # noqa: E402

st.set_page_config(page_title="TFT Addict — Fantasy Assistant", page_icon="🏀", layout="wide")

BASE_POSITIONS = ("PG", "SG", "SF", "PF", "C")
METRICS = {"FP/G": "value_fpg", "Minutes": "minutes", "ROS value": "value_ros", "DPM": "dpm"}


def run_daily_update() -> tuple[bool, str]:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "daily_update.py")],
                            cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr)[-2000:]


def refresh(reason: str) -> None:
    with st.spinner(f"{reason} — running the daily update (about a minute) ..."):
        ok, log = run_daily_update()
    st.cache_data.clear()
    if not ok:
        st.error("The update failed. Most often the ESPN cookies in .env have expired.")
        st.code(log)


def data_version() -> float:
    """Changes whenever the daily job writes, so cached reads refresh with it."""
    return HISTORY_DB.stat().st_mtime if HISTORY_DB.exists() else 0.0


@st.cache_data
def load(day: str | None, version: float) -> tuple[list[dict], dict]:
    return storage.load_snapshot(day), storage.load_extras(day)


@st.cache_data
def weekly(monday: str, version: float) -> tuple[dict, str | None, str | None]:
    return ranking.weekly_for(monday)


@st.cache_data
def history(name: str, version: float) -> list[dict]:
    return storage.player_history(name, days=120)


def positions(r: dict) -> str:
    return "/".join(p for p in (r.get("positions") or "").split(",") if p in BASE_POSITIONS)


def show_table(frame: pd.DataFrame) -> None:
    if len(frame):
        st.dataframe(frame, hide_index=True, width="stretch")
    else:
        st.write("Nobody this week.")


def short_day(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%a %m/%d")


# --- Header + refresh -------------------------------------------------------
today = date.today().isoformat()
if storage.latest_date() != today and not st.session_state.get("auto_refreshed"):
    st.session_state["auto_refreshed"] = True
    refresh("This morning's run was missed")

rows, extras = load(storage.latest_date(), data_version())
left, right = st.columns([4, 1])
left.title(f"🏀 {extras.get('my_team', 'My team')}")
left.caption(f"Data as of {storage.latest_date() or 'never'} · matchup "
             f"{' – '.join(short_day(d) for d in extras.get('period', [])) or '—'}")
if right.button("🔄 Refresh now", width="stretch"):
    refresh("Refreshing")
    st.rerun()

if not rows or not extras:
    st.warning("No data yet. Click **Refresh now** to run the first update.")
    st.stop()

my_team = extras["my_team"]
plan, ideas, tonight_proj = extras["plan"], extras["trades"], extras["tonight"]
mine = [r for r in rows if r.get("rostered_by") == my_team]

tab_today, tab_top, tab_team, tab_trades, tab_trends = st.tabs(
    ["Today", "Top 100", "My team", "Trades", "Trends"])

# --- Today --------------------------------------------------------------------
with tab_today:
    todays = [m for m in plan["moves"] if m["day"] == today]
    c1, c2, c3 = st.columns(3)
    c1.metric("Adds left this matchup", f"{7 - plan['adds_used']} of 7",
              f"{len(plan['moves'])} planned this week", delta_color="off")
    c2.metric("Open starting slots tonight", plan["open_slots_after"].get(today, 0))
    c3.metric("Projected lineup pts to Sunday", f"{plan['points_after']:.0f}",
              f"{plan['points_after'] - plan['points_before']:+.0f} from plan")

    st.subheader("Today's moves")
    for name in plan["ir_moves"]:
        st.info(f"🏥 **Move {name} to IR** — he's OUT; that frees a roster spot without a drop.")
    for m in todays:
        drop = f"drop **{m['drop']}**" if m["drop"] else "no drop needed (open spot)"
        st.success(f"➕ **Add {m['add']}** ({m['add_team']}), {drop} — "
                   f"+{m['gain']:.0f} projected lineup points this week.")
    if not todays and not plan["ir_moves"]:
        st.write("No move today — nothing clears the +8 point bar.")

    st.subheader("This week's plan")
    if plan["moves"]:
        st.dataframe(pd.DataFrame([{
            "Day": short_day(m["day"]), "Add": m["add"], "Team": m["add_team"],
            "Drop": m["drop"] or "(open spot)",
            "Projected games": ", ".join(f"{short_day(d)[:3]} {fp:.0f}" for d, fp in m["games"].items()),
            "Gain": round(m["gain"]),
        } for m in plan["moves"]]), hide_index=True, width="stretch")
    else:
        st.write("No pickups planned — your lineup is full on the nights that matter.")

    st.subheader("Open starting slots by night")
    st.dataframe(pd.DataFrame({
        "Night": [short_day(d) for d in plan["days"]],
        "Before plan": [plan["open_slots_before"][d] for d in plan["days"]],
        "After plan": [plan["open_slots_after"][d] for d in plan["days"]],
    }).set_index("Night").T, width="stretch")
    st.caption(f"Streamer spots: {', '.join(plan['streamers'])}. "
               "A pickup only scores on nights he plays and an eligible starting slot is open.")

# --- Top 100 ------------------------------------------------------------------
with tab_top:
    monday = ranking.last_monday(date.today()).isoformat()
    rank, snap_day, prev_day = weekly(monday, data_version())
    st.caption(f"Weekly ranking from {snap_day} vs {prev_day or 'no earlier snapshot'} — "
               "standard contracts, sorted by rest-of-season value.")
    f1, f2, f3 = st.columns([2, 2, 1])
    pos_filter = f1.multiselect("Positions", BASE_POSITIONS)
    owners = sorted({r.get("rostered_by") or "FA" for r in rank["core"]})
    owner_filter = f2.multiselect("Owner", owners)
    fa_only = f3.checkbox("Free agents only")

    def keep(r):
        return ((not pos_filter or any(p in positions(r).split("/") for p in pos_filter))
                and (not owner_filter or (r.get("rostered_by") or "FA") in owner_filter)
                and (not fa_only or not r.get("rostered_by")))

    def rank_frame(rs, with_minutes=False):
        def move(r):
            if r["rank_change"] is None:
                return "new"
            return "—" if r["rank_change"] == 0 else f"{'▲' if r['rank_change'] > 0 else '▼'}{abs(r['rank_change'])}"
        return pd.DataFrame([{
            "Rk": r["rank"], "Move": move(r), "Player": r["name"], "Team": r.get("pro_team"),
            "Pos": positions(r), "FP/G": r["value_fpg"], "ESPN avg": r.get("espn_avg"),
            "Games left": round(r["games_left"]), "ROS": round(r["value_ros"]),
            "Owner": r.get("rostered_by") or "FA", "Injury": r.get("injury") or "",
            **({"ΔMPG": r["minutes_change"]} if with_minutes else {}),
        } for r in rs if keep(r)])

    st.dataframe(rank_frame(rank["top"]), hide_index=True, width="stretch", height=600)
    st.subheader("Watch list — ranks 121–160 climbing fast")
    st.caption("Up 15+ spots or +4 MPG in the last week.")
    show_table(rank_frame(rank["watch"], with_minutes=True))
    st.subheader("Fallers — core players down 15+ spots")
    show_table(rank_frame(rank["fallers"]))

# --- My team ------------------------------------------------------------------
with tab_team:
    def role(r):
        if r.get("lineup_slot") == "IR":
            return "IR"
        return "streamer" if r["name"] in plan["streamers"] else "core"
    st.dataframe(pd.DataFrame([{
        "Player": r["name"], "Team": r.get("pro_team"), "Pos": positions(r), "Role": role(r),
        "Injury": r.get("injury") or "", "FP/G": r["value_fpg"], "ESPN avg": r.get("espn_avg"),
        "Tonight": tonight_proj.get(r["name"], {}).get(today, 0.0),
        "Games this week": r["games_week"], "ROS": round(r["value_ros"]), "DPM": r["dpm"],
    } for r in sorted(mine, key=lambda r: r["value_ros"], reverse=True)]),
        hide_index=True, width="stretch")
    st.caption("Streamer spots = your 2 lowest by average rank of FP/G and ROS. "
               "Core spots only change for a rest-of-season upgrade.")

# --- Trades -------------------------------------------------------------------
with tab_trades:
    st.subheader("Suggested trades")
    st.caption("You gain 3–15% on our rest-of-season value; it looks even or better to them "
               "on ESPN's numbers. Max 3 per team.")
    if ideas:
        for t in ideas:
            label = (f"{t['team']}: give {' + '.join(t['give'])} → get {' + '.join(t['get'])}   "
                     f"(you {t['my_pct']:+.0%} · them {t['their_pct']:+.0%})")
            with st.expander(label):
                a, b = st.columns(2)
                a.metric("Your side (our ROS)", f"{t['my_gain']:+.0f}", f"{t['my_pct']:+.0%}")
                b.metric("Their side (ESPN)", f"{t['their_gain']:+.0f}", f"{t['their_pct']:+.0%}")
                if t["my_fill"]:
                    st.write(f"Open spot: you'd add **{', '.join(t['my_fill'])}**; "
                             f"they'd drop **{', '.join(t['their_drop'])}**.")
    else:
        st.write("No trades fit both bands today.")

    st.subheader("Evaluate any trade")
    others = sorted((r for r in rows if r.get("rostered_by") not in (None, my_team)), key=lambda r: r["name"])
    with st.form("evaluate"):
        give = st.multiselect("You give", sorted(r["name"] for r in mine))
        get = st.multiselect("You get", [r["name"] for r in others],
                             format_func=lambda n: f"{n} ({next(r['rostered_by'] for r in others if r['name'] == n)})")
        submitted = st.form_submit_button("Evaluate")
    if submitted:
        t = trades.evaluate_named(rows, my_team, give, get)
        if "error" in t:
            st.error(t["error"])
        else:
            a, b = st.columns(2)
            a.metric("Your side (our ROS)", f"{t['my_gain']:+.0f}", f"{t['my_pct']:+.0%}")
            b.metric("Their side (ESPN)", f"{t['their_gain']:+.0f}", f"{t['their_pct']:+.0%}")
            for label, names in (("You add from FA (open spot)", t["my_fill"]), ("You must drop", t["my_drop"]),
                                 ("They must drop", t["their_drop"]), ("They add from FA", t["their_fill"])):
                if names:
                    st.write(f"{label}: **{', '.join(names)}**")
            st.info(trades.verdict(t))
            if t["their_pct"] < trades.THEIR_MIN:
                st.warning("They'll likely see this as a loss on ESPN's numbers — expect a no.")

# --- Trends -------------------------------------------------------------------
with tab_trends:
    all_names = sorted(r["name"] for r in rows)
    default = [r["name"] for r in sorted(mine, key=lambda r: r["value_ros"], reverse=True)[:3]]
    picked = st.multiselect("Players (up to 5)", all_names, default=default, max_selections=5)
    shown = [label for label in METRICS
             if st.checkbox(label, value=label in ("FP/G", "Minutes"), key=f"metric_{label}")]
    if picked and shown:
        frame = pd.DataFrame([{"date": h["snapshot_date"], "player": name,
                               **{label: h.get(col) for label, col in METRICS.items()}}
                              for name in picked for h in history(name, data_version())])
        frame["date"] = pd.to_datetime(frame["date"])
        for label in shown:
            st.altair_chart(
                alt.Chart(frame.dropna(subset=[label]), title=label).mark_line(point=True)
                .encode(x=alt.X("date:T", title=None), y=alt.Y(f"{label}:Q", title=label,
                                                                  scale=alt.Scale(zero=False)),
                        color=alt.Color("player:N", title=None), tooltip=["player", "date:T", f"{label}:Q"])
                .properties(height=260),
                width="stretch",
            )
    st.caption("One point per daily snapshot. DPM is DARKO's impact rating — a trend signal only.")
