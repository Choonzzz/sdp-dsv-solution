"""Streamlit dashboard for the M4 mockup (PRD section 6).

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

DEFAULTS = {"n_lanes": 12, "lane_throughput": 100, "lane_queue_cap": 100,
            "zone_capacity": 48, "warn_pct": 80}
TICK = 0.5  # real seconds between refreshes while playing
SPEEDS = [1, 2, 5, 10, 20, 30, 60]  # simulated minutes per real second

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
.seg-over{background:#e8a33d}
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
    st.slider("Lane queue cap (cartons)", 50, 400, step=25, key="set_lane_queue_cap")
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
    lane_queue_cap=st.session_state.set_lane_queue_cap,
    zone_capacity=st.session_state.set_zone_capacity,
)
WARN_PCT = st.session_state.set_warn_pct


@st.cache_resource(show_spinner="Simulating the day...")
def load_bundle(n_lanes, throughput, lane_cap, zone_cap):
    sim = Simulation(
        load_data(),
        Params(n_lanes=n_lanes, lane_throughput=throughput,
               lane_queue_cap=lane_cap, zone_capacity=zone_cap),
    )
    return {"sim": sim, "log": sim.event_log(), "occupancy": vh.occupancy_series(sim)}


if not DATA_PATH.exists():
    st.error(
        f"Input file not found: {DATA_PATH}. Run mockup/Data _Prep.ipynb to create "
        "data/Mockup_Data.xlsx (Excel files are not stored in the repository)."
    )
    st.stop()

bundle = load_bundle(params.n_lanes, params.lane_throughput, params.lane_queue_cap,
                     params.zone_capacity)
SIM: Simulation = bundle["sim"]
START, END = SIM.start_time.to_pydatetime(), SIM.end_time.to_pydatetime()

signature = (params.n_lanes, params.lane_throughput, params.lane_queue_cap, params.zone_capacity)
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
    "pallets and arrival times. The call-out rule is a simple placeholder: smallest gap between "
    "cut and forwarder arrival first, 12 lanes, and an LL waits while its zone is full."
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
    n_staged = int(row["Staged LLs"])
    avg, longest = vh.fmt_dur(row["Staging time mean (min)"]), vh.fmt_dur(row["Staging time max (min)"])
    queued = int(row["LLs queued for this zone (zone full)"])
    staging_line = f"{n_staged} LLs staged, average {avg}, longest {longest}" if n_staged else "Nothing staged"
    return (
        f'<div class="card {status}"><span class="chip {status}">{label}</span>'
        f'<b>Zone {int(row["Zone"])}</b>'
        f'<div class="big">{used} <span class="muted">/ {cap} pallets ({row["Used %"]:.0f}%)</span></div>'
        f'<div class="bar"><div class="seg-st" style="width:{w_st:.1f}%"></div>'
        f'<div class="seg-rs" style="width:{w_rs:.1f}%"></div></div>'
        f'<div class="muted">Staged {staged_p} · In a lane (reserved) {reserved_p}</div>'
        f'<div class="muted">{staging_line}</div>'
        f'<div>Queued, waiting for this zone: <b>{queued}</b></div></div>'
    )


def lane_card(lane: dict) -> str:
    q, cap = int(lane["Queue (cartons)"]), int(lane["Cap"])
    over = q > cap
    width = min(100.0, 100 * q / cap)
    seg = "seg-over" if over else "seg-st"
    if lane["Processing"] is None:
        body = '<div class="muted">Idle</div>'
        cls = "idle"
    else:
        body = f'<div>Processing LL <b>{lane["Processing"]}</b>, {vh.fmt_dur(lane["Remaining (min)"])} left</div>'
        behind = lane["Waiting behind"]
        if behind:
            shown = ", ".join(str(x) for x in behind[:3]) + (f" +{len(behind) - 3}" if len(behind) > 3 else "")
            body += f'<div class="muted">Behind: {shown}</div>'
        else:
            body += '<div class="muted">Nothing behind</div>'
        cls = "full" if over else "ok"
    note = " (single large LL)" if over else ""
    return (
        f'<div class="card {cls}"><b>Lane {lane["Lane"]}</b>'
        f'<div class="muted">{q} / {cap} cartons{note}</div>'
        f'<div class="bar"><div class="{seg}" style="width:{width:.1f}%"></div></div>{body}</div>'
    )


def style_queue(row):
    status = row["Status"]
    if status.startswith("LATE"):
        bg = "rgba(209,73,91,.30)"
    elif status.startswith("NEXT"):
        bg = "rgba(56,161,105,.32)"
    elif "zone" in status:
        bg = "rgba(232,163,61,.25)"
    else:
        bg = ""
    return [f"background-color: {bg}" if bg else ""] * len(row)


def floor_tab(state: dict, clock: pd.Timestamp):
    counts, late = state["counts"], state["late_summary"]
    st.subheader("Zones")
    zone_rows = [r for _, r in state["zones"].iterrows()]
    for start in range(0, len(zone_rows), 6):
        cols = st.columns(6)
        for col, row in zip(cols, zone_rows[start:start + 6]):
            col.markdown(zone_card(row), unsafe_allow_html=True)
    zones_df = state["zones"]
    n_staged_all = int(zones_df["Staged LLs"].sum())
    if n_staged_all:
        avg_all = (zones_df["Staging time mean (min)"] * zones_df["Staged LLs"]).sum() / n_staged_all
        overall = (f"All zones: {n_staged_all} LLs staged, average time in staging {vh.fmt_dur(avg_all)}, "
                   f"longest {vh.fmt_dur(zones_df['Staging time max (min)'].max())}.")
    else:
        overall = "All zones: nothing is staged yet."
    st.caption("Solid bar: staged pallets. Hatched bar: pallets reserved by LLs still in a lane. "
               "A zone never goes over its capacity. " + overall)

    st.subheader("LL progress")
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

    st.subheader("Late LLs")
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


def callout_tab(state: dict, clock: pd.Timestamp):
    queue = state["queue"]
    held_zone = int(queue["Reason held"].str.contains("zone").sum()) if len(queue) else 0
    cols = st.columns(4)
    cols[0].metric("LLs in the queue", len(queue), border=True)
    cols[1].metric("Held by a full zone", held_zone, border=True)
    cols[2].metric("LLs in lanes", state["counts"]["in lane"], border=True)
    cols[3].metric("Cartons in lanes", f'{state["cartons in lanes"]:,}', border=True)

    st.subheader("Call-out queue")
    st.caption(
        "Order: smallest gap between cut and forwarder arrival first. A row held by a full zone is "
        "skipped and the LLs behind it go ahead. An LL that does not fit any lane blocks the LLs "
        "behind it. LLs whose forwarder has already arrived skip the zone check."
    )
    if queue.empty:
        st.success("The queue is empty.")
    else:
        if not queue["Next"].any():
            st.warning("No LL can be called out right now. Every LL in the queue is waiting "
                       "for its zone to have room.")
        disp = vh.queue_display(queue)
        st.dataframe(disp.style.apply(style_queue, axis=1), hide_index=True,
                     height=min(35 * (len(disp) + 1) + 3, 480))

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

    tab1, tab2 = st.tabs(["Floor view", "Call-out view"])
    with tab1:
        floor_tab(state, clock)
    with tab2:
        callout_tab(state, clock)

    if finished:
        st.session_state.playing = False
        st.rerun()  # drops the timer


st.fragment(run_every=TICK if st.session_state.playing else None)(render)()
