# Decision Log: Dashboard Mockup

| | |
|---|---|
| Date | 2026-11-15 |
| Applies to | `mockup/PRD.md` v1.0 |
| Source of decisions | Project owner's replies to the assumptions and open questions listed in PRD v0.7 |

This file records the assumptions made while drafting the PRD and the answers given to each open question, so the reasoning stays traceable. The PRD holds the resulting requirements. This file holds the "why".

## 1. Assumptions

**Status: all confirmed.** The project owner confirmed on 2026-11-15 that "all assumptions made are valid". Questions Q1 to Q8 below also settle several of them explicitly, as noted.

### Data and synthetic inputs
| # | Assumption | Status |
|---|---|---|
| A1 | `Handover Time` is the forwarder arrival time, known exactly when the LL is cut, and is also when the LL leaves staging | Confirmed |
| A2 | Handover times come from a normal distribution fitted to historic data, floored at `Added Date` + 1 hour. The real data is lumpy (72% between 14:00 and 18:59), and 24% of sampled times fall at or after 19:00 | Confirmed |
| A3 | Forwarders are uniform across A to L, paired into zones 1 to 6. The real mix is about 60% one forwarder | Confirmed |
| A4 | Pallets = `ceil(Cartons / 50)`, minimum 1 | Confirmed |
| A5 | Zone capacity is 48 pallets, and one location is one pallet | Confirmed (see Q6) |
| A6 | `Complete Date` is ignored. The real call-out and staging times in the data are not used, because the simulation produces its own | Confirmed |
| A7 | One day of data stands for a typical day. It is a heavy day (3,248 DNs, against the SDP's 2,000 to 3,250) | Confirmed |

### Priority queue
| # | Assumption | Status |
|---|---|---|
| A8 | The key is smallest gap first (`Handover Time` minus `Added Date`) | Confirmed (see Q1) |
| A9 | The key is fixed at cut time. Long-gap LLs can be overtaken by later short-gap ones | Confirmed |
| A10 | Ties go to the earlier `Added Date` | Confirmed |

### Lanes
| # | Assumption | Status |
|---|---|---|
| A11 | Lane queue size is measured in cartons, and includes the LL being processed | Confirmed |
| A12 | Processing time is linear in cartons (100 per hour per lane), with no setup, travel or breaks, and all 12 lanes work all day | Confirmed |
| A13 | The shortest lane (fewest cartons, lowest number on a tie) is checked. If an LL does not fit it, it fits no lane | Confirmed |
| A14 | No overshoot: the lane's queue plus the LL's cartons must not exceed 100 | Confirmed |
| A15 | Oversize LLs (over 100 cartons) go only to an empty lane, which they then hold alone. Ten LLs are affected | Confirmed |
| A16 | An LL that fits no lane blocks the queue. Only zone-blocked LLs are skipped | Confirmed (see Q5) |
| A17 | A lane's queue size drops only when an LL finishes, by its whole carton count | Confirmed |
| A18 | Staging is immediate when processing finishes. No travel time | Confirmed |

### Zones and lateness
| # | Assumption | Status |
|---|---|---|
| A19 | Zone fullness counts staged LLs plus LLs still in a lane, because a called-out LL reserves its space | Confirmed (see Q3) |
| A20 | The zone check is "fits": pallets in the zone plus the LL's pallets must not exceed capacity | Confirmed (see Q4) |
| A21 | An LL whose forwarder has arrived skips the zone check, reserves no pallets, and is handed over the moment it is staged | Confirmed |
| A22 | Late means not staged by `Handover Time`. Lateness runs from handover time to staging | Confirmed |
| A23 | Calls continue after the SDP's 16:00 cut-off | Confirmed (see Q8) |

### Process
| # | Assumption | Status |
|---|---|---|
| A24 | The section 8 figures in the PRD come from a throwaway script, not the engine. They are expected values, to be reproduced once the engine exists | Confirmed |
| A25 | Staging time in the results counts only LLs that were not late | Confirmed |
| A26 | Streamlit is the front end, with the day computed once and replayed. `streamlit` still needs adding to `requirements.txt` | Confirmed |

## 2. Open questions and responses

| # | Question | Response | Effect on the PRD |
|---|---|---|---|
| Q1 | Which way round is the priority key, smallest gap first or largest? | **Smallest gap first.** | The "creation minus handover" wording is settled as smallest gap first. The assumption flag and the open question were removed from SIM-5 |
| Q2 | Should call-out wait until closer to arrival, to cut staging time? | **No. Keep the current call-out rule.** The reasoning given: even if staging time is minimised overall, staging space is still wasted, so waiting does not solve the underlying problem | No release window. Added to the Non-Goals. The long staging time (mean 341 minutes) stays as a known cost, and finding 5 in section 8 now refers to it as a result of this decision. The staging time readout (DSH-7) stays so reviewers can see it |
| Q3 | Should LLs in a lane count towards zone fullness? | **Yes, based on the current rule.** | SIM-16 confirmed. The assumption flag was removed |
| Q4 | Should the zone check be "fits" or "not full"? | **Fits. A zone cannot exceed capacity.** | SIM-15 confirmed. The build check that no zone exceeds capacity stays |
| Q5 | Should an LL that does not fit a lane block the queue? | **Yes, for this simulation let them block the queue.** | SIM-14 step 4 now says this is by design. A build check was added for it |
| Q6 | Is 48 locations per zone correct, and is one location one pallet? | **Yes, that is correct.** | The assumption flag was removed from `zone_capacity` in section 4.3 |
| Q7 | Is the zone imbalance acceptable? | **Keep the imbalance for now.** | No change to the data. A note was added to the `Zone` row in section 4.2. Zones 3 and 5 will keep filling and zone 6 will not |
| Q8 | What should the page say about the 10 LLs cut after 16:00? | **Keep to the simulation values and ignore this detail from the document.** | The 16:00 cut-off marker (old DSH-4), the cut-off rule (old SIM-20) and the data-fact bullet about 10 late cuts were removed. Added to the Non-Goals. Dashboard requirement numbers were renumbered, so DSH-5 onwards moved down by one |

## 3. Changes made to the PRD (v0.7 to v0.8)

- Status line, related files, and a pointer to this log added.
- Purpose and goals reworded so they no longer claim the rule minimises staging time.
- Non-Goals extended with: no release window, no 16:00 cut-off.
- SIM-5, SIM-16 and the `zone_capacity` parameter: assumption flags removed.
- SIM-14 step 4: blocking stated as by design.
- SIM-20 replaced: calls continue with no cut-off.
- The 16:00 marker requirement removed, and the DSH numbers renumbered.
- Section 9 replaced: open questions became a short table of decisions D1 to D8.
- Build checks: one check added for queue blocking.
- Milestones: the "settle open questions" step is marked done, and the Step 4 requirement numbers were updated.

## 4. Implementation choices made while building the engine (PRD v0.9)

These fill gaps the PRD left open. **I1 to I7 were accepted by the project owner on 2026-11-15** with no issues. I8 was changed by the owner's instruction.

| # | Choice | Why | Status |
|---|---|---|---|
| I1 | A waiting LL is **woken at the exact moment its forwarder arrives**, so it skips the zone check at that moment | Without a trigger at arrival, the skip only happened at the next unrelated event. This lowered total lateness from 253 to 242 minutes compared with the earlier throwaway estimate | Accepted |
| I2 | When several events share an instant, they are applied in this order: handovers, finishes, arrivals, cuts. The call-out step then runs once | Frees zone space before deciding who is called out, and keeps the run deterministic | Accepted |
| I3 | Ties in the priority key go to the earlier `Added Date`, then to the lower LL number | The PRD gives only the first tie-break | Accepted |
| I4 | A reserved LL whose forwarder arrives while it is still in a lane keeps its pallets reserved until it is staged, and is handed over at that moment | It has not yet been staged, so there is nothing to remove earlier | Accepted |
| I5 | An LL staged at exactly its arrival time is **on time**. Late means strictly after | Avoids counting zero-second lateness | Accepted |
| I6 | In the dashboard queue view, once calling has finished for an instant, every waiting LL that passes the zone gate is waiting for lane space, and only the first of them is marked "next" | Because an LL that does not fit a lane blocks the queue (D5), the rows behind it cannot move either | Accepted |
| I7 | Two diagnostic switches (`zone_gate`, `arrived_skips_zone_check`) exist in the engine parameters | They only reproduce the two reference rows in PRD section 8. They are not dashboard settings | Accepted |
| I8 | Tests are written for **pytest** (originally `unittest`, because pytest was not installed) | `pytest` has since been installed and is listed in `requirements.txt`. The tests were rewritten with fixtures, plain asserts and parametrisation, and now number 36 | Changed by owner, done |

## 5. Dashboard choices made while building the Streamlit app (PRD v1.0)

These fill gaps the PRD left open, and are **not yet confirmed**. Please check them.

| # | Choice | Why |
|---|---|---|
| B1 | When no waiting LL can be called out, the call-out tab shows a warning ("every LL in the queue is waiting for its zone") instead of highlighting a "next" row | At the default 12 lanes the queue is only ever held by full zones, so a "next" row (an LL that is ready but waiting for a lane) almost never exists. It appears with fewer lanes, for example 3 |
| B2 | Zone status is OK below 80% (the warning threshold), FILLING from 80%, FULL at 100%. The threshold is a sidebar setting | PRD section 4.3 sets 80% as the default |
| B3 | Playback speed is chosen in simulated minutes per second (1 to 60, default 10). At 10, the day plays in about 1 minute 45 seconds | The PRD asks for configurable speed without values |
| B4 | The jump slider works best when paused. Dragging it while playing is ignored | The timer moves the slider every refresh, and Streamlit cannot take both |
| B5 | The occupancy chart, recently staged table and event log sit behind toggles and are off by default | They are the "Could" items, and leaving them off keeps each refresh light |
| B6 | Changing any setting re-simulates the day, returns the clock to the start and stops playback | The old clock time may not exist in the new run |
| B7 | Pressing Play at the end of the day restarts from the beginning | Avoids a Play button that does nothing |
| B8 | The sidebar settings reach beyond the PRD defaults (lanes 1 to 24, throughput 25 to 400, lane cap 50 to 400, zone capacity 12 to 96) | They let a reviewer explore, for example a 3-lane run to see a "next" row and late rows in the queue |

## 6. Changes in PRD v1.1 (built)

Requested on 2026-11-15, and **built the same day** (engine, dashboard and 96 passing tests). Answers to Q1 to Q7 were all given on 2026-11-15 and are recorded below.

| Q | Answer given 2026-11-15 |
|---|---|
| Q1 | Yes, the call-out order changes. Supersedes D1 (smallest gap first) |
| Q2 | Zone cards are primarily in pallets. Below the progress bar: pallets staged, pallets reserved, and the LL count in the zone |
| Q3 | Correct (the existing four cards). Each card segment gets a header |
| Q4 | Option B: only the LL being processed in each lane. **Also a rule change:** remove the 100-carton restriction, LLs wait in the priority queue to enter a lane, and a lane processes one LL at a time with processing time from the 100 cartons per hour rule |
| Q5 | Correct: upcoming only (default), and upcoming and in lanes |
| Q6 | In-lane rows are grouped at the top of the table, with the earliest LL at the top |
| Q7 | Yes, the zone detail table keeps its time in staging column |

**Consequences of the Q4 answer:** D5 (an LL that does not fit a lane blocks the queue) no longer applies, because there is no fit test. Lane assumptions A11 to A18 change: lane queue size, no overshoot and oversize LLs are replaced by one LL per lane. The `lane_queue_cap` parameter is removed. At 12 lanes the trial shows the same late LLs as with the old lane queues (7 LLs, 225 minutes), but 108 LLs wait in the priority queue against 60 (PRD section 8, trial 2). Also corrected: the peak hour cuts **1,113 cartons**, not about 770 as the PRD said, so lanes are about 93% used at the peak.

**Interpretations I made, please check:** When several lanes are free, the lowest-numbered one is used. "Earliest LL" in Q6 means the LL whose forwarder arrives soonest. The "LL count in the zone" in Q2 is staged LLs plus LLs reserved in a lane. "Give a header" in Q3 means a header on every segment of the call-out view.

The requested changes themselves:

| # | Requested change | Status |
|---|---|---|
| P1 | Order the call-out queue by time to arrival | Approved (Q1). It supersedes D1 (smallest gap first), and `engine.py` and its tests change. Trial at 12 lanes: late LLs 9 to 7, total lateness 242 to 225 minutes. At 3 lanes: late LLs 101 to 151 |
| P2 | Call-out view becomes the first tab | Pending |
| P3 | LL progress and late LLs move to the call-out view | Pending |
| P4 | Zone cards keep only the staged and reserved breakdown. Staging time and "queued for this zone" are removed | Pending. This also removes the dashboard staging time readout, which Q2 in the earlier log said to keep so reviewers could see its cost. The engine still calculates it |
| P5 | Call-out view order: LL progress, late LLs, queue breakdown cards, call-out queue | Pending |
| P6 | Drop the cut time column, and add a filter to include LLs being processed in lanes | Pending |
| P7 | Keep lane cards, remove the "Nothing behind" line | Pending |

| # | Open question | Default used in the PRD |
|---|---|---|
| Q1 | Does ordering by time to arrival change the real call-out order, or only the table sort? | The call-out order changes |
| Q2 | Zone card breakdown in LLs or pallets? | Both, LL count first |
| Q3 | What are the queue breakdown cards? | The existing four cards. A per-zone queue breakdown is the alternative |
| Q4 | Only the LL processing in each lane, or every LL in a lane? | Every LL in a lane |
| Q5 | Filter options and default | Upcoming only (default), upcoming and in lanes |
| Q6 | In-lane rows mixed into one sort, or grouped? | Mixed, sorted by time to arrival |
| Q7 | Keep "time in staging" in the zone detail list? | Kept |

### Choices made while building v1.1

These fill small gaps the PRD left open, and are **not yet confirmed**. Please check them.

| # | Choice | Why |
|---|---|---|
| B9 | In the queue table, the **Waiting** column shows time since the LL was cut for upcoming LLs, and the time it waited in the queue before entering its lane for in-lane rows | The cut time column was dropped, so this is the only place the wait shows |
| B10 | Status wording: "Held: zone N full", "NEXT, waiting for a free lane", "Waiting: all lanes busy", "LATE x min, waiting for a free lane", and "Processing, lane N, x min left" | The old "no lane space" no longer made sense once lanes stopped holding queues |
| B11 | "NEXT" marks the first upcoming LL that is not held by its zone. It is always waiting for a lane, because if a lane were free it would already have gone | Follows from the lane rule |
| B12 | The "#" (queue position) column is blank for in-lane rows. A late LL being processed is tinted red rather than blue | Q6 asked for no queue position on in-lane rows, and lateness matters more than state |
| B13 | The zone card shows its three figures as separate lines: pallets staged, pallets reserved, LLs in the zone | Q2 asked for them below the progress bar |
| B14 | "LLs in the zone" counts staged LLs plus LLs being processed that reserved pallets. An LL that skipped the zone check is not counted | It reserves no pallets |
| B15 | The "Queue breakdown" card for cartons is labelled "Cartons being processed", and "LLs in lanes" is never more than the lane count | Matches the one-LL-per-lane rule |
| B16 | The zone detail list and the occupancy chart sit on the floor view, and the recently staged and event log toggles on the call-out view | Not specified by the request |
| B17 | The engine's zone snapshot no longer includes the staging time and queued figures. Time in staging is still in the zone detail list, in `ll_table()` and in `summary()` | The dashboard no longer shows them (P4) |
| B18 | **Correction:** with 24 lanes, up to 19 lanes are busy at once, not 17 as the PRD said before the build | My earlier estimate sampled every 2 minutes, and the engine measures exactly |

## 7. Items to revisit later

These are not open questions for the mockup, but they are choices made for the simulation that the full build may change.

- **Call-out timing (Q2).** The full M3 model uses estimated arrival as a soft constraint and calls out "closer to forecast arrival" (SDP 4.3, 3.3). The mockup does not.
- **The 16:00 cut-off (Q8).** The SDP states that all LLs are called out by 16:00. The mockup ignores it.
- **Zone mapping (Q7).** Forwarders were assigned to zones at random. Real zones are arranged alphabetically by forwarder and sized by DSV data (SDP 2.1, 5.2).
- **Priority key (Q1).** The mockup's key is a stand-in for the M3 weighted score (SDP 4.3).
