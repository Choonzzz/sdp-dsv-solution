"""Simulation engine for the M4 dashboard mockup.

Implements section 5 of ``PRD.md`` (v0.8). It has no UI dependency. The day is
simulated once as a discrete-event simulation, and ``Simulation.state_at`` then
reads the dashboard state for any clock time from the recorded timestamps.

Rules in short:
  * One priority queue, key = Handover Time - Added Date (smallest gap first,
    ties to the earlier Added Date). The key never changes.
  * 12 lanes (default), each a FIFO queue. Processing time = cartons / throughput.
  * An LL may leave the queue only if its zone has room for its pallets
    (staged + in-lane pallets + LL pallets <= zone capacity). LLs whose zone is
    full are skipped. LLs whose forwarder has already arrived skip the zone check.
  * An LL joins the lane with the smallest queue only if queue + cartons <= cap.
    An LL bigger than the cap needs an empty lane. An LL that does not fit a
    lane blocks the queue.
  * A lane's queue size falls only when an LL finishes. A finished LL is staged
    at once. At Handover Time it leaves staging.
  * An LL not staged by its Handover Time is late. It is handed over the moment
    it is staged.
"""
from __future__ import annotations

import bisect
import heapq
import itertools
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "Mockup_Data.xlsx"
REQUIRED_COLUMNS = ["LL", "Cartons", "Added Date", "Handover Time", "Zone", "Pallets"]

# Order in which simultaneous events are applied (lowest first).
_HANDOVER, _FINISH, _ARRIVAL, _CUT = 0, 1, 2, 3


@dataclass(frozen=True)
class Params:
    """Adjustable parameters (PRD section 4.3)."""

    n_lanes: int = 12
    lane_throughput: float = 100.0  # cartons per hour, per lane
    lane_queue_cap: int = 100  # cartons
    zone_capacity: int = 48  # pallets per zone
    # Diagnostic switches, used only to reproduce the reference rows of PRD section 8.
    zone_gate: bool = True  # False: ignore zone fullness when calling out
    arrived_skips_zone_check: bool = True  # False: arrived LLs still obey the zone gate


def load_data(path: Path | str = DATA_PATH) -> pd.DataFrame:
    """Read ``Mockup_Data.xlsx`` (one row per LL)."""
    return pd.read_excel(path)


class Simulation:
    """Runs the day once on construction. All times are seconds from ``t0``."""

    def __init__(self, data: pd.DataFrame, params: Params | None = None):
        self.params = params or Params()
        missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
        if missing:
            raise ValueError(f"Input is missing columns: {missing}")
        self.data = (
            data.sort_values(["Added Date", "LL"]).reset_index(drop=True).copy()
        )
        self.n = len(self.data)
        self.t0 = self.data["Added Date"].min()
        self._load_arrays()
        self._run()

    # ------------------------------------------------------------------ setup
    def _secs(self, series: pd.Series) -> list[float]:
        return [(v - self.t0).total_seconds() for v in series]

    def _load_arrays(self) -> None:
        d = self.data
        self.ll = d["LL"].tolist()
        self.cartons = d["Cartons"].astype(int).tolist()
        self.pallets = d["Pallets"].astype(int).tolist()
        self.zone = d["Zone"].astype(int).tolist()
        self.cut = self._secs(d["Added Date"])
        self.arrival = self._secs(d["Handover Time"])  # forwarder arrival = handover
        self.gap = [a - c for a, c in zip(self.arrival, self.cut)]
        self.key = [(self.gap[i], self.cut[i], self.ll[i], i) for i in range(self.n)]
        self.zones = sorted(set(self.zone))
        self.proc = [
            c / self.params.lane_throughput * 3600.0 for c in self.cartons
        ]

    # ------------------------------------------------------------------- core
    def _run(self) -> None:
        p, n = self.params, self.n
        nan = float("nan")
        # Per-LL results, indexed like self.data.
        self.call = [nan] * n  # left the priority queue (called out)
        self.call_seq = [-1] * n  # order in which LLs were called out
        self.lane = [-1] * n
        self.start = [nan] * n  # processing started
        self.finish = [nan] * n  # processing finished = staged
        self.left = [nan] * n  # left staging (handed over)
        self.reserved = [False] * n  # pallets reserved in the zone while in lane
        self.bypass = [False] * n  # skipped the zone check (forwarder arrived)
        self.events: list[dict] = []

        self._queue: list[tuple] = []  # sorted list of keys
        self._lane_q = [0] * p.n_lanes  # cartons in each lane's queue
        self._lane_free = [0.0] * p.n_lanes  # time each lane's last LL finishes
        self._zone_used = {z: 0 for z in self.zones}  # staged + reserved pallets
        self._zone_staged = {z: 0 for z in self.zones}  # staged pallets only
        self._seq = itertools.count()
        self._calls = itertools.count()

        self.max_queue_len = 0
        self.peak_used = {z: 0 for z in self.zones}
        self.peak_staged = {z: 0 for z in self.zones}
        self.peak_lane_q = 0

        heap: list[tuple] = []
        for i in range(n):
            heapq.heappush(heap, (self.cut[i], _CUT, next(self._seq), i))
            # An arrival event lets a waiting LL skip the zone check on time.
            heapq.heappush(heap, (self.arrival[i], _ARRIVAL, next(self._seq), i))
        self._heap = heap

        while heap:
            t = heap[0][0]
            while heap and heap[0][0] == t:
                _, kind, _, i = heapq.heappop(heap)
                if kind == _CUT:
                    bisect.insort(self._queue, self.key[i])
                    self._log(t, "cut", i)
                elif kind == _FINISH:
                    self._on_finish(t, i)
                elif kind == _HANDOVER:
                    self._on_handover(t, i)
                # _ARRIVAL needs no state change, only a dispatch.
            self._dispatch(t)
            self._track_peaks()

    def _log(self, t: float, event: str, i: int, **extra) -> None:
        self.events.append(
            {"time": t, "event": event, "LL": self.ll[i], "lane": self.lane[i], **extra}
        )

    def _on_finish(self, t: float, i: int) -> None:
        lane = self.lane[i]
        self._lane_q[lane] -= self.cartons[i]
        z = self.zone[i]
        if t > self.arrival[i]:
            # Forwarder already here: staged and handed over at once (late).
            self.left[i] = t
            if self.reserved[i]:
                self._zone_used[z] -= self.pallets[i]
            self._log(t, "staged", i, late_s=t - self.arrival[i])
            self._log(t, "handover", i, late_s=t - self.arrival[i])
        else:
            self._zone_staged[z] += self.pallets[i]
            self._log(t, "staged", i, late_s=0.0)
            heapq.heappush(self._heap, (self.arrival[i], _HANDOVER, next(self._seq), i))

    def _on_handover(self, t: float, i: int) -> None:
        z = self.zone[i]
        self._zone_used[z] -= self.pallets[i]
        self._zone_staged[z] -= self.pallets[i]
        self.left[i] = t
        self._log(t, "handover", i, late_s=0.0)

    def _dispatch(self, t: float) -> None:
        """Move LLs from the priority queue into lanes while the rules allow."""
        p = self.params
        while self._queue:
            # Zone gate: the first LL in key order that has room, or whose forwarder
            # has already arrived. LLs whose zone is full are skipped.
            cand_pos = None
            for pos, key in enumerate(self._queue):
                i = key[3]
                if (
                    not p.zone_gate
                    or (p.arrived_skips_zone_check and t >= self.arrival[i])
                    or self._zone_used[self.zone[i]] + self.pallets[i] <= p.zone_capacity
                ):
                    cand_pos = pos
                    break
            if cand_pos is None:
                return
            i = self._queue[cand_pos][3]

            # Lane check: smallest queue, ties to the lowest lane number.
            lane = min(range(p.n_lanes), key=lambda L: (self._lane_q[L], L))
            q, c = self._lane_q[lane], self.cartons[i]
            fits = q + c <= p.lane_queue_cap or (q == 0 and c > p.lane_queue_cap)
            if not fits:
                return  # this LL blocks the queue

            del self._queue[cand_pos]
            # Only an LL that actually skipped the check reserves nothing. With the
            # zone gate off, or when arrived LLs obey the gate, it reserves as normal.
            arrived = t >= self.arrival[i] and p.zone_gate and p.arrived_skips_zone_check
            start = max(t, self._lane_free[lane])
            finish = start + self.proc[i]
            self._lane_free[lane] = finish
            self._lane_q[lane] += c
            self.peak_lane_q = max(self.peak_lane_q, self._lane_q[lane])
            self.call[i], self.call_seq[i] = t, next(self._calls)
            self.lane[i], self.start[i], self.finish[i] = lane, start, finish
            if arrived:
                self.bypass[i] = True
            else:
                self.reserved[i] = True
                self._zone_used[self.zone[i]] += self.pallets[i]
            heapq.heappush(self._heap, (finish, _FINISH, next(self._seq), i))
            self._log(t, "call_out", i, bypass=arrived)

    def _track_peaks(self) -> None:
        self.max_queue_len = max(self.max_queue_len, len(self._queue))
        for z in self.zones:
            self.peak_used[z] = max(self.peak_used[z], self._zone_used[z])
            self.peak_staged[z] = max(self.peak_staged[z], self._zone_staged[z])

    # ---------------------------------------------------------------- results
    def to_dt(self, seconds: float) -> pd.Timestamp:
        return self.t0 + pd.Timedelta(seconds=seconds)

    def to_secs(self, t) -> float:
        if isinstance(t, (int, float)):
            return float(t)
        return (pd.Timestamp(t) - self.t0).total_seconds()

    @property
    def start_time(self) -> pd.Timestamp:
        return self.t0

    @property
    def end_time(self) -> pd.Timestamp:
        return self.to_dt(max(self.left))

    def lateness_s(self, i: int) -> float:
        """Seconds the LL was staged after its forwarder arrived (0 if on time)."""
        return max(0.0, self.finish[i] - self.arrival[i])

    def ll_table(self) -> pd.DataFrame:
        """One row per LL with every timestamp the simulation produced."""
        d = self.data[["LL", "Forwarder", "Zone", "Cartons", "Pallets"]].copy() \
            if "Forwarder" in self.data else self.data[["LL", "Zone", "Cartons", "Pallets"]].copy()
        d["Added"] = self.data["Added Date"]
        d["Arrival"] = self.data["Handover Time"]
        d["Called out"] = [self.to_dt(x) for x in self.call]
        d["Lane"] = self.lane
        d["Processing start"] = [self.to_dt(x) for x in self.start]
        d["Staged"] = [self.to_dt(x) for x in self.finish]
        d["Left staging"] = [self.to_dt(x) for x in self.left]
        d["Queue wait (min)"] = [(a - b) / 60 for a, b in zip(self.call, self.cut)]
        d["Cut to staged (min)"] = [(a - b) / 60 for a, b in zip(self.finish, self.cut)]
        d["Late (min)"] = [self.lateness_s(i) / 60 for i in range(self.n)]
        d["Time in staging (min)"] = [(l - f) / 60 for l, f in zip(self.left, self.finish)]
        d["Skipped zone check"] = self.bypass
        return d

    def event_log(self) -> pd.DataFrame:
        log = pd.DataFrame(self.events)
        log.insert(0, "clock", [self.to_dt(t) for t in log["time"]])
        return log

    def summary(self) -> dict:
        """Headline figures, comparable with PRD section 8."""
        t = self.ll_table()
        late = t[t["Late (min)"] > 0]["Late (min)"]
        not_late = t[t["Late (min)"] == 0]
        return {
            "LLs": self.n,
            "max LLs in queue": self.max_queue_len,
            "LLs that waited": int((t["Queue wait (min)"] > 0.01).sum()),
            "queue wait mean (min)": t["Queue wait (min)"].mean(),
            "queue wait max (min)": t["Queue wait (min)"].max(),
            "cut to staged mean (min)": t["Cut to staged (min)"].mean(),
            "cut to staged max (min)": t["Cut to staged (min)"].max(),
            "late LLs": int(len(late)),
            "late mean (min)": late.mean() if len(late) else 0.0,
            "late longest (min)": late.max() if len(late) else 0.0,
            "late total (min)": late.sum() if len(late) else 0.0,
            "staging time mean, not late (min)": not_late["Time in staging (min)"].mean(),
            "staging time max, not late (min)": not_late["Time in staging (min)"].max(),
            "LLs that skipped the zone check": int(sum(self.bypass)),
            "peak staged pallets per zone": dict(self.peak_staged),
            "peak used pallets per zone": dict(self.peak_used),
            "peak lane queue (cartons)": self.peak_lane_q,
        }

    # --------------------------------------------------------------- snapshot
    def state_at(self, clock) -> dict:
        """Dashboard state at ``clock`` (a Timestamp or seconds from ``t0``).

        An event at time T has already happened for any clock >= T, so the state is
        always the one left after all dispatching at that time.
        """
        t = self.to_secs(clock)
        p, idx = self.params, range(self.n)

        in_queue = [i for i in idx if self.cut[i] <= t < self.call[i]]
        in_lane = [i for i in idx if self.call[i] <= t < self.finish[i]]
        staged = [i for i in idx if self.finish[i] <= t < self.left[i]]
        completed = [i for i in idx if self.left[i] <= t]
        cut_so_far = [i for i in idx if self.cut[i] <= t]

        # Zone usage: staged pallets plus pallets reserved by LLs in a lane.
        staged_p = {z: 0 for z in self.zones}
        reserved_p = {z: 0 for z in self.zones}
        for i in staged:
            staged_p[self.zone[i]] += self.pallets[i]
        for i in in_lane:
            if self.reserved[i]:
                reserved_p[self.zone[i]] += self.pallets[i]
        used = {z: staged_p[z] + reserved_p[z] for z in self.zones}

        # Priority queue, in call-out order, with the reason each LL is held.
        rows, next_marked = [], False
        for pos, i in enumerate(sorted(in_queue, key=lambda k: self.key[k]), start=1):
            arrived = t >= self.arrival[i]
            zone_full = not arrived and used[self.zone[i]] + self.pallets[i] > p.zone_capacity
            if zone_full:
                reason = f"zone {self.zone[i]} full"
            else:
                reason = "no lane space"
            is_next = False
            if not zone_full and not next_marked:
                is_next, next_marked = True, True
            rows.append(
                {
                    "Position": pos,
                    "LL": self.ll[i],
                    "Forwarder": self.data["Forwarder"].iloc[i] if "Forwarder" in self.data else "",
                    "Zone": self.zone[i],
                    "Cartons": self.cartons[i],
                    "Pallets": self.pallets[i],
                    "Cut": self.to_dt(self.cut[i]),
                    "Arrival": self.to_dt(self.arrival[i]),
                    "Gap (min)": self.gap[i] / 60,
                    "Waiting (min)": (t - self.cut[i]) / 60,
                    "Late": arrived,
                    "Late for (min)": max(0.0, (t - self.arrival[i]) / 60),
                    "Reason held": reason,
                    "Next": is_next,
                }
            )
        queue = pd.DataFrame(rows)

        # Lanes.
        lanes = []
        for L in range(p.n_lanes):
            members = sorted(
                (i for i in in_lane if self.lane[i] == L), key=lambda k: self.call_seq[k]
            )
            current = next((i for i in members if self.start[i] <= t), None)
            lanes.append(
                {
                    "Lane": L + 1,
                    "Queue (cartons)": sum(self.cartons[i] for i in members),
                    "Cap": p.lane_queue_cap,
                    "Processing": self.ll[current] if current is not None else None,
                    "Remaining (min)": (self.finish[current] - t) / 60 if current is not None else None,
                    "Waiting behind": [self.ll[i] for i in members if i != current],
                }
            )

        # Zones.
        waiting_for_zone = {z: 0 for z in self.zones}
        for i in in_queue:
            if t < self.arrival[i] and used[self.zone[i]] + self.pallets[i] > p.zone_capacity:
                waiting_for_zone[self.zone[i]] += 1
        zrows = []
        for z in self.zones:
            here = [i for i in staged if self.zone[i] == z]
            dwell = [(t - self.finish[i]) / 60 for i in here]
            zrows.append(
                {
                    "Zone": z,
                    "Capacity": p.zone_capacity,
                    "Staged pallets": staged_p[z],
                    "Reserved pallets": reserved_p[z],
                    "Used": used[z],
                    "Used %": 100 * used[z] / p.zone_capacity,
                    "Staged LLs": len(here),
                    "LLs queued for this zone (zone full)": waiting_for_zone[z],
                    "Staging time mean (min)": sum(dwell) / len(dwell) if dwell else 0.0,
                    "Staging time max (min)": max(dwell) if dwell else 0.0,
                }
            )
        zones = pd.DataFrame(zrows)

        # Late LLs: forwarder has arrived and the LL was not staged by then.
        late_idx = [i for i in idx if self.arrival[i] <= t and self.finish[i] > self.arrival[i]]
        late_now = [i for i in late_idx if self.finish[i] > t]
        late_min = {i: (min(t, self.finish[i]) - self.arrival[i]) / 60 for i in late_idx}
        late_now_df = pd.DataFrame(
            [
                {
                    "LL": self.ll[i],
                    "Zone": self.zone[i],
                    "Arrived": self.to_dt(self.arrival[i]),
                    "Late for (min)": late_min[i],
                    "State": "waiting in queue" if t < self.call[i] else "in lane",
                }
                for i in late_now
            ]
        )
        vals = list(late_min.values())

        carton_total = sum(self.cartons)
        return {
            "clock": self.to_dt(t),
            "counts": {
                "cut so far": len(cut_so_far),
                "waiting": len(in_queue),
                "in lane": len(in_lane),
                "staged": len(staged),
                "completed": len(completed),
            },
            "workload": {
                "LLs cut": len(cut_so_far),
                "LLs total": self.n,
                "cartons cut": sum(self.cartons[i] for i in cut_so_far),
                "cartons total": carton_total,
            },
            "queue": queue,
            "lanes": lanes,
            "zones": zones,
            "late_now": late_now_df,
            "late_summary": {
                "late LLs so far": len(late_idx),
                "late now": len(late_now),
                "mean (min)": sum(vals) / len(vals) if vals else 0.0,
                "longest (min)": max(vals) if vals else 0.0,
                "total (min)": sum(vals),
            },
            "cartons in lanes": sum(self.cartons[i] for i in in_lane),
        }


def run(params: Params | None = None, data: pd.DataFrame | None = None) -> Simulation:
    """Convenience: simulate the real day with the given parameters."""
    return Simulation(load_data() if data is None else data, params)


if __name__ == "__main__":
    sim = run()
    for k, v in sim.summary().items():
        print(f"{k:40s} {v}")
