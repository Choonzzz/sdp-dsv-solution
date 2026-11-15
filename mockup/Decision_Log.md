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

## 6. Items to revisit later

These are not open questions for the mockup, but they are choices made for the simulation that the full build may change.

- **Call-out timing (Q2).** The full M3 model uses estimated arrival as a soft constraint and calls out "closer to forecast arrival" (SDP 4.3, 3.3). The mockup does not.
- **The 16:00 cut-off (Q8).** The SDP states that all LLs are called out by 16:00. The mockup ignores it.
- **Zone mapping (Q7).** Forwarders were assigned to zones at random. Real zones are arranged alphabetically by forwarder and sized by DSV data (SDP 2.1, 5.2).
- **Priority key (Q1).** The mockup's key is a stand-in for the M3 weighted score (SDP 4.3).
