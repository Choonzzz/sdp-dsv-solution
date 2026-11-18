"""Streamlit dashboard for the M4 mockup (PRD section 6, v1.1).

Run from the repository root:
    .venv/Scripts/python.exe -m streamlit run mockup/app.py

The day is simulated once by engine.py. This file only displays it: it picks a clock
time and shows the engine's state for that moment. It makes no decisions of its own.
"""
import sys
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import view_helpers as vh  # noqa: E402
from engine import DATA_PATH, Params, Simulation, load_data  # noqa: E402

st.set_page_config(page_title="Staging dashboard preview", page_icon="📦", layout="wide")

DEFAULTS = {"n_lanes": 10, "lane_throughput": 100, "zone_capacity": 48, "warn_pct": 80}
TICK = 0.5  # real seconds between refreshes while playing
SPEEDS = [1, 2, 5, 10, 20, 30, 60]  # simulated minutes per real second
FILTER_OPTIONS = ["Upcoming LLs only", "Upcoming and in lanes"]

CSS = """
<style>
.card{border:1px solid rgba(128,128,128,.35);border-left-width:6px;border-radius:10px;
      padding:10px 12px;margin-bottom:10px;line-height:1.4}
.card.ok{border-left-color:#3b82c4}.card.warn{border-left-color:#e8a33d}
.card.full{border-left-color:#d1495b}.card.idle{border-left-color:rgba(128,128,128,.5)}
.chip{float:right;font-size:.7rem;font-weight:700;padding:1px 9px;border-radius:999px;color:#fff}
.chip.ok{background:#3b82c4}.chip.warn{background:#b9770e}.chip.full{background:#d1495b}
.bar{display:flex;height:12px;border-radius:6px;overflow:hidden;
     background:rgba(128,128,128,.25);margin:6px 0}
.seg-st{background:#3b82c4}
.seg-rs{background:repeating-linear-gradient(45deg,#8fbfe8,#8fbfe8 4px,#6aa6d8 4px,#6aa6d8 8px)}
.muted{opacity:.7;font-size:.85rem}
.big{font-size:1.5rem;font-weight:700}
</style>
"""


# ------------------------------------------------------------------ settings
def reset_settings():
    for key, value in DEFAULTS.items():
        st.session_state[f"set_{key}"] = value


for _k, _v in DEFAULTS.items():
    st.session_state.setdefault(f"set_{_k}", _v)
st.session_state.setdefault("playing", False)
st.session_state.setdefault("speed", 10)

with st.sidebar:
    st.header("Settings")
    st.slider("Lanes", 1, 24, key="set_n_lanes")
    st.slider("Lane throughput (cartons per hour)", 25, 400, step=25, key="set_lane_throughput")
    st.slider("Zone capacity (pallets)", 12, 96, step=4, key="set_zone_capacity")
    st.slider("Zone warning threshold (%)", 50, 99, key="set_warn_pct")
    st.button("Reset to defaults", on_click=reset_settings)
    st.caption(
        "Changing a setting re-simulates the whole day and returns the clock to the start. "
        "Defaults are the agreed values in the PRD."
    )

params = Params(
    n_lanes=st.session_state.set_n_lanes,
    lane_throughput=float(st.session_state.set_lane_throughput),
    zone_capacity=st.session_state.set_zone_capacity,
)
WARN_PCT = st.session_state.set_warn_pct


@st.cache_resource(show_spinner="Simulating the day...")
def load_bundle(n_lanes, throughput, zone_cap):
    sim = Simulation(
        load_data(),
        Params(n_lanes=n_lanes, lane_throughput=throughput, zone_capacity=zone_cap),
    )
    return {"sim": sim, "log": sim.event_log(), "occupancy": vh.occupancy_series(sim)}


if not DATA_PATH.exists():
    st.error(
        f"Input file not found: {DATA_PATH}. Run mockup/Data _Prep.ipynb to create "
        "data/Mockup_Data.xlsx (Excel files are not stored in the repository)."
    )
    st.stop()

bundle = load_bundle(params.n_lanes, params.lane_throughput, params.zone_capacity)
SIM: Simulation = bundle["sim"]
START, END = SIM.start_time.to_pydatetime(), SIM.end_time.to_pydatetime()

signature = (params.n_lanes, params.lane_throughput, params.zone_capacity)
if st.session_state.get("signature") != signature:
    st.session_state.signature = signature
    st.session_state.clock = START
    st.session_state.playing = False
st.session_state.setdefault("clock", START)


# ------------------------------------------------------------------ controls
def toggle_play():
    if not st.session_state.playing and st.session_state.clock >= END:
        st.session_state.clock = START  # pressing play at the end starts the day again
    st.session_state.playing = not st.session_state.playing


def restart():
    st.session_state.clock = START
    st.session_state.playing = False


st.markdown(CSS, unsafe_allow_html=True)
st.title("📦 Staging dashboard preview")
st.info(
    "**Mockup.** Real LL volumes and cut times from 8 Sep 2026, with synthetic forwarders, zones, "
    "pallets and arrival times. The call-out rule is a simple placeholder: soonest forwarder "
    "arrival first, 10 lanes that each process one LL at a time, and an LL waits while its zone "
    "is full."
)

c1, c2, c3 = st.columns([1, 1, 2])
c1.button("⏸ Pause" if st.session_state.playing else "▶ Play", on_click=toggle_play,
          width="stretch", type="primary")
c2.button("↺ Restart", on_click=restart, width="stretch")
c3.selectbox("Speed (simulated minutes per second)", SPEEDS, key="speed")


# ----------------------------------------------------------------- components
def zone_card(row) -> str:
    cap, used = int(row["Capacity"]), int(row["Used"])
    staged_p, reserved_p = int(row["Staged pallets"]), int(row["Reserved pallets"])
    status = vh.zone_status(used, cap, WARN_PCT)
    label = {"ok": "OK", "warn": "FILLING", "full": "FULL"}[status]
    w_st = min(100.0, 100 * staged_p / cap)
    w_rs = min(100.0 - w_st, 100 * reserved_p / cap)
    return (
        f'<div class="card {status}"><span class="chip {status}">{label}</span>'
        f'<b>Zone {int(row["Zone"])}</b>'
        f'<div class="big">{used} <span class="muted">/ {cap} pallets ({row["Used %"]:.0f}%)</span></div>'
        f'<div class="bar"><div class="seg-st" style="width:{w_st:.1f}%"></div>'
        f'<div class="seg-rs" style="width:{w_rs:.1f}%"></div></div>'
        f'<div>Pallets staged: <b>{staged_p}</b></div>'
        f'<div>Pallets reserved: <b>{reserved_p}</b></div>'
        f'<div>LLs in the zone: <b>{int(row["LLs in zone"])}</b></div></div>'
    )


def lane_card(lane: dict) -> str:
    if lane["Processing"] is None:
        return (f'<div class="card idle"><b>Lane {lane["Lane"]}</b>'
                f'<div class="muted">Idle</div>'
                f'<div class="bar"><div class="seg-st" style="width:0%"></div></div></div>')
    width = min(100.0, 100 * lane["Progress"])
    return (
        f'<div class="card ok"><b>Lane {lane["Lane"]}</b>'
        f'<div>Processing LL <b>{lane["Processing"]}</b></div>'
        f'<div class="muted">{lane["Cartons"]} cartons, {vh.fmt_dur(lane["Remaining (min)"])} left</div>'
        f'<div class="bar"><div class="seg-st" style="width:{width:.1f}%"></div></div></div>'
    )


def style_table(row):
    status = row["Status"]
    if status.startswith("LATE"):
        bg = "rgba(209,73,91,.30)"
    elif status.startswith("Processing"):
        bg = "rgba(59,130,196,.25)"
    elif status.startswith("NEXT"):
        bg = "rgba(56,161,105,.32)"
    elif status.startswith("Held"):
        bg = "rgba(232,163,61,.25)"
    else:
        bg = ""
    return [f"background-color: {bg}" if bg else ""] * len(row)


def callout_tab(state: dict, clock: pd.Timestamp):
    counts, late, queue = state["counts"], state["late_summary"], state["queue"]

    with st.expander("LL progress", expanded=True):
        cols = st.columns(5)
        for col, (label, key) in zip(
            cols,
            [("Cut so far", "cut so far"), ("Waiting in queue", "waiting"), ("In a lane", "in lane"),
             ("Staged", "staged"), ("Completed", "completed")],
        ):
            col.metric(label, counts[key], border=True)
        work = state["workload"]
        w1, w2 = st.columns(2)
        w1.progress(work["LLs cut"] / work["LLs total"], text=f'LLs cut: {work["LLs cut"]} of {work["LLs total"]}')
        w2.progress(work["cartons cut"] / work["cartons total"],
                    text=f'Cartons cut: {work["cartons cut"]:,} of {work["cartons total"]:,}')

    with st.expander("Late LLs", expanded=True):
        st.caption("An LL is late when its forwarder has arrived and it is not yet staged.")
        cols = st.columns(5)
        cols[0].metric("Late so far", late["late LLs so far"], border=True)
        cols[1].metric("Late right now", late["late now"], border=True)
        cols[2].metric("Average lateness", vh.fmt_dur(late["mean (min)"]), border=True)
        cols[3].metric("Longest", vh.fmt_dur(late["longest (min)"]), border=True)
        cols[4].metric("Total lateness", vh.fmt_dur(late["total (min)"]), border=True)
        late_now = state["late_now"]
        if late_now.empty:
            st.success("No LL is late right now.")
        else:
            shown = pd.DataFrame(
                {
                    "LL": late_now["LL"],
                    "Zone": late_now["Zone"],
                    "Forwarder arrived": late_now["Arrived"].map(vh.fmt_hm),
                    "Late for": late_now["Late for (min)"].map(vh.fmt_dur),
                    "State": late_now["State"],
                }
            )
            st.dataframe(shown, hide_index=True)

    with st.expander("Queue breakdown", expanded=True):
        held_zone = int(queue["Reason held"].str.contains("zone").sum()) if len(queue) else 0
        cols = st.columns(4)
        cols[0].metric("LLs in the queue", len(queue), border=True)
        cols[1].metric("Held by a full zone", held_zone, border=True)
        cols[2].metric("LLs in lanes", counts["in lane"], border=True)
        cols[3].metric("Cartons being processed", f'{state["cartons in lanes"]:,}', border=True)

    st.subheader("Call-out queue")
    st.caption(
        "Soonest forwarder arrival first. A row held by a full zone is skipped and the LLs behind "
        "it go ahead. When every lane is busy, nothing moves until one frees up. LLs whose "
        "forwarder has already arrived skip the zone check, and their time to arrival is negative."
    )
    view = st.radio("Show", FILTER_OPTIONS, horizontal=True, key="queue_filter")
    include_lanes = view == FILTER_OPTIONS[1]
    table = vh.call_out_table(queue, state["in_lanes"], include_in_lanes=include_lanes)
    if table.empty:
        st.success("The queue is empty.")
    else:
        if len(queue) and not queue["Next"].any():
            st.warning("No LL can be called out right now. Every LL in the queue is waiting "
                       "for its zone to have room.")
        st.dataframe(table.style.apply(style_table, axis=1), hide_index=True,
                     height=min(35 * (len(table) + 1) + 3, 480))
        if include_lanes:
            st.caption("Blue rows are LLs being processed in a lane, soonest arrival first. "
                       "The upcoming LLs follow below them.")

    st.subheader("Lanes")
    lanes = state["lanes"]
    per_row = 6
    for start in range(0, len(lanes), per_row):
        cols = st.columns(per_row)
        for col, lane in zip(cols, lanes[start:start + per_row]):
            col.markdown(lane_card(lane), unsafe_allow_html=True)

    if st.toggle("Show recently staged LLs", key="show_recent"):
        st.dataframe(vh.recent_staged(SIM, clock), hide_index=True)
    if st.toggle("Show event log", key="show_log"):
        st.dataframe(vh.event_log_until(bundle["log"], SIM, clock), hide_index=True, height=300)


def floor_tab(state: dict, clock: pd.Timestamp):
    st.subheader("Zones")
    zone_rows = [r for _, r in state["zones"].iterrows()]
    for start in range(0, len(zone_rows), 6):
        cols = st.columns(6)
        for col, row in zip(cols, zone_rows[start:start + 6]):
            col.markdown(zone_card(row), unsafe_allow_html=True)
    st.caption("Solid bar: staged pallets. Hatched bar: pallets reserved by LLs being processed in "
               "a lane. A zone never goes over its capacity.")

    st.subheader("Zone detail")
    zone = st.selectbox("Zone", SIM.zones, key="zone_detail", format_func=lambda z: f"Zone {z}")
    detail = vh.zone_detail(SIM, zone, clock)
    if detail.empty:
        st.caption(f"Zone {zone} is empty.")
    else:
        st.dataframe(detail, hide_index=True, height=min(35 * (len(detail) + 1) + 3, 400))

    if st.toggle("Show pallets used per zone over the day", key="show_occ"):
        occ = bundle["occupancy"]
        cap = SIM.params.zone_capacity
        lines = alt.Chart(occ).mark_line().encode(
            x=alt.X("Time:T", title=None),
            y=alt.Y("Pallets used:Q", scale=alt.Scale(domain=[0, cap * 1.1])),
            color=alt.Color("Zone:N"),
        )
        cap_rule = alt.Chart(pd.DataFrame({"y": [cap]})).mark_rule(
            strokeDash=[6, 4], color="#d1495b").encode(y="y:Q")
        now_rule = alt.Chart(pd.DataFrame({"t": [clock]})).mark_rule(color="gray").encode(x="t:T")
        st.altair_chart(lines + cap_rule + now_rule)


# --------------------------------------------------------------------- render
def render():
    finished = False
    if st.session_state.playing:
        nxt = st.session_state.clock + timedelta(minutes=st.session_state.speed * TICK)
        if nxt >= END:
            nxt, finished = END, True
        st.session_state.clock = nxt

    st.slider("Jump to time (pause first to drag while playing)", min_value=START, max_value=END,
              step=timedelta(minutes=1), format="HH:mm", key="clock")
    clock = pd.Timestamp(st.session_state.clock)
    state = SIM.state_at(clock)
    st.markdown(f"### 🕒 {clock:%a %d %b %Y, %H:%M}")

    tab_callout, tab_floor = st.tabs(["Call-out view", "Floor view"])
    with tab_callout:
        callout_tab(state, clock)
    with tab_floor:
        floor_tab(state, clock)

    if finished:
        st.session_state.playing = False
        st.rerun()  # drops the timer


st.fragment(run_every=TICK if st.session_state.playing else None)(render)()
