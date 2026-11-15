"""Pure helpers for the dashboard: formatting and data shaping. No Streamlit here,
so everything in this file can be tested on its own."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import Simulation


# ---------------------------------------------------------------- formatting
def fmt_dur(minutes: float) -> str:
    """Minutes as '45 min' or '3 h 05 min'."""
    m = int(round(minutes))
    if m < 60:
        return f"{m} min"
    return f"{m // 60} h {m % 60:02d} min"


def fmt_hm(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).strftime("%H:%M")


def zone_status(used: float, capacity: float, warn_pct: float) -> str:
    """'ok', 'warn' or 'full' (over capacity counts as full)."""
    pct = 100 * used / capacity
    if pct >= 100:
        return "full"
    if pct >= warn_pct:
        return "warn"
    return "ok"


# ------------------------------------------------------------------- queue
def queue_display(queue: pd.DataFrame) -> pd.DataFrame:
    """Shape the engine's queue table for display (DSH-11 to DSH-13)."""
    if queue.empty:
        return pd.DataFrame(
            columns=["#", "LL", "Forwarder", "Zone", "Cartons", "Pallets", "Cut",
                     "Arrival", "Gap", "Waiting", "Status"]
        )

    def status(row) -> str:
        if row["Late"]:
            return f"LATE {fmt_dur(row['Late for (min)'])}, {row['Reason held']}"
        if row["Next"]:
            return f"NEXT, {row['Reason held']}"
        return f"Held: {row['Reason held']}"

    out = pd.DataFrame(
        {
            "#": queue["Position"],
            "LL": queue["LL"],
            "Forwarder": queue["Forwarder"],
            "Zone": queue["Zone"],
            "Cartons": queue["Cartons"],
            "Pallets": queue["Pallets"],
            "Cut": queue["Cut"].map(fmt_hm),
            "Arrival": queue["Arrival"].map(fmt_hm),
            "Gap": queue["Gap (min)"].map(fmt_dur),
            "Waiting": queue["Waiting (min)"].map(fmt_dur),
            "Status": queue.apply(status, axis=1),
        }
    )
    return out


# ------------------------------------------------------------------- zones
def zone_detail(sim: Simulation, zone: int, clock) -> pd.DataFrame:
    """LLs currently in a zone: staged ones and ones reserved by a lane (DSH-9)."""
    t = sim.to_secs(clock)
    rows = []
    for i in range(sim.n):
        if sim.zone[i] != zone:
            continue
        if sim.finish[i] <= t < sim.left[i]:
            state, in_staging = "Staged", (t - sim.finish[i]) / 60
        elif sim.reserved[i] and sim.call[i] <= t < sim.finish[i]:
            state, in_staging = "In lane (reserved)", 0.0
        else:
            continue
        rows.append(
            {
                "LL": sim.ll[i],
                "Forwarder": sim.data["Forwarder"].iloc[i] if "Forwarder" in sim.data else "",
                "State": state,
                "Cartons": sim.cartons[i],
                "Pallets": sim.pallets[i],
                "Time in staging": fmt_dur(in_staging) if state == "Staged" else "",
                "Handover": fmt_hm(sim.to_dt(sim.arrival[i])),
                "_sort": in_staging,
            }
        )
    out = pd.DataFrame(rows, columns=["LL", "Forwarder", "State", "Cartons", "Pallets",
                                      "Time in staging", "Handover", "_sort"])
    return out.sort_values("_sort", ascending=False).drop(columns="_sort").reset_index(drop=True)


def occupancy_series(sim: Simulation, step_min: int = 5) -> pd.DataFrame:
    """Pallets used (staged + reserved) per zone over the day (DSH-10)."""
    start, end = sim.start_time, sim.end_time
    times = pd.date_range(start, end, freq=f"{step_min}min")
    secs = np.array([(t - start).total_seconds() for t in times])
    call, left = np.array(sim.call), np.array(sim.left)
    zone, pallets = np.array(sim.zone), np.array(sim.pallets)
    reserved = np.array(sim.reserved)
    frames = []
    for z in sim.zones:
        mask = (zone == z) & reserved
        used = [
            int(pallets[mask][(call[mask] <= s) & (s < left[mask])].sum()) for s in secs
        ]
        frames.append(pd.DataFrame({"Time": times, "Zone": f"Zone {z}", "Pallets used": used}))
    return pd.concat(frames, ignore_index=True)


# ------------------------------------------------------------------- events
def recent_staged(sim: Simulation, clock, n: int = 8) -> pd.DataFrame:
    """The last LLs to be staged, with time from cut to staging (DSH-16)."""
    t = sim.to_secs(clock)
    rows = []
    for i in range(sim.n):
        if sim.finish[i] <= t:
            rows.append(
                {
                    "Staged at": fmt_hm(sim.to_dt(sim.finish[i])),
                    "LL": sim.ll[i],
                    "Zone": sim.zone[i],
                    "Cartons": sim.cartons[i],
                    "Cut to staged": fmt_dur((sim.finish[i] - sim.cut[i]) / 60),
                    "Late": fmt_dur(sim.lateness_s(i) / 60) if sim.lateness_s(i) > 0 else "",
                    "_t": sim.finish[i],
                }
            )
    out = pd.DataFrame(rows, columns=["Staged at", "LL", "Zone", "Cartons", "Cut to staged", "Late", "_t"])
    return out.sort_values("_t", ascending=False).head(n).drop(columns="_t").reset_index(drop=True)


def event_log_until(log: pd.DataFrame, sim: Simulation, clock, n: int = 40) -> pd.DataFrame:
    """The latest events up to the clock, newest first (DSH-17)."""
    t = sim.to_secs(clock)
    shown = log[log["time"] <= t].tail(n).iloc[::-1]
    out = pd.DataFrame(
        {
            "Time": shown["clock"].map(lambda x: x.strftime("%H:%M:%S")),
            "Event": shown["event"].str.replace("_", " "),
            "LL": shown["LL"],
            "Lane": shown["lane"].map(lambda v: "" if v < 0 else int(v) + 1),
        }
    )
    return out.reset_index(drop=True)
