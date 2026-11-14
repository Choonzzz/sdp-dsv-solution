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


def test_no_overshoot_waits_for_lane():
    # 60 + 50 > 100, so LL 2 waits for LL 1 to finish (36 minutes after it started).
    sim = Simulation(make([(1, 60, 0, 900, 1, 1), (2, 50, 1, 900, 1, 1)]), Params(n_lanes=1))
    assert sim.call[idx(sim, 2)] == sim.finish[idx(sim, 1)]
    assert (sim.call[idx(sim, 2)] - sim.cut[idx(sim, 2)]) / 60 == pytest.approx(35.0)


def test_second_lane_takes_the_overflow():
    sim = Simulation(make([(1, 60, 0, 900, 1, 1), (2, 50, 1, 900, 1, 1)]), Params(n_lanes=2))
    assert sim.call[idx(sim, 2)] == sim.cut[idx(sim, 2)]
    assert sim.lane[idx(sim, 1)] == 0
    assert sim.lane[idx(sim, 2)] == 1


def test_shortest_lane_and_tie_to_lowest_number():
    rows = [(1, 60, 0, 900, 1, 1), (2, 30, 1, 900, 1, 1), (3, 20, 2, 900, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=2))
    assert [sim.lane[idx(sim, k)] for k in (1, 2, 3)] == [0, 1, 1]


def test_oversize_ll_waits_for_an_empty_lane():
    # 150 cartons exceeds the cap of 100, so it needs an empty lane.
    sim = Simulation(make([(1, 60, 0, 900, 1, 1), (2, 150, 1, 900, 1, 3)]), Params(n_lanes=1))
    assert sim.call[idx(sim, 2)] == sim.finish[idx(sim, 1)]


def test_nothing_joins_a_lane_held_by_an_oversize_ll():
    rows = [(1, 150, 0, 900, 1, 3), (2, 10, 1, 900, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=1))
    assert sim.call[idx(sim, 2)] == sim.finish[idx(sim, 1)]


def test_priority_is_smallest_gap_first():
    rows = [
        (1, 100, 0, 900, 1, 2),  # fills the only lane
        (2, 10, 5, 1000, 1, 1),  # gap 995 min
        (3, 10, 6, 100, 1, 1),  # gap 94 min, cut later, higher priority
    ]
    sim = Simulation(make(rows), Params(n_lanes=1))
    # Both small LLs are called the moment the lane frees, so compare call order.
    assert sim.call_seq[idx(sim, 3)] < sim.call_seq[idx(sim, 2)]
    assert sim.call[idx(sim, 3)] == sim.finish[idx(sim, 1)]


@pytest.mark.parametrize(
    "rows",
    [
        # Equal gaps (195 and 195): the earlier cut goes first.
        [(1, 100, 0, 900, 1, 2), (2, 10, 5, 200, 1, 1), (3, 10, 6, 201, 1, 1)],
        # Equal gaps (200 and 200).
        [(1, 100, 0, 900, 1, 2), (2, 10, 5, 205, 1, 1), (3, 10, 6, 206, 1, 1)],
    ],
)
def test_ties_go_to_the_earlier_cut(rows):
    sim = Simulation(make(rows), Params(n_lanes=1))
    assert sim.call_seq[idx(sim, 2)] < sim.call_seq[idx(sim, 3)]


def test_zone_gate_skips_a_full_zone():
    # Zone 1 holds 2 pallets. LL 1 fills it. LL 2 (zone 1) is skipped, LL 3 (zone 2) goes ahead.
    rows = [
        (1, 10, 0, 120, 1, 2),
        (2, 10, 1, 130, 1, 1),  # smaller gap than LL 3, but its zone is full
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
        (3, 10, 2, 500, 1, 1),  # fits: goes ahead although it has the larger gap
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


def test_lane_blocks_the_queue_by_design():
    # LL 2 (90 cartons) fits nowhere while the lane is busy. LL 3 (small) must not overtake it.
    rows = [(1, 50, 0, 900, 1, 1), (2, 90, 1, 800, 1, 2), (3, 10, 2, 850, 1, 1)]
    sim = Simulation(make(rows), Params(n_lanes=1))
    assert sim.call_seq[idx(sim, 2)] < sim.call_seq[idx(sim, 3)]
    assert sim.call[idx(sim, 2)] <= sim.call[idx(sim, 3)]


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
        assert sim.start[i] >= sim.call[i]
        assert sim.finish[i] > sim.start[i]
        assert sim.left[i] >= sim.finish[i]


def test_real_processing_time_is_cartons_over_throughput(sim):
    for i in range(sim.n):
        expected = sim.cartons[i] / sim.params.lane_throughput * 3600
        assert sim.finish[i] - sim.start[i] == pytest.approx(expected)


def test_lane_queue_never_negative_and_never_over_cap_unless_alone(sim, event_times):
    cap = sim.params.lane_queue_cap
    for t in event_times:
        for lane in range(sim.params.n_lanes):
            members = [
                i for i in range(sim.n) if sim.lane[i] == lane and sim.call[i] <= t < sim.finish[i]
            ]
            q = sum(sim.cartons[i] for i in members)
            assert q >= 0
            if q > cap:
                assert len(members) == 1, f"lane {lane} at {t}"
                assert sim.cartons[members[0]] > cap


def test_lanes_process_one_ll_at_a_time(sim):
    for lane in range(sim.params.n_lanes):
        ids = sorted((i for i in range(sim.n) if sim.lane[i] == lane), key=lambda k: sim.call_seq[k])
        for a, b in zip(ids, ids[1:]):
            assert sim.start[b] >= sim.finish[a]


def test_zone_never_exceeds_capacity(sim, event_times):
    cap = sim.params.zone_capacity
    for t in event_times:
        for z, used in zone_used_at(sim, t).items():
            assert used <= cap, f"zone {z} at {t}"
    assert max(sim.peak_used.values()) <= cap


def test_call_out_respects_zone_gate_and_key_order(sim):
    """At every call-out the LL chosen is the first in key order that passes the zone gate,
    so every waiting LL ahead of it was held by a full zone. This also proves that an LL
    that fits no lane blocks the queue, since nobody ahead of the caller could have gone."""
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


def test_zone_pallets_equal_sum_of_staged_and_reserved(sim, event_times):
    for t in event_times[::11]:
        zones = sim.state_at(t)["zones"]
        tt = sim.to_secs(t)
        for _, row in zones.iterrows():
            z = int(row["Zone"])
            staged = sum(
                sim.pallets[i] for i in range(sim.n)
                if sim.zone[i] == z and sim.finish[i] <= tt < sim.left[i]
            )
            reserved = sum(
                sim.pallets[i] for i in range(sim.n)
                if sim.zone[i] == z and sim.reserved[i] and sim.call[i] <= tt < sim.finish[i]
            )
            assert row["Staged pallets"] == staged
            assert row["Reserved pallets"] == reserved
            assert row["Used"] == staged + reserved


def test_snapshot_queue_is_in_key_order_with_one_next(sim, event_times):
    found_held = False
    for t in event_times[::5]:
        q = sim.state_at(t)["queue"]
        if q.empty:
            continue
        assert list(q["Position"]) == list(range(1, len(q) + 1))
        keys = list(zip(q["Gap (min)"], q["Cut"], q["LL"]))
        assert keys == sorted(keys)
        assert int(q["Next"].sum()) <= 1
        if q["Reason held"].str.contains("zone").any():
            found_held = True
    assert found_held, "expected some LLs held back by a full zone"


def test_snapshot_lane_cards_are_never_negative(sim, event_times):
    for t in event_times[::13]:
        for lane in sim.state_at(t)["lanes"]:
            assert lane["Queue (cartons)"] >= 0


def test_snapshot_before_start_and_after_end(sim):
    before = sim.state_at(sim.start_time - pd.Timedelta(minutes=1))
    assert before["counts"]["cut so far"] == 0
    after = sim.state_at(sim.end_time)
    assert after["counts"]["completed"] == sim.n
    assert after["counts"]["waiting"] + after["counts"]["in lane"] + after["counts"]["staged"] == 0
    assert after["late_summary"]["late LLs so far"] == sim.summary()["late LLs"]


# --------------------------------------------------------------------------
# Expected values quoted in PRD section 8
# --------------------------------------------------------------------------
def test_prd_default_12_lanes():
    s = run(Params()).summary()
    assert s["max LLs in queue"] == 30
    assert s["LLs that waited"] == 60
    assert s["late LLs"] == 9
    assert s["late mean (min)"] == pytest.approx(27, abs=0.5)
    assert s["late longest (min)"] == pytest.approx(115, abs=0.5)
    assert s["late total (min)"] == pytest.approx(242, abs=0.5)
    assert list(s["peak staged pallets per zone"].values()) == [48, 48, 48, 48, 48, 38]


@pytest.mark.parametrize("lanes", [6, 24])
def test_prd_late_count_is_the_same_for_other_lane_counts(lanes):
    assert run(Params(n_lanes=lanes)).summary()["late LLs"] == 9


def test_prd_no_skip_for_arrived_ll_is_later():
    s = run(Params(arrived_skips_zone_check=False)).summary()
    assert s["late total (min)"] == pytest.approx(437, abs=0.5)
    assert s["LLs that skipped the zone check"] == 0


def test_prd_no_zone_gate_reference():
    s = run(Params(zone_gate=False)).summary()
    assert s["max LLs in queue"] <= 2
    assert max(s["peak staged pallets per zone"].values()) > 48
