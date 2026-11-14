# PRD: M4 Dashboard Mockup (Streamlit) with Priority Queue, Lanes and Zone Gating

| | |
|---|---|
| Status | Draft v0.9 (all open questions resolved, simulation engine built and tested) |
| Date | 2026-11-15 |
| Location | `mockup/` (all mockup files live here) |
| Related | `mockup/engine.py`, `mockup/test_engine.py`, `mockup/Decision_Log.md`, `mockup/Data _Prep.ipynb`, `data/Mockup_Data.xlsx`, SDP sections 2.2, 3.1 (requirement 6), 4.4 |

> Every assumption in earlier drafts has been confirmed, and every open question has been answered. The full record is in [Decision_Log.md](Decision_Log.md). Section 8 reports what a trial run of these rules on the real data showed.

## 1. Purpose

This mockup is a **preview of the M4 dashboard**, built in **Streamlit**. It replays one working day so that Ops and Admin can see how the dashboard behaves and judge whether the system will be useful once the full logic is built.

The call-out rule is **deliberately simple**: a priority queue ordered by the gap between cut time and forwarder arrival, feeding 12 processing lanes, and an LL is not sent to a lane while its zone is full. LLs are called out as soon as a lane and zone space allow, with no waiting for the forwarder's arrival. The mockup does **not** use the SDP's weighted scoring model or its CEP, flight and permit factors. Those belong to M3 and come in the full build.

What the preview should help a reviewer answer:
- Is the information on each tab the information Ops would look at?
- Does the zone view make fullness easy to read?
- Do the call-out queue and the lane view show what Ops needs, including which LLs are held back and which are late?
- What is missing?

### Problems the layout speaks to (SDP 2.2)
| SDP problem | What the preview shows |
|---|---|
| P2 Unclear daily workload, volume | LLs cut so far against the day's total |
| P2 Unclear daily workload, floor status | Zone fullness, staged LLs, completed LLs as a count |
| P3 Inaccurate arrival timings | Each LL's forwarder arrival time (known at cut in this mockup), and how many LLs miss it |
| Requirement 6 | One place for staged pallets, outstanding LLs, zone capacity and upcoming call-outs |

## 2. Goals and Non-Goals

### Goals
1. Replay one real operating day (2026-09-08) in compressed time, with LLs appearing in the order Admin actually cut them.
2. Order call-outs with a priority queue ranked by the gap between cut and forwarder arrival, smallest gap first (section 5.3).
3. Simulate 12 processing lanes, each with its own queue (section 5.4), so the time from cut to staging comes out of the simulation and is not scripted.
4. Hold an LL in the priority queue while its zone is full, and let LLs behind it go ahead (section 5.5).
5. Track **late LLs**: how many, and how late each is (section 5.6).
6. **Tab 1 (floor view):** zone utilisation against capacity, staged LLs, LL progress, late LLs, workload and staging time.
7. **Tab 2 (call-out view):** the priority queue in call-out order, the state of each lane, and late LLs.
8. Let a reviewer control the clock and walk through the day.

### Non-Goals
- **No SDP scoring model.** No weights, urgency formula, CEP, UDF11 or UDF12 factors.
- **No cone colours, and no urgent or permit flags.**
- **No visible reordering display.** The queue is shown in order, and nothing animates or logs a change of position.
- **No release window.** Call-out is not delayed until closer to arrival.
- **No 16:00 call-out cut-off.** The simulation runs on its own values and does not enforce, mark or count against the SDP's cut-off.
- No manpower model beyond the lane rule, and no air waybill grouping.
- No forecasting. M1 and M2 are out of scope, and arrival times are simply known.
- No measurement of the SDP Table 6 benefits. The late and staging-time figures are readouts, not targets.
- No live WMS, Master List or dock tracking integration. The data pipeline here is temporary, and a secure pipeline from DSV is still needed.
- No database, authentication or multi-user state.
- No manual call-out or override. The queue order is the call-out order.

## 3. Users

| User | Source | Role in the preview |
|---|---|---|
| Ops Team (planner) | SDP | Primary reviewer of both tabs |
| Admin Team | SDP | Reviews what Ops would see after a cut |
| Staging floor staff | SDP | Reviews Tab 1 against what they check on the floor today |
| FYP team, DSV reviewers | | Run the replay in the Ops review session |

## 4. Data

### 4.1 Source files
| File | Use |
|---|---|
| `data/Test_True.xlsx` | Real operating day, 2026-09-08. 3,248 DNs rolling up to 327 LLs |
| `data/Randomiser_True.xlsx` | Historic handover records, used for the forwarder count (12) and the handover time-of-day distribution |
| `data/Mockup_Data.xlsx` | **Simulation input.** One row per LL, produced by `Data _Prep.ipynb` with seed 42 |

### 4.2 Schema (`Mockup_Data.xlsx`, already built, no new columns needed)
| Column | Source | Meaning in the mockup |
|---|---|---|
| `LL` | Real | Loading list number |
| `Cartons` | Real | Cartons in the LL (1 to 205, median 5, total 5,680) |
| `Added Date` | Real (`Create Date`) | When Admin cut the LL into the WMS. This is the **creation time** |
| `Complete Date` | Real | LL completed in SynQ. **Unused**, kept for reference |
| `Forwarder` | Synthetic | Uniform random from A to L |
| `Zone` | Synthetic | Forwarders pair up: A and B go to zone 1, up to K and L in zone 6. The resulting imbalance between zones is kept |
| `Pallets` | Synthetic | `ceil(Cartons / 50)`, minimum 1 (372 in total) |
| `Handover Time` | Synthetic | Sampled from a normal fitted to historic handovers. If earlier than `Added Date`, set to `Added Date` + 1 hour. **In this mockup it is the forwarder arrival time, and also the time the LL is removed from staging.** It is treated as known the moment the LL is created |

Call-out and staging times are **outputs of the simulation**, not stored columns.

### 4.3 Parameters
All are adjustable from a settings panel.

| Parameter | Default | Meaning |
|---|---|---|
| `n_lanes` | 12 | Number of processing lanes |
| `lane_throughput` | 100 cartons per hour | Processing rate of one lane. Sets processing time |
| `lane_queue_cap` | 100 cartons | The most cartons a lane's queue may hold (SIM-11) |
| `zone_capacity` | 48 pallets | Capacity of each of the six zones, with one location holding one pallet. Confirmed |
| `warn_threshold` | 80% | Zone card turns to warning above this |

### 4.4 Data facts that shape the mockup
- LLs are cut from 06:24 to 17:14, busiest from 09:00 to 12:00 (about 770 cartons cut per hour at the peak).
- Total lane capacity at the defaults is 12 x 100 = 1,200 cartons per hour.
- **Ten LLs have more than 100 cartons** (the largest has 205), so they exceed the lane cap by themselves. See SIM-12.
- Sampled handover times: 72% between 14:00 and 18:59, 4% before 14:00, 24% at or after 19:00.
- Nine LLs have their handover time forced to exactly `Added Date` + 1 hour by the rule in section 4.2, so they share the same smallest gap.

## 5. Simulation Requirements

### 5.1 Clock
- **SIM-1.** A virtual clock runs from the first cut (about 06:24) until the last LL has left staging (about 23:48). Compression is configurable.
- **SIM-2.** Controls: play, pause, restart, speed (for example 1x, 60x, 600x), and jump to a time.
- **SIM-3.** The run is deterministic. The same input and parameters give the same day.

### 5.2 LL lifecycle

| State | Begins when | Where it shows |
|---|---|---|
| **Waiting** | `Added Date` (cut) | In the priority queue |
| **In lane** | Removed from the priority queue and added to a lane | In that lane's queue, either waiting its turn or being processed. This is the "called out" state. Its pallets are reserved in its zone (SIM-16) |
| **Staged** | Its processing in the lane finishes | Counted in its zone. Staging is immediate, with no travel time |
| **Completed** | `Handover Time` is reached | Removed from the zone and added to a completed count |

An LL is also flagged **Late** if it reaches its `Handover Time` before it has been staged (section 5.6).

### 5.3 Priority queue (call-out order)
- **SIM-4.** When an LL is cut, it is inserted into one shared priority queue. The forwarder arrival time (`Handover Time`) is known at that moment.
- **SIM-5.** **Static priority key = `Handover Time` minus `Added Date`** (the gap from cut to arrival). The LL with the **smallest** gap is first. Ties go to the earlier `Added Date`.
- **SIM-6.** The key is fixed when the LL is cut and never changes. An LL with a long gap can be overtaken by later-cut LLs with shorter gaps, and this is accepted.

### 5.4 Lanes
- **SIM-7.** There are `n_lanes` lanes. Each has a **first-in first-out queue** and processes one LL at a time. All lanes work for the whole run.
- **SIM-8. Processing time** of an LL is `Cartons / lane_throughput` hours, with no setup or travel time. At 100 cartons per hour, an LL of 50 cartons takes 30 minutes.
- **SIM-9. Queue size** of a lane is the sum of cartons of every LL in it, including the one being processed.
- **SIM-10.** The queue size of a lane **drops only when an LL finishes processing**, by that LL's whole carton count. It does not fall gradually while the LL is being processed.
- **SIM-11. No overshoot.** An LL fits a lane only if the lane's queue size **plus the LL's cartons is no more than `lane_queue_cap`**. The lane with the smallest queue size is checked (ties go to the lowest lane number). If the LL does not fit it, it fits no lane.
- **SIM-12. Oversize LLs.** An LL with more cartons than `lane_queue_cap` is admitted **only to a lane whose queue is empty**, and holds that lane alone until it finishes.
- **SIM-13.** An LL starts processing when it reaches the front of its lane and finishes `Cartons / lane_throughput` hours later. It is staged at that moment and never held in the lane.

### 5.5 Admission and the zone gate
- **SIM-14. Admission.** Whenever the clock reaches an event (an LL is cut, an LL finishes, or an LL leaves staging), the simulation repeats these steps:
  1. Go down the priority queue in order and find the **first LL that passes the zone gate** (SIM-15). LLs whose zone is full are **skipped** for now, and stay in the queue in their place.
  2. Take the lane with the smallest queue size.
  3. If the LL fits that lane (SIM-11, SIM-12), remove it from the queue, add it to the end of the lane, and reserve its pallets in its zone. Repeat from step 1.
  4. Otherwise stop. **An LL that does not fit a lane blocks the queue by design.** It is not passed over for a smaller one that fits, since only zone-blocked LLs are skipped.
- **SIM-15. Zone gate.** An LL may leave the priority queue only if it **fits** in its zone: **pallets already in the zone plus the LL's pallets is no more than `zone_capacity`**. If not, the LL stays in the queue, and the LLs behind it are sent to lanes in turn until space opens in its zone.
- **SIM-16.** "Pallets already in the zone" counts **staged LLs and LLs still in a lane**, because a called-out LL has reserved its space. This stops a zone overfilling after the LL leaves its lane.
- **SIM-17.** An LL's pallets are removed from its zone at `Handover Time`. A skipped LL is retried whenever that frees space.
- **SIM-18.** Because of SIM-15 and SIM-16, a zone can never go above `zone_capacity`, and no LL is ever held at the end of a lane.
- **SIM-19. Forwarder already arrived.** An LL whose `Handover Time` has passed while it is still in the queue **skips the zone check**. It still needs a lane (SIM-11). It reserves no pallets, since it is handed over the moment it is staged.
- **SIM-20.** Call-outs continue for as long as there are LLs waiting. There is no cut-off time.

### 5.6 Late LLs
- **SIM-21.** An LL is **late** if it is not staged by its `Handover Time` (the forwarder has arrived and the cargo is not ready).
- **SIM-22.** **Lateness** is the time from `Handover Time` until the LL is staged. It is handed over at that moment.
- **SIM-23.** While an LL is late, its running lateness is the clock minus its `Handover Time`. When it is staged, the figure is fixed.
- **SIM-24.** The simulation reports the **number of late LLs** and the lateness of each, with the mean, longest and total.

## 6. Dashboard Requirements (Streamlit)

The SDP specifies two tabs (SDP 4.4). The dashboard is built in **Streamlit**.

### 6.1 Global header
| ID | Requirement | Priority |
|---|---|---|
| DSH-1 | Simulated date and time, with play, pause, speed, restart and jump controls | Must |
| DSH-2 | A visible note that the data is synthetic and the call-out rule is a simple placeholder | Must |
| DSH-3 | Settings panel for the parameters in section 4.3 | Should |

### 6.2 Tab 1: floor view
| ID | Requirement | Priority |
|---|---|---|
| DSH-4 | **Zone utilisation against capacity.** Six zone cards with used and total pallets (for example 31 / 48), a fill bar and a status colour. The bar separates **staged** pallets from pallets **reserved by LLs still in a lane**. A card also shows how many LLs are waiting in the queue for that zone | Must |
| DSH-5 | **LL progress.** Counts of waiting, in lane, staged and completed LLs. Completed LLs are a **count only**, since the SDP says completed LLs cluttering the view is a problem | Must |
| DSH-6 | **Late LLs.** A running count of late LLs, with a panel showing those late now with their running lateness, and totals for the day: number late, mean, longest and total lateness | Must |
| DSH-7 | **Staging time.** The average and longest time the LLs currently in staging have been there, shown overall and per zone | Should |
| DSH-8 | **Workload.** LLs and cartons cut so far against the day's total, standing in for the M2 forecast | Should |
| DSH-9 | Click a zone to list the LLs in it, with forwarder, cartons, pallets, time in staging and handover time | Should |
| DSH-10 | Per-zone occupancy over the day as a line chart | Could |

### 6.3 Tab 2: call-out view
| ID | Requirement | Priority |
|---|---|---|
| DSH-11 | **Priority queue table** in call-out order. Columns: position, LL, forwarder, zone, cartons, pallets, cut time, forwarder arrival, **gap from cut to arrival** (the priority key), time waiting | Must |
| DSH-12 | Each row says whether it is **ready to go** or **held back**, with the reason: "zone N full" or "no lane space". The first ready row is highlighted as **next to be called out** | Must |
| DSH-13 | Rows that are late (forwarder already arrived) are marked and show running lateness | Must |
| DSH-14 | **Lane panel.** One card per lane showing queue size in cartons against the cap, the LL being processed with its time remaining, and the LLs behind it | Must |
| DSH-15 | A summary line: LLs in the queue, LLs held back by a full zone, LLs in lanes, and cartons currently being called out | Should |
| DSH-16 | Time from cut to staging for each recently staged LL | Could |
| DSH-17 | Event log of each cut, call-out, staging and handover with its simulated time (SDP requirement 5) | Could |

Layout: readable on a laptop or a wall display. The visual design follows the reference screenshot of the current dashboard.

## 7. Technical Approach

- **Pipeline:** `mockup/Data _Prep.ipynb` is the only place synthetic columns are generated. It writes `data/Mockup_Data.xlsx`.
- **Simulation engine (built):** `mockup/engine.py`, a plain Python module with no Streamlit dependency. It runs the day as a discrete-event simulation (events are an LL being cut, a forwarder arriving, an LL finishing processing, and a handover) and records every LL's timestamps. `Simulation.state_at(clock)` then returns the queue (with each row's reason held), lane contents, zone occupancy, late LLs and counters for any clock time, ready for the dashboard. `Simulation.summary()` gives the headline figures, `ll_table()` the per-LL results, and `event_log()` the event log (DSH-17).
- **Tests (built):** `mockup/test_engine.py`, written for **pytest**. It holds small scenario tests, the section 10 build checks run on the real day, and checks of the section 8 figures. Run `python mockup/engine.py` for the summary, and `python -m pytest mockup -v` from the repository root for the tests (36 tests, all passing).
- **Precompute, then replay.** Because the run is deterministic, the timeline is computed once per parameter set and cached (for example with `st.cache_data`). The clock only reads from it, which keeps the UI fast and makes pause, jump and restart simple. Changing a parameter recomputes the timeline.
- **Streamlit:** two tabs matching section 6, and a clock that advances on a timer. Streamlit reruns the script on each interaction, so the clock position lives in `st.session_state`. `streamlit` is not yet in `requirements.txt` and must be added.
- **Files:** every new file lives under `mockup/`.

## 8. Review: what a trial run of these rules showed

These figures were produced by `mockup/engine.py` on `Mockup_Data.xlsx`, and the default row is checked by `test_engine.py`. Parameters are at the defaults except where noted. Lateness figures are in minutes. Staging time is the time from staging to handover, for LLs that were not late. The two reference rows use the engine's diagnostic switches (`arrived_skips_zone_check`, `zone_gate`). An earlier throwaway estimate gave slightly higher lateness (total 253 minutes), because it did not wake a waiting LL at the exact moment its forwarder arrived. The engine does.

| Setup | Max LLs in queue | LLs that waited | Mean cut to staging | Late LLs | Lateness: mean / longest / total | Mean staging time | Staged pallets, peak per zone (1 to 6) |
|---|---|---|---|---|---|---|---|
| **12 lanes (spec)** | **30** | **60** | 30 min | **9** | **27 / 115 / 242** | 341 min | 48, 48, 48, 48, 48, 38 |
| 12 lanes, no skip for arrived LLs | 32 | 60 | 31 min | 9 | 49 / 168 / 437 | 341 min | 48, 48, 48, 48, 48, 38 |
| 6 lanes | 51 | 132 | 56 min | 9 | 32 / 115 / 285 | 314 min | 48, 46, 46, 48, 48, 36 |
| 24 lanes | 30 | 58 | 29 min | 9 | 27 / 115 / 242 | 342 min | 48, 48, 48, 48, 48, 38 |
| 12 lanes, no zone gate (reference) | 1 | 2 | 12 min | 1 | 55 / 55 / 55 | 350 min | 50, 48, 55, 50, 76, 38 |

All 327 LLs are staged and handed over in every run.

### Findings
1. **The zone gate at the queue works, and lanes never stall.** 58 different LLs were held back by a full zone at some point, up to 30 at once, and the LLs behind them kept flowing to lanes. 60 of the 327 waited in the queue, for 19 minutes on average and 373 minutes at most. Zones stay at or below 48.
2. **Nine LLs are late (2.8%).** Mean lateness is 27 minutes, the median is about 6, and the longest is 115 minutes (a 192-carton LL for zone 5). Total lateness is 242 minutes. All nine are in zones 5 (seven LLs) and 3 (two LLs), the zones that stay full. Three of the nine have more than 100 cartons.
3. **The count of late LLs is the same, 9, with 6, 12 or 24 lanes.** Zone space, not lane capacity, drives lateness. More lanes only shorten the time spent in the queue.
4. **Skipping the zone check for arrived LLs cuts total lateness from 437 to 242 minutes (45%)** and the worst case from 168 to 115 minutes. It does not change how many LLs are late. Six LLs used the skip in the default run.
5. **LLs spend a long time in staging, and the gate barely changes it.** For LLs that were not late, the mean time in staging is 341 minutes (5.7 hours), the 95th percentile is 676 minutes, and the longest is 940 minutes. With no zone gate it is 350 minutes. Total pallet-hours in staging fall only 6% (2,036 against 2,158). This follows from the decision to call out as soon as space allows. The staging time readout (DSH-7) lets reviewers see this cost directly.
6. **The priority queue has no effect on staging time.** Ordering by smallest gap decides who goes first, but every LL is sent out as soon as it can be.

## 9. Decisions

All assumptions from earlier drafts are confirmed, and all open questions are answered. The full record, with the reasoning, is in [Decision_Log.md](Decision_Log.md). There are no open questions.

| # | Decision |
|---|---|
| D1 | Priority key is the smallest gap first (`Handover Time` minus `Added Date`) |
| D2 | Call-out does not wait for the forwarder's arrival. The current call-out rule is kept |
| D3 | LLs in a lane count towards zone fullness |
| D4 | The zone check is "fits", so a zone can never exceed capacity |
| D5 | An LL that does not fit a lane blocks the queue |
| D6 | Zone capacity is 48 pallets, and one location holds one pallet |
| D7 | The zone imbalance from random forwarder assignment is kept |
| D8 | The 16:00 call-out cut-off from the SDP is ignored, and the simulation uses its own values |

## 10. Success Criteria

### Usefulness (the point of the mockup)
In an Ops review session, a reviewer should be able to say, after watching one day:
1. Whether Tab 1 shows what they would otherwise check on the floor.
2. Whether they can see which LLs are held back, why, and which are late.
3. Whether the Tab 2 queue and lane view show what they need to decide a call-out, and what is missing.
4. Whether seeing lanes fill and clear helps them judge how many LLs can be called out at once.

Feedback is captured as notes. No numeric target is set.

### Build checks
- Replaying the day twice gives identical output.
- No LL is called out before it is cut, or staged before its processing finishes.
- Processing time equals `Cartons / lane_throughput` for every LL (an LL of 50 cartons takes 30 minutes at the defaults).
- A lane's queue size drops only when an LL finishes, and never goes below zero.
- A lane's queue size never exceeds `lane_queue_cap`, except when it holds a single oversize LL on its own.
- A zone's pallets (staged plus reserved) never exceed `zone_capacity`.
- An LL leaves the priority queue only if its zone has room, or its forwarder has already arrived.
- Among the LLs that pass the zone gate, LLs leave the priority queue strictly in key order.
- If the first LL that passes the zone gate does not fit a lane, no later LL leaves the queue until it does.
- The late count equals the number of LLs staged after their `Handover Time`, and each LL's lateness equals the difference.
- At every point in time, waiting, in-lane, staged and completed LLs add up to the LLs cut so far.

## 11. Milestones

SDP Table 14 puts "finalise M3 outputs and decision variables with Ops, finish mock-up" in November 2026.

| Step | Deliverable | Depends on |
|---|---|---|
| 1 | Decisions recorded (done, see `Decision_Log.md`) | |
| 2 | Simulation engine with the priority queue, lanes, zone gate and lateness tracking, and tests for the section 10 build checks (**done**, `engine.py` and `test_engine.py`) | Step 1 |
| 3 | Confirm the section 8 results from the engine (**done**, table refreshed) | Step 2 |
| 4 | Streamlit dashboard v1: header, Tab 1 zone cards, counters and late panel, Tab 2 queue and lane panel (DSH-1, 2, 4 to 6, 11 to 14) | Step 3 |
| 5 | Should items: settings panel, staging time, workload, zone detail | Step 4 |
| 6 | Ops review session, with feedback captured for the December edits | Step 5 |
