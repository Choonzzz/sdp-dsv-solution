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
    "minutes, text",
    [(45, "45 min"), (0, "0 min"), (-0.2, "0 min"), (-12, "-12 min"), (-75, "-1 h 15 min")],
)
def test_fmt_signed_dur_goes_negative_after_arrival(minutes, text):
    assert vh.fmt_signed_dur(minutes) == text


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
        assert len(detail) == zones.loc[z, "LLs in zone"]
        assert (detail["State"] == "Staged").sum() == zones.loc[z, "Staged LLs"]


def test_zone_detail_keeps_the_time_in_staging_column(sim):
    assert "Time in staging" in vh.zone_detail(sim, 1, at_time(sim, 12)).columns


def busy_moments(sim, step="10min"):
    return pd.date_range(sim.start_time, sim.end_time, freq=step)


def test_table_has_no_cut_time_or_gap_column(sim):
    clock = at_time(sim, 11)
    state = sim.state_at(clock)
    table = vh.call_out_table(state["queue"], state["in_lanes"], include_in_lanes=True)
    assert list(table.columns) == vh.TABLE_COLUMNS
    assert "Cut" not in table.columns and "Gap" not in table.columns
    assert "Time to arrival" in table.columns


def test_upcoming_only_shows_exactly_the_queue(sim):
    for clock in busy_moments(sim):
        state = sim.state_at(clock)
        table = vh.call_out_table(state["queue"], state["in_lanes"], include_in_lanes=False)
        assert len(table) == len(state["queue"])
        assert not table["Status"].str.startswith("Processing").any()
        if len(table):
            assert list(table["#"]) == [str(k) for k in range(1, len(table) + 1)]


def test_with_in_lanes_the_processing_rows_are_grouped_at_the_top(sim):
    saw_both = False
    for clock in busy_moments(sim, "5min"):
        state = sim.state_at(clock)
        table = vh.call_out_table(state["queue"], state["in_lanes"], include_in_lanes=True)
        n_lane = len(state["in_lanes"])
        assert len(table) == n_lane + len(state["queue"])
        assert n_lane == state["counts"]["in lane"] <= sim.params.n_lanes
        top = table.head(n_lane)
        assert top["Status"].str.contains("rocessing").all()
        assert (top["#"] == "").all()
        assert not table.iloc[n_lane:]["Status"].str.contains("rocessing").any()
        saw_both |= bool(n_lane and len(state["queue"]))
        # Soonest arrival first inside the in-lane group.
        if n_lane > 1:
            assert state["in_lanes"]["Time to arrival (min)"].is_monotonic_increasing
    assert saw_both, "expected moments with both in-lane and upcoming rows"


def test_table_marks_next_late_held_and_processing():
    # With 12 lanes the queue is only held by full zones. With 3 lanes lanes run short too, which
    # shows NEXT and LATE rows, and no zone ever fills.
    seen = {"next": False, "held": False, "late": False, "processing": False}
    for lanes in (12, 3):
        s = Simulation(load_data(), Params(n_lanes=lanes))
        for clock in pd.date_range(s.start_time, s.end_time, freq="5min"):
            state = s.state_at(clock)
            table = vh.call_out_table(state["queue"], state["in_lanes"], include_in_lanes=True)
            if table.empty:
                continue
            assert table["Status"].str.startswith("NEXT").sum() <= 1
            seen["next"] |= bool(table["Status"].str.startswith("NEXT").any())
            seen["held"] |= bool(table["Status"].str.contains("Held: zone .* full", regex=True).any())
            seen["late"] |= bool(table["Status"].str.startswith("LATE").any())
            seen["processing"] |= bool(table["Status"].str.contains("rocessing, lane").any())
    assert all(seen.values()), seen


def test_time_to_arrival_is_negative_for_late_rows():
    s = Simulation(load_data(), Params(n_lanes=3))
    for clock in pd.date_range(s.start_time, s.end_time, freq="10min"):
        state = s.state_at(clock)
        table = vh.call_out_table(state["queue"], state["in_lanes"], include_in_lanes=True)
        late = table[table["Status"].str.startswith("LATE")]
        if len(late):
            assert late["Time to arrival"].str.startswith("-").all()
            return
    pytest.fail("no late row found")


def test_call_out_table_of_nothing():
    empty = vh.call_out_table(pd.DataFrame(), pd.DataFrame(), include_in_lanes=True)
    assert empty.empty and list(empty.columns) == vh.TABLE_COLUMNS


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


def all_html(at):
    return " ".join(m.value for m in at.markdown)


def queue_table(at):
    """The call-out queue table on the page (found by its columns)."""
    tables = [df.value for df in at.dataframe if "Time to arrival" in df.value.columns]
    assert tables, "queue table not found"
    return tables[0]


def test_app_loads_with_the_call_out_view_first():
    at = run_app()
    assert [t.label for t in at.tabs] == ["Call-out view", "Floor view"]
    assert "Mockup" in at.info[0].value
    assert at.title[0].value.endswith("Staging dashboard preview")


def test_call_out_view_has_its_segments_in_order():
    at = run_app()
    assert [e.label for e in at.expander][:3] == ["LL progress", "Late LLs", "Queue breakdown"]
    assert all(e.proto.expanded for e in at.expander[:3])
    headers = [h.value for h in at.subheader]
    call_out = headers[: headers.index("Zones")]
    assert call_out == ["Call-out queue", "Lanes"]
    assert headers[headers.index("Zones"):] == ["Zones", "Zone detail"]


def test_ll_progress_and_late_lls_are_no_longer_on_the_floor_view():
    at = run_app()
    floor_headers = [h.value for h in at.subheader][2:]
    assert "LL progress" not in floor_headers and "Late LLs" not in floor_headers


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
    assert metric(at, "LLs in lanes") == str(state["counts"]["in lane"])
    assert metric(at, "Late so far") == str(state["late_summary"]["late LLs so far"])


def test_zone_cards_show_pallets_and_no_staging_time_or_queued_count():
    at = go_to(run_app(), 11, 0)
    cards = [m.value for m in at.markdown if "<b>Zone " in m.value]
    assert len(cards) == 6
    for card in cards:
        assert "pallets (" in card  # the headline is in pallets
        assert "Pallets staged:" in card
        assert "Pallets reserved:" in card
        assert "LLs in the zone:" in card
        for gone in ("average", "longest", "staging time", "Queued", "waiting for this zone"):
            assert gone.lower() not in card.lower(), gone


def test_lane_cards_show_one_ll_and_no_behind_line(sim):
    at = go_to(run_app(), 11, 0)
    html = all_html(at)
    assert html.count("<b>Lane ") == 12
    assert "Nothing behind" not in html and "Behind:" not in html
    state = sim.state_at(datetime(2026, 9, 8, 11, 0))
    assert html.count("Processing LL") == state["counts"]["in lane"]
    assert html.count(">Idle<") == 12 - state["counts"]["in lane"]


def test_the_filter_defaults_to_upcoming_only_and_can_add_lanes(sim):
    at = go_to(run_app(), 11, 0)
    state = sim.state_at(datetime(2026, 9, 8, 11, 0))
    assert at.radio(key="queue_filter").value == "Upcoming LLs only"
    assert len(queue_table(at)) == len(state["queue"])
    at.radio(key="queue_filter").set_value("Upcoming and in lanes").run()
    assert not at.exception, [e.value for e in at.exception]
    table = queue_table(at)
    assert len(table) == len(state["queue"]) + state["counts"]["in lane"]
    # The rows being processed come first.
    assert table.head(state["counts"]["in lane"])["Status"].str.contains("rocessing").all()


def test_queue_table_columns_have_no_cut_time():
    at = go_to(run_app(), 11, 0)
    at.radio(key="queue_filter").set_value("Upcoming and in lanes").run()
    assert list(queue_table(at).columns) == vh.TABLE_COLUMNS


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


def test_changing_the_lane_count_resimulates_and_resets_the_clock():
    at = go_to(run_app(), 12, 0)
    at.sidebar.slider(key="set_n_lanes").set_value(3).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["clock"].hour == 6
    assert all_html(at).count("<b>Lane ") == 3
    go_to(at, 11, 0)
    assert int(metric(at, "LLs in the queue")) > 0


def test_there_is_no_lane_queue_cap_setting():
    at = run_app()
    labels = [s.label for s in at.sidebar.slider]
    assert not any("cap" in label.lower() and "lane" in label.lower() for label in labels)
    assert labels == ["Lanes", "Lane throughput (cartons per hour)", "Zone capacity (pallets)",
                      "Zone warning threshold (%)"]


def test_reset_to_defaults_restores_twelve_lanes():
    at = run_app()
    at.sidebar.slider(key="set_n_lanes").set_value(4).run()
    next(b for b in at.sidebar.button if "Reset" in b.label).click().run()
    assert at.session_state["set_n_lanes"] == 12
    assert all_html(at).count("<b>Lane ") == 12


def test_playing_advances_the_clock_by_speed_times_tick():
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
