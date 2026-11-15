# PRD: M4 Dashboard Mockup (Streamlit) with Priority Queue, Lanes and Zone Gating

| | |
|---|---|
| Status | **v1.1: built.** The engine and dashboard implement this document, and all 96 tests pass. Nothing is open |
| Date | 2026-11-15 |
| Location | `mockup/` (all mockup files live here) |
| Related | `mockup/engine.py`, `mockup/test_engine.py`, `mockup/Decision_Log.md`, `mockup/Data _Prep.ipynb`, `data/Mockup_Data.xlsx`, SDP sections 2.2, 3.1 (requirement 6), 4.4 |

> Every assumption in drafts up to v1.0 has been confirmed, and every open question from them has been answered. The full record is in [Decision_Log.md](Decision_Log.md). Section 8 reports what a trial run of these rules on the real data showed.
>
> **v1.1 rearranges the dashboard and changes how the call-out queue is ordered.** All its questions were answered on 2026-11-15, and the answer to the last one (Q4) also changes how lanes work (section 5.4). Text marked **(v1.1)** or **(v1.1, approved)** was new in v1.1. All of it is now built and tested. The results in section 8 for the v1.0 rules are kept for comparison, and are labelled as such.

## 1. Purpose

This mockup is a **preview of the M4 dashboard**, built in **Streamlit**. It replays one working day so that Ops and Admin can see how the dashboard behaves and judge whether the system will be useful once the full logic is built.

The call-out rule is **deliberately simple**: a priority queue ordered by time to forwarder arrival, soonest first **(v1.1; v1.0 ordered by the gap between cut and arrival)**, feeding 12 processing lanes that each process one LL at a time, and an LL is not sent to a lane while its zone is full. LLs are called out as soon as a lane is free and its zone has space, with no waiting for the forwarder's arrival. The mockup does **not** use the SDP's weighted scoring model or its CEP, flight and permit factors. Those belong to M3 and come in the full build.

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
| P3 Inaccurate arrival timings | Each LL's forwarder arrival time (known at cut in this mockup) with a live countdown to it, and how many LLs miss it |
| Requirement 6 | One place for staged pallets, outstanding LLs, zone capacity and upcoming call-outs |

## 2. Goals and Non-Goals

### Goals
1. Replay one real operating day (2026-09-08) in compressed time, with LLs appearing in the order Admin actually cut them.
2. Order call-outs with a priority queue ranked by time to forwarder arrival, soonest first (section 5.3) **(v1.1; v1.0 ranked by the gap between cut and arrival)**.
3. Simulate 12 processing lanes, each processing one LL at a time (section 5.4, v1.1), so the time from cut to staging comes out of the simulation and is not scripted.
4. Hold an LL in the priority queue while its zone is full, and let LLs behind it go ahead (section 5.5).
5. Track **late LLs**: how many, and how late each is (section 5.6).
6. **Tab 1 (call-out view), the first tab (v1.1):** LL progress and workload, late LLs, the queue breakdown cards, the call-out queue (optionally with the LLs being processed in lanes), and the lane cards.
7. **Tab 2 (floor view) (v1.1):** zone utilisation against capacity with the staged and reserved breakdown, zone detail, and occupancy over the day.
8. Let a reviewer control the clock and walk through the day.

### Non-Goals
- **No SDP scoring model.** No weights, urgency formula, CEP, UDF11 or UDF12 factors.
- **No cone colours, and no urgent or permit flags.**
- **No visible reordering display.** The queue is shown in order, and nothing animates or logs a change of position.
- **No release window.** Call-out is not delayed until closer to arrival.
- **No 16:00 call-out cut-off.** The simulation runs on its own values and does not enforce, mark or count against the SDP's cut-off.
- No manpower model beyond the lane rule, and no air waybill grouping.
- No forecasting. M1 and M2 are out of scope, and arrival times are simply known.
- No measurement of the SDP Table 6 benefits. The late figures are readouts, not targets.
- **No staging-time readout on the dashboard (v1.1).** The engine still calculates time in staging, but the dashboard no longer shows it.
- No live WMS, Master List or dock tracking integration. The data pipeline here is temporary, and a secure pipeline from DSV is still needed.
- No database, authentication or multi-user state.
- No manual call-out or override. The queue order is the call-out order.

## 3. Users

| User | Source | Role in the preview |
|---|---|---|
| Ops Team (planner) | SDP | Primary reviewer of both tabs |
| Admin Team | SDP | Reviews what Ops would see after a cut |
| Staging floor staff | SDP | Reviews the floor view against what they check on the floor today |
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
All are adjustable from a settings panel. **(v1.1, approved) The `lane_queue_cap` parameter (100 cartons) is removed**, because lanes no longer hold a queue (section 5.4).

| Parameter | Default | Meaning |
|---|---|---|
| `n_lanes` | 12 | Number of processing lanes |
| `lane_throughput` | 100 cartons per hour | Processing rate of one lane. Sets processing time |
| `zone_capacity` | 48 pallets | Capacity of each of the six zones, with one location holding one pallet. Confirmed |
| `warn_threshold` | 80% | Zone card turns to warning above this |

### 4.4 Data facts that shape the mockup
- LLs are cut from 06:24 to 17:14, busiest from 09:00 to 12:00. **The peak hour (10:00 to 10:59) cuts 1,113 cartons.** An earlier draft said about 770, which was wrong.
- Total lane capacity at the defaults is 12 x 100 = 1,200 cartons per hour. **The peak hour therefore uses about 93% of it**, so lanes are close to saturated at the busiest time and have spare capacity for the rest of the day.
- The largest LL (205 cartons) takes about 2 hours 3 minutes on one lane. With one LL per lane (SIM-9), size is no longer a problem for lane admission.
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
| **In lane** | Removed from the priority queue and sent to a free lane **(v1.1, approved)** | Being processed in that lane, one LL per lane. This is the "called out" state. Its pallets are reserved in its zone (SIM-16) |
| **Staged** | Its processing in the lane finishes | Counted in its zone. Staging is immediate, with no travel time |
| **Completed** | `Handover Time` is reached | Removed from the zone and added to a completed count |

An LL is also flagged **Late** if it reaches its `Handover Time` before it has been staged (section 5.6).

### 5.3 Priority queue (call-out order)
- **SIM-4.** When an LL is cut, it is inserted into one shared priority queue. The forwarder arrival time (`Handover Time`) is known at that moment.
- **SIM-5 (v1.1, approved).** **Priority key = time to arrival = `Handover Time` minus the current time.** The LL with the **smallest** value is first. An LL whose forwarder has already arrived has a negative value and goes ahead of every other LL. Ties go to the earlier `Added Date`, then the lower LL number.
- **SIM-6 (v1.1, approved).** Because the current time is the same for every LL, ranking by time to arrival gives **exactly the same order as ranking by arrival time, soonest first**. The order of LLs already waiting therefore never changes. Only the countdown shown for each LL changes as the clock moves. An LL can still be overtaken by a later-cut LL whose forwarder arrives sooner, and this is accepted.
- *v1.0 wording, replaced if v1.1 is approved:* SIM-5 used the static key `Handover Time` minus `Added Date` (the gap from cut to arrival), smallest gap first. SIM-6 said the key is fixed at cut time. See Q1 in section 12.2.

### 5.4 Lanes
**(v1.1, approved, Q4.)** Lanes no longer hold a queue of LLs. An LL waits in the priority queue until a lane is free, and a lane processes exactly one LL at a time. The 100-carton limit is removed. The v1.0 rules for a lane queue, no overshoot and oversize LLs (old SIM-9 to SIM-12) are replaced, and the numbers SIM-11 and SIM-12 are no longer used.

- **SIM-7.** There are `n_lanes` lanes. Each processes **one LL at a time**, and has no queue behind it. All lanes work for the whole run.
- **SIM-8. Processing time** of an LL is `Cartons / lane_throughput` hours, with no setup or travel time. At 100 cartons per hour, an LL of 50 cartons takes 30 minutes, and an LL of 205 cartons takes 2 hours 3 minutes.
- **SIM-9. Lane gate.** An LL can enter a lane **only if that lane is free**, meaning it is not processing another LL. If every lane is busy, the LL stays in the priority queue. There is **no limit on the cartons** of an LL, so an LL of any size can use a free lane.
- **SIM-10. Which lane.** If several lanes are free, the lowest-numbered free lane is used **[Assumption]**.
- **SIM-13.** The lane is busy from the moment the LL enters it until `Cartons / lane_throughput` hours later. The LL is then staged at once, and the lane is free again.

### 5.5 Admission and the zone gate
- **SIM-14. Admission.** Whenever the clock reaches an event (an LL is cut, an LL finishes, or an LL leaves staging), the simulation repeats these steps:
  1. Go down the priority queue in order and find the **first LL that passes the zone gate** (SIM-15). LLs whose zone is full are **skipped** for now, and stay in the queue in their place.
  2. Look for a **free lane** (SIM-9). If every lane is busy, stop. The LLs stay in the queue, and nothing is skipped because of lane availability.
  3. Otherwise remove the LL from the queue, send it to the lowest-numbered free lane (SIM-10), start processing, and reserve its pallets in its zone. Repeat from step 1.
- **SIM-15. Zone gate.** An LL may leave the priority queue only if it **fits** in its zone: **pallets already in the zone plus the LL's pallets is no more than `zone_capacity`**. If not, the LL stays in the queue, and the LLs behind it are sent to lanes in turn until space opens in its zone.
- **SIM-16.** "Pallets already in the zone" counts **staged LLs and LLs still in a lane**, because a called-out LL has reserved its space. This stops a zone overfilling after the LL leaves its lane. "In a lane" now means being processed, so at most `n_lanes` LLs can have pallets reserved this way.
- **SIM-17.** An LL's pallets are removed from its zone at `Handover Time`. A skipped LL is retried whenever that frees space.
- **SIM-18.** Because of SIM-15 and SIM-16, a zone can never go above `zone_capacity`, and no LL is ever held at the end of a lane.
- **SIM-19. Forwarder already arrived.** An LL whose `Handover Time` has passed while it is still in the queue **skips the zone check**. It still needs a free lane (SIM-9). It reserves no pallets, since it is handed over the moment it is staged.
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

**(v1.1.)** The tabs are reordered and their contents redistributed. The **call-out view is now the first tab**, and the floor view is the second. Requirement numbers below are new in v1.1, and follow the top-to-bottom order on screen.

### 6.2 Tab 1: call-out view (first tab)
From top to bottom. Each segment has its own header: **LL progress, Late LLs, Queue breakdown, Call-out queue, Lanes**.

| ID | Requirement | Priority |
|---|---|---|
| DSH-4 | **LL progress** (moved from the floor view). Counts of cut so far, waiting in the queue, in a lane, staged and completed LLs. Completed LLs are a **count only**, since the SDP says completed LLs cluttering the view is a problem. The workload bars (LLs and cartons cut so far against the day's total, standing in for the M2 forecast) sit with it | Must |
| DSH-5 | **Late LLs** (moved from the floor view). Late so far, late right now, average, longest and total lateness, with a table of the LLs that are late right now and their running lateness | Must |
| DSH-6 | **Queue breakdown cards.** Four cards: LLs in the queue, LLs held by a full zone, LLs in lanes (being processed, never more than the number of lanes), and cartons being processed. The segment has a header, "Queue breakdown" (approved, Q3) | Must |
| DSH-7 | **Call-out queue table**, ordered by **time to arrival**, soonest first (SIM-5). Columns: position, LL, forwarder, zone, cartons, pallets, forwarder arrival (clock time), **time to arrival** (a live countdown, negative once the forwarder has arrived), time waiting, status. **The cut time column and the gap column are dropped** | Must |
| DSH-8 | **Status column.** Each upcoming LL says whether it is **held** and why ("zone N full" or "all lanes busy"). The first LL that is not held by its zone is marked **NEXT**. It goes to a lane as soon as one is free. An LL whose forwarder has arrived is marked **LATE** with its running lateness. If no LL can be called out, a message says so | Must |
| DSH-9 | **View filter** above the table, with two options: **Upcoming LLs only** and **Upcoming and in lanes**. The default is upcoming only (approved, Q5) | Must |
| DSH-10 | **LLs being processed in the table.** When the filter includes them, the LLs being processed in lanes are added to the same table, **one per busy lane (Option B, approved, Q4)**. **They are grouped at the top, with the LL that arrives soonest first** (approved, Q6), and the upcoming LLs follow below, also ordered by time to arrival. Their status says **Processing, lane N, x min left**. They have no queue position, and are shaded differently. There are never more of them than lanes | Must |
| DSH-11 | **Lane cards** (kept, below the table). One card per lane showing either **Idle**, or the LL being processed with its cartons, the time remaining and a progress bar for the processing. **(v1.1, approved) There is no "behind" list and no queue size against a cap, because a lane holds one LL** | Must |
| DSH-12 | Optional toggles at the bottom: recently staged LLs with time from cut to staging, and the event log (SDP requirement 5) | Could |

### 6.3 Tab 2: floor view (second tab)
| ID | Requirement | Priority |
|---|---|---|
| DSH-13 | **Zone cards.** Six cards, each with the zone name, a status chip, used and total pallets (for example 31 / 48), a fill bar separating **staged** pallets from pallets **reserved by LLs still in a lane**. **The card is primarily in pallets.** Below the progress bar it shows three figures: **pallets staged, pallets reserved, and the number of LLs in the zone** (staged LLs plus LLs reserved in a lane; an LL that skipped the zone check reserves nothing, so it is not counted). **Removed from the cards: the staging time figures and the "queued, waiting for this zone" count** (approved, Q2) | Must |
| DSH-14 | **Zone detail.** Pick a zone to list the LLs in it, with forwarder, cartons, pallets, state, time in staging and handover time. The time in staging column is kept (approved, Q7) | Should |
| DSH-15 | Pallets used per zone over the day as a line chart | Could |

*Removed in v1.1:* the staging time readout (average and longest, overall and per zone, old DSH-7), and the count of LLs queued for each zone on the zone cards.

Layout: readable on a laptop or a wall display. The visual design follows the reference screenshot of the current dashboard.

## 7. Technical Approach

- **Pipeline:** `mockup/Data _Prep.ipynb` is the only place synthetic columns are generated. It writes `data/Mockup_Data.xlsx`.
- **Simulation engine (built):** `mockup/engine.py`, a plain Python module with no Streamlit dependency. It runs the day as a discrete-event simulation (events are an LL being cut, a forwarder arriving, an LL finishing processing, and a handover) and records every LL's timestamps. `Simulation.state_at(clock)` then returns the queue (with each row's reason held and its countdown to arrival), the LLs being processed in lanes, lane cards, zone occupancy, late LLs and counters for any clock time, ready for the dashboard. `Simulation.summary()` gives the headline figures, `ll_table()` the per-LL results, and `event_log()` the event log (DSH-12). Updated to v1.1: the priority key is arrival time, and each lane holds one LL.
- **Tests (built):** `mockup/test_engine.py`, written for **pytest**. It holds small scenario tests (41 tests), the section 10 build checks run on the real day, and checks of the section 8 figures. Run `python mockup/engine.py` for the summary, and `python -m pytest mockup -v` from the repository root for the tests (96 in total across the suite, all passing).
- **Precompute, then replay.** Because the run is deterministic, the timeline is computed once per parameter set and cached (for example with `st.cache_data`). The clock only reads from it, which keeps the UI fast and makes pause, jump and restart simple. Changing a parameter recomputes the timeline.
- **Streamlit dashboard (built to v1.1):** `mockup/app.py`, with pure helpers in `mockup/view_helpers.py`. Two tabs, in the section 6 layout, with the call-out view first. The clock advances on a `st.fragment` timer (every 0.5 s) and its position lives in `st.session_state`. The simulation is cached per set of parameters, so changing a setting in the sidebar re-simulates the day. Run it from the repository root with `python -m streamlit run mockup/app.py`. `streamlit` and `pytest` are in `requirements.txt`.
- **Dashboard tests (built):** `mockup/test_dashboard.py` tests the helpers, and runs the app headless with Streamlit's `AppTest` to check that what is shown matches the engine at several clock times, that play, restart and settings changes work, and that the clock advances and stops at the end of the day. For v1.1 it also checks the tab order and section headers, the queue filter and its grouping, the table columns (no cut time), the zone card contents, and that there is no lane cap setting.
- **Files:** every new file lives under `mockup/`.

## 8. Review: what a trial run of these rules showed

**The first table and findings below are for the v1.0 rules as built** (gap ordering, 100-carton lane queues). The v1.1 rules are trialled in the two subsections after them. These figures were produced by `mockup/engine.py` on `Mockup_Data.xlsx`, and the default row is checked by `test_engine.py`. Parameters are at the defaults except where noted. Lateness figures are in minutes. Staging time is the time from staging to handover, for LLs that were not late. The two reference rows use the engine's diagnostic switches (`arrived_skips_zone_check`, `zone_gate`). An earlier throwaway estimate gave slightly higher lateness (total 253 minutes), because it did not wake a waiting LL at the exact moment its forwarder arrived. The engine does.

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
5. **LLs spend a long time in staging, and the gate barely changes it.** For LLs that were not late, the mean time in staging is 341 minutes (5.7 hours), the 95th percentile is 676 minutes, and the longest is 940 minutes. With no zone gate it is 350 minutes. Total pallet-hours in staging fall only 6% (2,036 against 2,158). This follows from the decision to call out as soon as space allows. The dashboard readout for staging time is removed in v1.1 (section 6.3), but the engine still calculates it.
6. **The priority queue has no effect on staging time.** The order decides who goes first, but every LL is sent out as soon as it can be.

### Trial 1: ordering by time to arrival alone (v1.1)

To see what the new ordering does by itself, I ran the engine with the key replaced by arrival time (the same ranking as time to arrival, SIM-6), and the lanes unchanged. This was done with a temporary variant of the v1.0 engine, before the changes were built. Other parameters are at the defaults, except the lane count.

| Lanes | Ordering | Max LLs in queue | LLs that waited | Late LLs | Lateness: mean / longest / total (min) | Cut to staged: mean / longest (min) |
|---|---|---|---|---|---|---|
| 12 | Gap (v1.0) | 30 | 60 | 9 | 27 / 115 / 242 | 30 / 491 |
| 12 | **Time to arrival (v1.1)** | 30 | 60 | **7** | 32 / 115 / **225** | 30 / 488 |
| 3 | Gap (v1.0) | 122 | 173 | 101 | 196 / 432 / 19,844 | 253 / 1,020 |
| 3 | **Time to arrival (v1.1)** | 149 | 218 | **151** | 188 / 350 / 28,313 | 312 / 1,022 |

At the default 12 lanes, ordering by time to arrival is slightly better: two fewer late LLs and 17 fewer minutes of total lateness. When lanes are scarce (3), it leaves more LLs late (151 against 101), although the worst lateness is shorter (350 against 432 minutes). The default view would change little. A reviewer who reduces the lane count would see a different picture.

### Trial 2: the v1.1 rules together, with one LL per lane (v1.1)

This run combines arrival-time ordering with the Q4 lane rule: each lane processes one LL at a time, with no queue behind it and no carton limit. These figures are now produced by the built engine (`python mockup/engine.py`, and `test_engine.py` checks the default row and the other lane counts). They match the estimate I made before building, apart from one correction noted in finding 3.

| Lanes | Max LLs in queue | LLs that waited | Mean wait in queue | Late LLs | Lateness: mean / longest / total (min) | Cut to staged: mean / longest (min) | Staged pallets, peak per zone (1 to 6) |
|---|---|---|---|---|---|---|---|
| **12 (default)** | **31** | **108** | 19 min | **7** | 32 / 115 / 225 | 30 / 488 | 48, 48, 48, 48, 48, 38 |
| 24 | 30 | 58 | 19 min | 7 | 32 / 115 / 225 | 29 / 488 | 48, 48, 48, 48, 48, 38 |
| 8 | 50 | 231 | 32 min | 4 | 34 / 115 / 136 | 42 / 458 | 48, 48, 48, 48, 48, 38 |
| 6 | 82 | 297 | 55 min | 6 | 24 / 115 / 146 | 65 / 459 | 48, 45, 47, 48, 48, 32 |
| 3 | 167 | 319 | 309 min | 149 | 181 / 344 / 27,004 | 320 / 1,023 | 24, 19, 27, 17, 37, 18 |

Reference rows, also from the built engine at 12 lanes: with arrived LLs obeying the zone gate (no skip), 7 LLs are still late but total lateness rises from 225 to 377 minutes and the longest from 115 to 168. With the zone gate off, the queue peaks at 10 LLs, 77 LLs wait, only 1 LL is late, and zones overfill to 50, 48, 55, 50, 76 and 38 pallets.

All 327 LLs are staged and handed over in every run.

1. **At the default 12 lanes, lateness is unchanged by the lane rule.** Late LLs and total lateness (7 LLs, 225 minutes) are the same as with 100-carton lane queues in trial 1. What changes is where LLs wait: **108 LLs spend time in the priority queue, against 60 before**, because the LLs that used to sit in a lane's buffer now wait in the priority queue instead. The call-out queue on screen is therefore busier, and the in-lane rows are never more than 12.
2. **The mean wait in the queue is the same (19 minutes),** and the longest wait is about the same. The waiting is dominated by full zones (zones 1 to 5 reach 48 pallets), not by lanes.
3. **The lanes are saturated at the peak.** The peak hour cuts 1,113 cartons against a capacity of 1,200, and all 12 lanes were busy at once at some point. With 24 lanes, up to 19 are busy at once (my earlier estimate of 17 was sampled too coarsely), so 12 lanes do limit the flow at the busiest moments. Even so, the late count and total lateness are the same with 24 lanes (7 LLs, 225 minutes), and cut-to-staging time improves by only a minute.
4. **Fewer lanes do not simply mean more late LLs.** With 8 lanes, only 4 LLs are late, and with 6 lanes, 6, against 7 at 12 lanes. The cost shows up as longer times from cut to staging (42 and 65 minutes against 30). I have not investigated why fewer lanes reduce lateness, so treat it as an observation. At 3 lanes the system overloads (149 late LLs, queue of up to 167).

## 9. Decisions

All assumptions from earlier drafts are confirmed, and all open questions are answered, including the v1.1 questions Q1 to Q7 (section 12). The full record, with the reasoning, is in [Decision_Log.md](Decision_Log.md).

| # | Decision |
|---|---|
| D1 | ~~Priority key is the smallest gap first (`Handover Time` minus `Added Date`)~~ **Superseded in v1.1 (Q1) by D9** |
| D2 | Call-out does not wait for the forwarder's arrival. The current call-out rule is kept |
| D3 | LLs in a lane count towards zone fullness |
| D4 | The zone check is "fits", so a zone can never exceed capacity |
| D5 | ~~An LL that does not fit a lane blocks the queue~~ **Superseded in v1.1 (Q4) by D10.** There is no fit test any more |
| D6 | Zone capacity is 48 pallets, and one location holds one pallet |
| D7 | The zone imbalance from random forwarder assignment is kept |
| D8 | The 16:00 call-out cut-off from the SDP is ignored, and the simulation uses its own values |
| D9 | **(v1.1)** The call-out queue is ordered by time to arrival, soonest first. This is the same order as arrival time, so the queue does not re-sort |
| D10 | **(v1.1)** Each lane processes one LL at a time, with no queue behind it and no carton limit. An LL waits in the priority queue until a lane is free, and the lowest-numbered free lane is used |
| D11 | **(v1.1)** The call-out view is the first tab. LL progress and late LLs move to it. Zone cards show pallets, with the pallets staged, pallets reserved and LL count below the bar |
| D12 | **(v1.1)** The queue table drops cut time, and has a filter for showing the LLs being processed in lanes, grouped at the top. The dashboard no longer shows staging time |

## 10. Success Criteria

### Usefulness (the point of the mockup)
In an Ops review session, a reviewer should be able to say, after watching one day:
1. Whether the floor view shows what they would otherwise check on the floor.
2. Whether they can see which LLs are held back, why, and which are late.
3. Whether the call-out view (progress, late LLs, queue and lanes) shows what they need to decide a call-out, and what is missing.
4. Whether seeing lanes fill and clear helps them judge how many LLs can be called out at once.

Feedback is captured as notes. No numeric target is set.

### Build checks
- Replaying the day twice gives identical output.
- No LL is called out before it is cut, or staged before its processing finishes.
- Processing time equals `Cartons / lane_throughput` for every LL (an LL of 50 cartons takes 30 minutes at the defaults).
- **(v1.1)** A lane processes at most one LL at a time, and an LL enters a lane only when that lane is free.
- **(v1.1)** No LL is ever held at the end of a lane: it is staged the moment its processing finishes.
- A zone's pallets (staged plus reserved) never exceed `zone_capacity`.
- An LL leaves the priority queue only if its zone has room, or its forwarder has already arrived.
- Among the LLs that pass the zone gate, LLs leave the priority queue strictly in key order.
- **(v1.1)** If no lane is free, no LL leaves the queue. If a lane is free, the first LL that passes the zone gate goes to it.
- The late count equals the number of LLs staged after their `Handover Time`, and each LL's lateness equals the difference.
- At every point in time, waiting, in-lane, staged and completed LLs add up to the LLs cut so far.
- **(v1.1)** Among the LLs that pass the zone gate, LLs leave the priority queue in order of arrival time, soonest first.
- **(v1.1)** An LL enters the lowest-numbered free lane.
- **(v1.1)** The call-out view is the first tab. The queue table is sorted by time to arrival and has no cut time column. With the filter on "Upcoming LLs only" it shows exactly the LLs in the queue. With "Upcoming and in lanes" the in-lane LLs are grouped above the upcoming ones, soonest arrival first, and their number equals the "LLs in lanes" card, which is never more than the number of lanes.
- **(v1.1)** Zone cards show no staging time and no queued count, and their staged and reserved LL counts match the zone detail list.

## 11. Milestones

SDP Table 14 puts "finalise M3 outputs and decision variables with Ops, finish mock-up" in November 2026.

| Step | Deliverable | Depends on |
|---|---|---|
| 1 | Decisions recorded (done, see `Decision_Log.md`) | |
| 2 | Simulation engine with the priority queue, lanes, zone gate and lateness tracking, and tests for the section 10 build checks (**done**, `engine.py` and `test_engine.py`) | Step 1 |
| 3 | Confirm the section 8 results from the engine (**done**, table refreshed) | Step 2 |
| 4 | Streamlit dashboard v1.0: header, zone cards, counters and late panel, queue and lane panel, using the v1.0 layout and requirement numbers (**done**, `app.py`) | Step 3 |
| 5 | Should and Could items: settings panel, staging time, workload, zone detail, occupancy chart, recently staged, event log (**done** for v1.0, all of its DSH-1 to DSH-17 are built) | Step 4 |
| 6 | **Apply the v1.1 changes:** engine ordering key and one-LL-per-lane rule, tab order and layout, zone cards, queue table with the in-lane filter, and updated tests. Then refresh section 8 from the engine (**done**, 96 tests passing) | Section 12 |
| 7 | Ops review session, with feedback captured for the December edits | Step 6 |

## 12. v1.1 changes (built)

Q1 to Q7 were all answered on 2026-11-15, and are written into sections 5 and 6. The changes have been applied to the engine, the dashboard and the tests, and section 8 has been refreshed from the engine. The record is in [Decision_Log.md](Decision_Log.md).

### 12.1 What was asked for
| # | Change | Where in this PRD |
|---|---|---|
| P1 | The call-out queue is ordered by **time to arrival** | SIM-5, SIM-6, DSH-7 |
| P2 | The **call-out view becomes the first tab** | Section 6, goals 6 and 7 |
| P3 | **LL progress and the late LLs panel move** from the floor view to the call-out view | DSH-4, DSH-5 |
| P4 | **Zone cards keep only the breakdown of LLs staged and reserved.** The staging time figures and the "queued, waiting for this zone" count are removed | DSH-13 |
| P5 | The call-out view runs top to bottom: **LL progress, late LLs, queue breakdown cards, call-out queue** (then the lane cards) | DSH-4 to DSH-11 |
| P6 | The queue table **drops the cut time column**, and gains a **filter to include the LLs being processed in lanes** | DSH-7, DSH-9, DSH-10 |
| P7 | The lane cards stay, **without the "Nothing behind" line** | DSH-11 |
| P8 | **Lane logic changes (from the answer to Q4):** the 100-carton restriction is removed, LLs wait in the priority queue to enter a lane, and a lane processes one LL at a time, with the 100 cartons per hour rule setting processing time | SIM-7 to SIM-10, SIM-13, SIM-14, sections 4.3 and 4.4 |

### 12.2 Answers

| # | Question | Answer (2026-11-15) | Where it is written |
|---|---|---|---|
| Q1 | Does "order by time to arrival" change the actual call-out order? | **Yes.** The call-out order changes. It supersedes D1 | SIM-5, SIM-6 |
| Q2 | Zone card breakdown | **Primarily pallets.** Below the progress bar: pallets staged, pallets reserved, and the LL count in the zone | DSH-13 |
| Q3 | What are the queue breakdown cards? | **The existing four cards, and each card segment gets a header** | DSH-6 |
| Q4 | What "in lanes" rows does the table show? | **Option B: only the LL being processed in each lane.** This also changes the lane rule: the 100-carton restriction is removed, LLs wait in the priority queue to enter a lane, and a lane processes one LL at a time (100 cartons per hour sets processing time) | DSH-10, SIM-7 to SIM-14 |
| Q5 | Filter options and default | **Correct.** Upcoming LLs only (default), and upcoming and in lanes | DSH-9 |
| Q6 | How are in-lane rows ordered? | **Grouped at the top of the table, with the earliest LL first** | DSH-10 |
| Q7 | Keep "time in staging" in the zone detail table? | **Yes, kept** | DSH-14 |

#### What the Q4 answer changes

Your answer picks Option B, and goes further by removing lane queues altogether. The effects, written into section 5.4 and 5.5:

- **Lanes hold one LL.** A lane is free or busy. There is no queue behind a busy lane, no "queue size", and no 100-carton cap, so the `lane_queue_cap` setting is removed.
- **LLs wait in the priority queue.** An LL leaves it only when a lane is free (and its zone has room). The LLs that used to wait inside a lane now wait in the call-out queue, so that queue becomes busier on screen (108 LLs wait at some point, against 60).
- **No oversize rule.** An LL of any size, up to 205 cartons (about 2 hours 3 minutes), can use a free lane.
- **Lanes show Idle or one LL.** The lane cards have no "behind" list. The table's in-lane rows are at most one per lane, which are exactly the LLs counted in the "LLs in lanes" card.
- **Decision D5 no longer applies,** because there is no test of whether an LL fits.
- **Results change.** At 12 lanes, late LLs and total lateness stay the same as trial 1 (7 LLs, 225 minutes). See section 8, trial 2.

### 12.3 Smaller defaults I assumed
- The "gap" column is replaced by the live **time to arrival**, and arrival is still shown as a clock time. The "time waiting" column stays.
- Once a forwarder has arrived, time to arrival shows as a negative value and the row is marked LATE.
- The optional toggles (recently staged, event log) stay at the bottom of the call-out view.
- The zone detail and the occupancy chart stay on the floor view.
- The workload bars move together with LL progress.
- "Give a header to these card segments" (Q3) is read as a header on every segment of the call-out view, with the four queue cards under "Queue breakdown".
- Within the in-lane group, "earliest LL at the top" (Q6) is read as the LL whose forwarder arrives soonest.
- When several lanes are free, the lowest-numbered one is used (SIM-10). The answer to Q4 did not say.
- The processing progress bar on each lane card shows how much of the LL's processing time has passed.
- "No restriction" on cartons (Q4) means no limit at all, so a 205-carton LL occupies one lane for about 2 hours 3 minutes.

### 12.4 What changed in the code
- `engine.py`: the priority key, and **the lane rules**. Lane queues, the carton cap, the fit test, and the oversize exception are removed, and an LL is sent to a free lane instead. The `lane_queue_cap` parameter is gone. The docstring and the rows `state_at` returns changed (one LL per lane, and a new `in_lanes` table with arrival countdowns). The zone snapshot dropped the staging time and queued columns and gained reserved LL counts.
- `test_engine.py`: tests for the lane queue, no overshoot, oversize LLs, the shortest-lane rule and lane blocking were replaced with tests for one LL per lane and the lowest-numbered free lane. The gap-ordering tests changed to arrival ordering.
- `app.py` and `view_helpers.py`: tab order, moved sections, the zone card text, the queue table columns and the filter, lane cards (Idle or one LL with a progress bar), and the removal of the lane queue cap setting from the sidebar. `queue_display` became `call_out_table`.
- `test_dashboard.py`: tab order, headers, moved metrics, the lane setting, and checks for the filter and the table.
