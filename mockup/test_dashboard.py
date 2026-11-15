"""Tests for the dashboard: view_helpers.py and app.py (run headless with AppTest).

Run from the repository root:
    .venv/Scripts/python.exe -m pytest mockup -v
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import view_helpers as vh  # noqa: E402
from engine import Params, Simulation, load_data  # noqa: E402

APP = str(Path(__file__).resolve().parent / "app.py")


@pytest.fixture(scope="module")
def sim():
    return Simulation(load_data())


def at_time(sim, hour, minute=0):
    return sim.start_time.normalize() + pd.Timedelta(hours=hour, minutes=minute)


# --------------------------------------------------------------- formatting
@pytest.mark.parametrize(
    "minutes, text",
    [(0, "0 min"), (0.4, "0 min"), (45, "45 min"), (59.6, "1 h 00 min"), (65, "1 h 05 min"), (341, "5 h 41 min")],
)
def test_fmt_dur(minutes, text):
    assert vh.fmt_dur(minutes) == text


@pytest.mark.parametrize(
    "used, status", [(0, "ok"), (38, "ok"), (39, "warn"), (47, "warn"), (48, "full"), (50, "full")]
)
def test_zone_status_thresholds(used, status):
    assert vh.zone_status(used, 48, 80) == status


# ----------------------------------------------------------- data shaping
def test_occupancy_series_matches_the_engine_snapshot(sim):
    occ = vh.occupancy_series(sim, step_min=15)
    for t in pd.date_range(sim.start_time, sim.end_time, freq="15min")[::6]:
        zones = sim.state_at(t)["zones"].set_index("Zone")["Used"]
        sample = occ[occ["Time"] == t].set_index("Zone")["Pallets used"]
        for z in sim.zones:
            assert sample[f"Zone {z}"] == zones[z], f"zone {z} at {t}"


def test_occupancy_never_exceeds_capacity(sim):
    assert vh.occupancy_series(sim)["Pallets used"].max() <= sim.params.zone_capacity


@pytest.mark.parametrize("hour", [9, 11, 14, 17])
def test_zone_detail_adds_up_to_the_zone_card(sim, hour):
    clock = at_time(sim, hour)
    zones = sim.state_at(clock)["zones"].set_index("Zone")
    for z in sim.zones:
        detail = vh.zone_detail(sim, z, clock)
        assert detail["Pallets"].sum() == zones.loc[z, "Used"]
        assert (detail["State"] == "Staged").sum() == zones.loc[z, "Staged LLs"]


def test_queue_display_marks_next_late_and_held():
    # With 12 lanes the queue is only held by full zones, so no NEXT row occurs. With 3 lanes
    # lane space runs short, which shows NEXT and LATE rows but no zone ever fills.
    seen = {"next": False, "held": False, "late": False}
    for lanes in (12, 3):
        sim = Simulation(load_data(), Params(n_lanes=lanes))
        for clock in pd.date_range(sim.start_time, sim.end_time, freq="5min"):
            q = sim.state_at(clock)["queue"]
            disp = vh.queue_display(q)
            assert len(disp) == len(q)
            if disp.empty:
                continue
            assert list(disp["#"]) == list(range(1, len(disp) + 1))
            assert disp["Status"].str.startswith("NEXT").sum() <= 1
            seen["next"] |= bool(disp["Status"].str.startswith("NEXT").any())
            seen["held"] |= bool(disp["Status"].str.contains("zone .* full", regex=True).any())
            seen["late"] |= bool(disp["Status"].str.startswith("LATE").any())
    assert all(seen.values()), seen


def test_queue_display_of_an_empty_queue():
    empty = vh.queue_display(pd.DataFrame())
    assert empty.empty and "Status" in empty.columns


def test_event_log_is_newest_first_and_respects_the_clock(sim):
    log = sim.event_log()
    clock = at_time(sim, 12)
    shown = vh.event_log_until(log, sim, clock, n=25)
    assert len(shown) == 25
    times = list(shown["Time"])
    assert times == sorted(times, reverse=True)
    assert pd.Timestamp(f"{clock:%Y-%m-%d} {times[0]}") <= clock


def test_recent_staged_only_includes_already_staged_lls(sim):
    clock = at_time(sim, 10)
    recent = vh.recent_staged(sim, clock, n=8)
    assert len(recent) == 8
    staged_ids = {sim.ll[i] for i in range(sim.n) if sim.finish[i] <= sim.to_secs(clock)}
    assert set(recent["LL"]) <= staged_ids


# ------------------------------------------------------------------ the app
def run_app():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def go_to(at, hour, minute=0):
    at.session_state["clock"] = datetime(2026, 9, 8, hour, minute)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_app_loads_with_two_tabs_and_the_synthetic_note():
    at = run_app()
    assert [t.label for t in at.tabs] == ["Floor view", "Call-out view"]
    assert "Mockup" in at.info[0].value
    assert at.title[0].value.endswith("Staging dashboard preview")


@pytest.mark.parametrize("hour, minute", [(6, 30), (9, 0), (11, 0), (13, 30), (16, 0), (18, 0), (23, 0)])
def test_app_matches_the_engine_at_different_times(sim, hour, minute):
    at = go_to(run_app(), hour, minute)
    state = sim.state_at(datetime(2026, 9, 8, hour, minute))
    assert metric(at, "Cut so far") == str(state["counts"]["cut so far"])
    assert metric(at, "Waiting in queue") == str(state["counts"]["waiting"])
    assert metric(at, "In a lane") == str(state["counts"]["in lane"])
    assert metric(at, "Staged") == str(state["counts"]["staged"])
    assert metric(at, "Completed") == str(state["counts"]["completed"])
    assert metric(at, "LLs in the queue") == str(len(state["queue"]))
    assert metric(at, "Late so far") == str(state["late_summary"]["late LLs so far"])


def test_app_shows_six_zone_cards_and_twelve_lane_cards():
    at = go_to(run_app(), 11, 0)
    html = " ".join(m.value for m in at.markdown)
    assert html.count("<b>Zone ") == 6
    assert html.count("<b>Lane ") == 12


def test_app_shows_a_held_queue_at_midday(sim):
    at = go_to(run_app(), 11, 0)
    state = sim.state_at(datetime(2026, 9, 8, 11, 0))
    held = int(state["queue"]["Reason held"].str.contains("zone").sum())
    assert metric(at, "Held by a full zone") == str(held)


def test_end_of_day_shows_everything_completed_and_an_empty_queue(sim):
    at = run_app()
    at.session_state["clock"] = sim.end_time.to_pydatetime()  # the last time on the slider
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert metric(at, "Completed") == str(sim.n)
    assert metric(at, "LLs in the queue") == "0"
    assert any("queue is empty" in s.value for s in at.success)


def test_play_and_restart_buttons():
    at = run_app()
    play = next(b for b in at.button if "Play" in b.label)
    play.click().run()
    assert at.session_state["playing"] is True
    assert any("Pause" in b.label for b in at.button)
    go_to(at, 12, 0)
    restart = next(b for b in at.button if "Restart" in b.label)
    restart.click().run()
    assert at.session_state["playing"] is False
    assert at.session_state["clock"].hour == 6


def test_changing_a_setting_resimulates_and_resets_the_clock():
    at = go_to(run_app(), 12, 0)
    at.sidebar.slider(key="set_n_lanes").set_value(3).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["clock"].hour == 6
    html = " ".join(m.value for m in at.markdown)
    assert html.count("<b>Lane ") == 3
    go_to(at, 11, 0)
    assert int(metric(at, "LLs in the queue")) > 0


def test_reset_to_defaults_restores_twelve_lanes():
    at = run_app()
    at.sidebar.slider(key="set_n_lanes").set_value(4).run()
    next(b for b in at.sidebar.button if "Reset" in b.label).click().run()
    assert at.session_state["set_n_lanes"] == 12
    assert " ".join(m.value for m in at.markdown).count("<b>Lane ") == 12


def test_playing_advances_the_clock_by_speed_times_tick(sim):
    at = run_app()
    at.session_state["clock"] = datetime(2026, 9, 8, 10, 0)
    at.session_state["speed"] = 20
    at.session_state["playing"] = True
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    # 20 simulated minutes per second x 0.5 s per refresh = 10 minutes.
    assert at.session_state["clock"] == datetime(2026, 9, 8, 10, 10)
    assert at.session_state["playing"] is True


def test_playing_stops_at_the_end_of_the_day(sim):
    at = run_app()
    end = sim.end_time.to_pydatetime()
    at.session_state["clock"] = end.replace(minute=max(end.minute - 1, 0))
    at.session_state["speed"] = 60
    at.session_state["playing"] = True
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["clock"] == end
    assert at.session_state["playing"] is False
    assert any("Play" in b.label for b in at.button)


def test_pressing_play_at_the_end_starts_the_day_again(sim):
    at = run_app()
    at.session_state["clock"] = sim.end_time.to_pydatetime()
    at.run()
    next(b for b in at.button if "Play" in b.label).click().run()
    assert at.session_state["playing"] is True
    # Back at the start, then advanced by one refresh (10 simulated min per second x 0.5 s).
    assert at.session_state["clock"] == sim.start_time.to_pydatetime() + timedelta(minutes=5)
