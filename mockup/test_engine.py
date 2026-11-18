"""Tests for engine.py: the build checks in PRD section 10, plus small scenarios.

Run from the repository root:
    .venv/Scripts/python.exe -m pytest mockup -v
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import Params, Simulation, load_data, run  # noqa: E402

BASE = pd.Timestamp("2026-09-08 08:00:00")


def make(rows):
    """Build an input table. Each row is (LL, cartons, cut_min, arrival_min, zone, pallets)."""
    return pd.DataFrame(
        [
            {
                "LL": ll,
                "Cartons": c,
                "Added Date": BASE + pd.Timedelta(minutes=cut),
                "Handover Time": BASE + pd.Timedelta(minutes=arr),
                "Zone": z,
                "Pallets": p,
                "Forwarder": "A",
            }
            for ll, c, cut, arr, z, p in rows
        ]
    )


def idx(sim, ll):
    return sim.ll.index(ll)


# --------------------------------------------------------------------------
# Small scenarios, one rule each
# --------------------------------------------------------------------------
def test_processing_time_is_cartons_over_throughput():
    # 50 cartons at 100 per hour = 30 minutes. Staged the moment it finishes.
    sim = Simulation(make([(1, 50, 0, 600, 1, 1)]), Params(n_lanes=1))
    i = idx(sim, 1)
    assert (sim.finish[i] - sim.start[i]) / 60 == pytest.approx(30.0)
    assert sim.call[i] == sim.cut[i]
    assert sim.left[i] == sim.arrival[i]
    assert sim.lateness_s(i) == 0.0


def test_a_lane_processes_one_ll_at_a_time():
    # One lane, two LLs cut a minute apart: the second waits in the priority queue.
    sim = Simulation(make([(1, 50, 0, 900, 1, 1), (2, 10, 1, 800, 1, 1)]), Params(n_lanes=1))
    assert sim.call[idx(sim, 2)] == sim.finish[idx(sim, 1)]
    assert (sim.call[idx(sim, 2)] - sim.cut[idx(sim, 2)]) / 60 == pytest.approx(29.0)


def test_a_second_lane_takes_the_second_ll_at_once():
    sim = Simulation(make([(1, 50, 0, 900, 1, 1), (2, 10, 1, 800, 1, 1)]), Params(n_lanes=2))
    assert sim.call[idx(sim, 2)] == sim.cut[idx(sim, 2)]
    assert sim.lane[idx(sim, 1)] == 0
    assert sim.lane[idx(sim, 2)] == 1


def test_lowest_numbered_free_lane_is_used():
    # LL 1 takes lane 0 and LL 2 takes lane 1. When lane 0 frees first, LL 3 goes there.
    rows = [(1, 10, 0, 900, 1, 1), (2, 50, 1, 900, 1, 1), (3, 10, 20, 900, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=2))
    assert [sim.lane[idx(sim, k)] for k in (1, 2, 3)] == [0, 1, 0]


def test_no_carton_limit_on_a_lane():
    # A 205-carton LL goes straight into a free lane and takes about 2 h 3 min.
    sim = Simulation(make([(1, 205, 0, 900, 1, 5)]), Params(n_lanes=1))
    i = idx(sim, 1)
    assert sim.call[i] == sim.cut[i]
    assert (sim.finish[i] - sim.start[i]) / 60 == pytest.approx(123.0)


def test_priority_is_soonest_arrival_first():
    rows = [
        (1, 100, 0, 900, 1, 2),  # fills the only lane
        (2, 10, 5, 1000, 1, 1),  # arrives at 1000, cut first
        (3, 10, 6, 100, 1, 1),  # arrives at 100, cut later, higher priority
    ]
    sim = Simulation(make(rows), Params(n_lanes=1))
    # Each of the small LLs needs the lane for 6 minutes, so LL 3 goes first, then LL 2.
    assert sim.call[idx(sim, 3)] == sim.finish[idx(sim, 1)]
    assert sim.call[idx(sim, 2)] == sim.finish[idx(sim, 3)]


def test_the_old_gap_order_is_no_longer_used():
    # LL 1 keeps the only lane busy for 123 minutes. LL 2 and LL 3 are both waiting by then.
    #   LL 2: cut at 5, arrives at 200, gap 195 min. Arrives sooner.
    #   LL 3: cut at 100, arrives at 250, gap 150 min. Smaller gap.
    # The old rule (smallest gap) would send LL 3 first. Soonest arrival sends LL 2 first.
    rows = [(1, 205, 0, 900, 1, 5), (2, 10, 5, 200, 1, 1), (3, 10, 100, 250, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=1))
    assert sim.call_seq[idx(sim, 2)] < sim.call_seq[idx(sim, 3)]


@pytest.mark.parametrize(
    "rows",
    [
        # Same arrival time: the earlier cut goes first.
        [(1, 100, 0, 900, 1, 2), (2, 10, 5, 300, 1, 1), (3, 10, 6, 300, 1, 1)],
        # Same arrival and same cut time: the lower LL number goes first.
        [(1, 100, 0, 900, 1, 2), (3, 10, 5, 300, 1, 1), (2, 10, 5, 300, 1, 1)],
    ],
)
def test_ties_go_to_the_earlier_cut_then_the_lower_ll_number(rows):
    sim = Simulation(make(rows), Params(n_lanes=1))
    assert sim.call_seq[idx(sim, 2)] < sim.call_seq[idx(sim, 3)]


def test_zone_gate_skips_a_full_zone():
    # Zone 1 holds 2 pallets. LL 1 fills it. LL 2 (zone 1) is skipped, LL 3 (zone 2) goes ahead.
    rows = [
        (1, 10, 0, 120, 1, 2),
        (2, 10, 1, 130, 1, 1),  # arrives before LL 3, but its zone is full
        (3, 10, 2, 500, 2, 1),
    ]
    sim = Simulation(make(rows), Params(n_lanes=2, zone_capacity=2))
    assert sim.call[idx(sim, 3)] == sim.cut[idx(sim, 3)]
    # LL 2 is called when LL 1 leaves staging at its handover time (minute 120).
    assert sim.call[idx(sim, 2)] == sim.arrival[idx(sim, 1)]


def test_zone_never_exceeds_capacity_in_a_small_run():
    rows = [(k, 10, k, 600 + k, 1, 1) for k in range(1, 8)]
    sim = Simulation(make(rows), Params(n_lanes=3, zone_capacity=3))
    assert max(sim.peak_used.values()) <= 3


def test_pallets_must_fit():
    # Zone has 3 pallets, 2 used. A 2-pallet LL does not fit but a 1-pallet LL does.
    rows = [
        (1, 10, 0, 300, 1, 2),
        (2, 10, 1, 400, 1, 2),  # needs 2, only 1 free: held
        (3, 10, 2, 500, 1, 1),  # fits: goes ahead although it arrives later
    ]
    sim = Simulation(make(rows), Params(n_lanes=2, zone_capacity=3))
    assert sim.call[idx(sim, 3)] == sim.cut[idx(sim, 3)]
    assert sim.call[idx(sim, 2)] == sim.arrival[idx(sim, 1)]


def test_arrived_ll_skips_the_zone_check_and_is_late():
    # Zone 1 is full until minute 300. LL 2 arrives at minute 60 while still queued.
    rows = [(1, 10, 0, 300, 1, 2), (2, 10, 1, 60, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=2, zone_capacity=2))
    i = idx(sim, 2)
    assert sim.bypass[i]
    assert not sim.reserved[i]
    # Called the moment its forwarder arrives, with no other event to trigger it.
    assert sim.call[i] == sim.arrival[i]
    assert sim.left[i] == sim.finish[i]  # handed over at once
    assert sim.lateness_s(i) / 60 == pytest.approx(6.0)  # 10 cartons = 6 minutes


def test_all_lanes_busy_holds_every_ll():
    # One lane. LL 2 passes the zone gate but must wait for the lane, and so must LL 3 behind it.
    rows = [(1, 50, 0, 900, 1, 1), (2, 10, 1, 800, 1, 1), (3, 10, 2, 850, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=1))
    assert sim.call[idx(sim, 2)] == sim.finish[idx(sim, 1)]
    assert sim.call[idx(sim, 3)] == sim.finish[idx(sim, 2)]


def test_late_only_when_staged_after_arrival():
    late = Simulation(make([(1, 100, 0, 30, 1, 2)]), Params(n_lanes=1)).summary()
    assert late["late LLs"] == 1  # takes 60 minutes, forwarder arrives at 30
    assert late["late longest (min)"] == pytest.approx(30.0)
    on_time = Simulation(make([(1, 100, 0, 61, 1, 2)]), Params(n_lanes=1)).summary()
    assert on_time["late LLs"] == 0


def test_staged_exactly_at_arrival_is_on_time():
    sim = Simulation(make([(1, 100, 0, 60, 1, 2)]), Params(n_lanes=1))
    assert sim.summary()["late LLs"] == 0


def test_missing_columns_are_rejected():
    with pytest.raises(ValueError):
        Simulation(make([(1, 10, 0, 100, 1, 1)]).drop(columns=["Zone"]))


def test_snapshot_lists_the_processing_ll_and_idle_lanes():
    sim = Simulation(make([(1, 50, 0, 900, 1, 1)]), Params(n_lanes=3))
    state = sim.state_at(BASE + pd.Timedelta(minutes=10))
    lanes = {lane["Lane"]: lane for lane in state["lanes"]}
    assert lanes[1]["Processing"] == 1
    assert lanes[1]["Remaining (min)"] == pytest.approx(20.0)
    assert lanes[1]["Progress"] == pytest.approx(10 / 30)
    assert lanes[2]["Processing"] is None and lanes[3]["Processing"] is None
    assert list(state["in_lanes"]["LL"]) == [1]
    assert state["counts"]["in lane"] == 1


def test_snapshot_time_to_arrival_counts_down_and_goes_negative():
    # One lane busy for 100 minutes, so LL 2 waits in the queue.
    rows = [(1, 100, 0, 900, 1, 2), (2, 10, 1, 30, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=1))
    early = sim.state_at(BASE + pd.Timedelta(minutes=10))["queue"].iloc[0]
    assert early["Time to arrival (min)"] == pytest.approx(20.0)
    assert not early["Late"]
    later = sim.state_at(BASE + pd.Timedelta(minutes=40))["queue"].iloc[0]
    assert later["Time to arrival (min)"] == pytest.approx(-10.0)
    assert later["Late"] and later["Late for (min)"] == pytest.approx(10.0)


# --------------------------------------------------------------------------
# The real day: build checks from PRD section 10
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def data():
    return load_data()


@pytest.fixture(scope="module")
def sim(data):
    return Simulation(data)


@pytest.fixture(scope="module")
def event_times(sim):
    return sorted(set(sim.cut) | set(sim.call) | set(sim.finish) | set(sim.left))


def zone_used_at(sim, t, upto_seq=None):
    """Independent recount of reserved + staged pallets per zone at time t."""
    used = {z: 0 for z in sim.zones}
    for i in range(sim.n):
        if not sim.reserved[i]:
            continue
        if upto_seq is not None and sim.call_seq[i] >= upto_seq:
            continue
        if sim.call[i] <= t < sim.left[i]:
            used[sim.zone[i]] += sim.pallets[i]
    return used


def test_replay_is_deterministic(data, sim):
    again = Simulation(data)
    assert sim.call == again.call
    assert sim.finish == again.finish
    assert sim.left == again.left
    assert sim.lane == again.lane


def test_every_ll_is_processed(sim):
    assert sim.n == 327
    assert not any(pd.isna(x) for x in sim.call + sim.finish + sim.left)


def test_timestamps_are_in_order(sim):
    for i in range(sim.n):
        assert sim.call[i] >= sim.cut[i]
        assert sim.start[i] == sim.call[i]
        assert sim.finish[i] > sim.start[i]
        assert sim.left[i] >= sim.finish[i]


def test_real_processing_time_is_cartons_over_throughput(sim):
    for i in range(sim.n):
        expected = sim.cartons[i] / sim.params.lane_throughput * 3600
        assert sim.finish[i] - sim.start[i] == pytest.approx(expected)


def test_a_lane_never_processes_two_lls_at_once(sim):
    for lane in range(sim.params.n_lanes):
        ids = sorted((i for i in range(sim.n) if sim.lane[i] == lane), key=lambda k: sim.call_seq[k])
        for a, b in zip(ids, ids[1:]):
            assert sim.start[b] >= sim.finish[a], f"lane {lane}"


def test_at_most_one_ll_per_lane_in_any_snapshot(sim, event_times):
    for t in event_times[::9]:
        state = sim.state_at(t)
        assert state["counts"]["in lane"] <= sim.params.n_lanes
        assert len(state["in_lanes"]) == state["counts"]["in lane"]
        assert state["in_lanes"]["Lane"].is_unique if len(state["in_lanes"]) else True


def test_an_ll_enters_the_lowest_numbered_free_lane(sim):
    for i in sorted(range(sim.n), key=lambda k: sim.call_seq[k]):
        t = sim.call[i]
        busy = {
            sim.lane[j]
            for j in range(sim.n)
            if sim.call_seq[j] < sim.call_seq[i] and sim.start[j] <= t < sim.finish[j]
        }
        free = [lane for lane in range(sim.params.n_lanes) if lane not in busy]
        assert sim.lane[i] == free[0], f"LL {sim.ll[i]}"


def test_zone_never_exceeds_capacity(sim, event_times):
    cap = sim.params.zone_capacity
    for t in event_times:
        for z, used in zone_used_at(sim, t).items():
            assert used <= cap, f"zone {z} at {t}"
    assert max(sim.peak_used.values()) <= cap


def test_call_out_respects_zone_gate_and_arrival_order(sim):
    """At every call-out the LL chosen is the first in arrival order that passes the zone
    gate, so every waiting LL ahead of it was held by a full zone. A lane must also have
    been free, so when every lane is busy nobody is called out."""
    cap = sim.params.zone_capacity
    for i in sorted(range(sim.n), key=lambda k: sim.call_seq[k]):
        t = sim.call[i]
        used = zone_used_at(sim, t, upto_seq=sim.call_seq[i])
        arrived = t >= sim.arrival[i]
        if not arrived:
            assert used[sim.zone[i]] + sim.pallets[i] <= cap, f"LL {sim.ll[i]}"
        assert sim.bypass[i] == arrived
        for j in range(sim.n):
            waiting = sim.cut[j] <= t and sim.call_seq[j] > sim.call_seq[i]
            if waiting and sim.key[j] < sim.key[i]:
                passes = t >= sim.arrival[j] or used[sim.zone[j]] + sim.pallets[j] <= cap
                assert not passes, f"LL {sim.ll[j]} was waiting ahead of LL {sim.ll[i]} and could go"


def test_late_count_and_lateness(sim):
    late = {i for i in range(sim.n) if sim.finish[i] > sim.arrival[i]}
    assert sim.summary()["late LLs"] == len(late)
    for i in range(sim.n):
        assert sim.lateness_s(i) == pytest.approx(max(0.0, sim.finish[i] - sim.arrival[i]))
        if i in late:
            assert sim.left[i] == sim.finish[i]  # handed over at staging
        else:
            assert sim.left[i] == sim.arrival[i]  # leaves at handover time


def test_counts_add_up_at_every_time(sim, event_times):
    for t in event_times[::7] + [sim.start_time, sim.end_time]:
        c = sim.state_at(t)["counts"]
        assert c["waiting"] + c["in lane"] + c["staged"] + c["completed"] == c["cut so far"]


def test_zone_pallets_and_lls_equal_staged_plus_reserved(sim, event_times):
    for t in event_times[::11]:
        zones = sim.state_at(t)["zones"]
        tt = sim.to_secs(t)
        for _, row in zones.iterrows():
            z = int(row["Zone"])
            staged = [i for i in range(sim.n) if sim.zone[i] == z and sim.finish[i] <= tt < sim.left[i]]
            reserved = [
                i for i in range(sim.n)
                if sim.zone[i] == z and sim.reserved[i] and sim.call[i] <= tt < sim.finish[i]
            ]
            assert row["Staged pallets"] == sum(sim.pallets[i] for i in staged)
            assert row["Reserved pallets"] == sum(sim.pallets[i] for i in reserved)
            assert row["Used"] == row["Staged pallets"] + row["Reserved pallets"]
            assert row["Staged LLs"] == len(staged)
            assert row["Reserved LLs"] == len(reserved)
            assert row["LLs in zone"] == len(staged) + len(reserved)


def test_snapshot_queue_is_in_arrival_order_with_one_next(sim, event_times):
    found_held = False
    for t in event_times[::5]:
        q = sim.state_at(t)["queue"]
        if q.empty:
            continue
        assert list(q["Position"]) == list(range(1, len(q) + 1))
        keys = list(zip(q["Arrival"], q["Cut"], q["LL"]))
        assert keys == sorted(keys)
        assert q["Time to arrival (min)"].is_monotonic_increasing
        assert int(q["Next"].sum()) <= 1
        if q["Reason held"].str.contains("zone").any():
            found_held = True
    assert found_held, "expected some LLs held back by a full zone"


def test_snapshot_in_lane_rows_are_soonest_arrival_first(sim, event_times):
    for t in event_times[::13]:
        rows = sim.state_at(t)["in_lanes"]
        if len(rows) > 1:
            assert rows["Time to arrival (min)"].is_monotonic_increasing


def test_snapshot_before_start_and_after_end(sim):
    before = sim.state_at(sim.start_time - pd.Timedelta(minutes=1))
    assert before["counts"]["cut so far"] == 0
    after = sim.state_at(sim.end_time)
    assert after["counts"]["completed"] == sim.n
    assert after["counts"]["waiting"] + after["counts"]["in lane"] + after["counts"]["staged"] == 0
    assert after["late_summary"]["late LLs so far"] == sim.summary()["late LLs"]


# --------------------------------------------------------------------------
# Expected values quoted in PRD section 8 (v1.1 rules)
# --------------------------------------------------------------------------
def test_prd_default_12_lanes():
    s = run(Params(n_lanes=12)).summary()
    assert s["max LLs in queue"] == 31
    assert s["LLs that waited"] == 108
    assert s["late LLs"] == 7
    assert s["late mean (min)"] == pytest.approx(32, abs=0.5)
    assert s["late longest (min)"] == pytest.approx(115, abs=0.5)
    assert s["late total (min)"] == pytest.approx(225, abs=0.5)
    assert s["peak LLs processing at once"] == 12
    assert list(s["peak staged pallets per zone"].values()) == [48, 48, 48, 48, 48, 38]


@pytest.mark.parametrize(
    "lanes, waited, late, total",
    [(24, 58, 7, 225), (8, 231, 4, 136), (6, 297, 6, 146), (3, 319, 149, 27004)],
)
def test_prd_other_lane_counts(lanes, waited, late, total):
    s = run(Params(n_lanes=lanes)).summary()
    assert s["LLs that waited"] == waited
    assert s["late LLs"] == late
    assert s["late total (min)"] == pytest.approx(total, abs=1)


def test_prd_no_skip_for_arrived_ll_is_later():
    s = run(Params(arrived_skips_zone_check=False)).summary()
    assert s["late total (min)"] > run(Params()).summary()["late total (min)"]
    assert s["LLs that skipped the zone check"] == 0


def test_prd_no_zone_gate_reference():
    s = run(Params(zone_gate=False)).summary()
    assert s["late LLs"] == 1
    assert max(s["peak staged pallets per zone"].values()) > 48
