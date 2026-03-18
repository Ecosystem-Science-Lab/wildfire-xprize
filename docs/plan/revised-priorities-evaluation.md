# Revised Priorities Evaluation

**Date:** 2026-03-18
**Context:** External review from ChatGPT Pro identified critical flaws in our system plan. This document evaluates the proposed revised priority list through four specialist lenses, identifies consensus and disagreements, and produces a final recommended priority list with a Week 1 checklist.

**Time remaining:** 22 days to competition start (April 9, 2026).

---

## 1. Sensor Strategist Assessment

### On the scope cut: AGREE, but with caveats

The original plan listed 8 sensor tiers. For 22 days, we need ruthless focus. The right cut is:

**KEEP (must-have):**
- **Himawari-9 AHI** -- Non-negotiable. 144 scans/day, AWS NODD with SNS push, fastest geostationary path. This IS our system.
- **VIIRS via DEA Hotspots** -- 6 passes/day at 375m, ~17 min latency, no partnership needed, WFS API requires no registration. This is our confirmation layer.
- **FIRMS API** -- Safety net. Catches anything DEA misses. Poll every 2-5 minutes.

**KEEP (low-effort, real value):**
- **GK-2A** -- DISAGREE with dropping it. The AWS NODD mirror already exists. The incremental engineering cost of ingesting GK-2A is trivial once Himawari works (same ABI-class instrument, same data format). GK-2A provides genuine independent confirmation from a different viewing angle (128.2E vs 140.7E). This matters for the double-counting problem. Keep it, but only as a cross-check feed into the event store -- not a separate detection pipeline.

**DROP (for now):**
- FY-4B (data access unreliable from NSMC, adds complexity for marginal gain)
- Sentinel-3 SLSTR (~3 hour latency, adds nothing over DEA Hotspots)
- Sentinel-2 (5-day revisit, no thermal band, only useful for post-event confirmation)
- MODIS (redundant with VIIRS, same orbits, coarser resolution)
- FY-3D MERSI (250m is tempting but NSMC data access is a risk we cannot take in 22 days)
- Raw VIIRS processing (direct broadcast partnership is aspirational, not load-bearing)

**DROP Landsat real-time processing.** Keep Landsat via FIRMS only. The FarEarth/Alice Springs partnership is a fantasy at this timeline.

### On HimawariRequest rapid scan (2.5 min): SKEPTICAL but worth one email

The AHI Target Area scan provides 2.5-minute cadence over a 1000x1000 km box. This would be transformative for detection speed -- cutting our geostationary revisit from 10 min to 2.5 min. However:

- The Target Area is controlled by JMA. It is primarily used for typhoons and volcanoes.
- Requesting it for a 2-week fire competition in NSW requires JMA agreement, likely brokered through BoM.
- The probability of success is LOW (maybe 10-15%).
- BUT the cost of asking is one well-crafted email to BoM (satellites@bom.gov.au) explaining the XPRIZE context.

**Verdict:** Send the email. Frame it as "would JMA consider positioning the Target Area over NSW during April 9-21 for bushfire research?" Expect nothing. Move on.

### On OroraTech: WORTH ONE EMAIL, but manage expectations

OroraTech claims 3-minute alerts, 4x4m fires, ~16+ satellites operational by April 2026. If they would share alerts with us during the competition window:
- We get an independent, high-resolution thermal detection layer we cannot build ourselves.
- It fills our biggest gap (small fires between VIIRS passes).

**Concerns:**
- "Public data only" rule interpretation. The R&R says "observations of wildfires shall be made from Space" and "legally-sourced data." It does NOT say "public data only." Commercial data is allowed as long as it is declared and legally obtained.
- OroraTech may want payment or see no benefit in helping a competitor.
- Even a pilot/trial period during the competition would be valuable.

**Verdict:** Send a short email to OroraTech sales. Worst case: they say no. Time cost: 30 minutes.

### On Earth Fire Alliance / FireSat: NOT viable

FireSat (Muon Space) Phase 1 (3 satellites) is planned for mid-2026. It will almost certainly NOT be operational by April 9. The memory file confirms this. Do not pursue.

### On VIIRS direct broadcast: DEPRIORITIZE

Direct broadcast partnerships (GA Alice Springs, BoM, CfAT/Viasat) are the highest-impact data improvement possible -- potentially cutting VIIRS latency from 17 min to 5 min. But:
- 22 days is not enough to establish a government research partnership
- We already have DEA Hotspots at ~17 min with zero effort
- Any partnership that materializes is pure upside, not load-bearing

**Verdict:** Send partnership emails (GA, BoM) as part of the batch of outreach emails, but do not invest engineering time planning for direct broadcast data. Design everything around DEA Hotspots as the VIIRS path.

### Summary recommendation
Core sensor stack: Himawari-9 (custom processing) + GK-2A (cross-check) + DEA Hotspots + FIRMS. Everything else is stretch.

---

## 2. Detection Architect Assessment

### On demoting CUSUM to shadow layer: AGREE

The external review is correct that CUSUM was overclaimed. The numbers in our own domain brief tell the story:

| Fire Area | CUSUM Detection Delay |
|---|---|
| 200 m2 | ~11 hours |
| 500 m2 | ~2.3 hours |
| 1,000 m2 | ~0.8 hours |
| 5,000 m2 | 1 frame (instant) |

For a speed competition, CUSUM adds nothing for fires >1,000 m2 (which are already detectable in a single Himawari frame). For fires of 200-500 m2, CUSUM takes 2-11 hours -- by which time VIIRS will have confirmed or denied the fire. CUSUM's sweet spot (detecting fires too small for single-frame detection but too large for VIIRS to miss) is narrow and does not justify being the "centerpiece."

**What CUSUM is actually good for:** Background monitoring during the 10-11 hour VIIRS gap (15:00-01:00 AEST and 03:00-13:00 AEST). If a 500 m2 fire ignites at 16:00, CUSUM might flag it by 18:00 -- 7 hours before the next VIIRS pass. That is real value, but it is supplementary.

**Recommendation:** CUSUM becomes an optional Week 3 item. If we have time, implement it. If not, contextual + persistence + VIIRS confirmation is sufficient.

### On "immediate provisional alert": AGREE, with safeguards

The current plan HOLDS first detections for 20-30 minutes waiting for persistence. This is backwards for a speed competition where the clarification states "low confidence detections still count if correct."

**The right approach:**

1. **First AHI frame with strong anomaly (BT_B7 > 360K night / saturated):** Immediately report as HIGH confidence. These are almost never false positives.

2. **First AHI frame with moderate anomaly (passes contextual tests, BTD > mean + 3.5*sigma):** Report as PROVISIONAL/LOW confidence immediately. This is the controversial case.

3. **Subsequent frames upgrade or retract:** If the anomaly persists in frame 2 (T+10 min), upgrade to NOMINAL. If it disappears, retract. If VIIRS confirms, upgrade to HIGH.

**False positive risk assessment:**

The concern is that immediate provisional alerts will flood judges with false positives. But:
- The 6-layer filtering pipeline (static masks, geometric filters, contextual detection, ML classifier) runs in <5 seconds BEFORE any alert. Most false positives are eliminated before the alert stage.
- The clarification from the all-teams call says "low confidence detections still count if correct." This means the downside of a false positive is much less than the downside of a delayed true positive.
- Emergency FP reduction protocols remain available if our rate exceeds 5%.

**Key safeguard:** Distinguish "provisional" from "confirmed" in our reporting. Judges see "PROVISIONAL: thermal anomaly detected at [location], [time], awaiting confirmation" vs "CONFIRMED: fire detected at [location], corroborated by [sensors]."

### On the minimum viable detection pipeline for 22 days:

**Week 1 deliverable (MUST):**
1. Himawari HSD decode + BT conversion for Band 7 and Band 14 (NSW segments only)
2. Fast cloud mask (Tier 1: BT_11 < 265K, simple tests)
3. Contextual threshold detection (adapted from GOES FDC / VNP14IMG for AHI)
4. Static masks (land/water, known industrial sites from FIRMS STA)
5. Sun glint rejection (glint angle < 12 deg)
6. Alert generation with lat/lon and confidence tier

This gives us a working fire detector in ~7 days. Everything else (ML, CUSUM, fancy fusion) is optimization.

**What we skip initially:**
- ML classifier (Pass 2) -- push to Week 2 or 3
- CUSUM temporal integration (Pass 3) -- push to Week 3 if time
- Kalman filter DTC modeling -- push to Week 3 if time
- VZA-dependent thresholds -- nice to have, not essential

### On the detection approach for best speed/accuracy tradeoff:

Simple contextual detection + 2-frame persistence gives us:
- **Detection speed:** ~7-15 min (data latency) + 10 min (persistence) = 17-25 min from observation
- **With immediate provisional alerts:** ~7-15 min from observation (no persistence wait)
- **False positive rate:** Contextual detection alone achieves ~0.1% FP rate per scan. Adding persistence drops it to ~0.003%. Adding VIIRS confirmation drops it to near zero.

This is good enough to be competitive. Not optimal, but buildable in 22 days.

---

## 3. Fusion Specialist Assessment

### On the double-counting criticism: VALID and important to fix

The external review correctly identified that our Bayesian scoring counts the same Himawari observation multiple times:

1. AHI strong anomaly: +4.0 LLR (from our raw processing)
2. FIRMS Himawari detection: +3.0 LLR (from FIRMS, which processes the same AHI data)
3. DEA Hotspots Himawari detection: +2.5 LLR (from DEA, which also processes the same AHI data)

These three are NOT independent observations. They are three different processing chains applied to the SAME satellite observation. Treating them as independent inflates confidence and violates the Bayesian framework's conditional independence assumption.

**How to fix:**

**Rule 1: One observation = one evidence contribution.** When the same satellite observation is processed by multiple pipelines, take the MAXIMUM LLR, not the sum.

```
For a given Himawari observation at time T:
  our_detection = contextual_fire_test(AHI_data)     -> LLR = +4.0
  firms_detection = FIRMS_match(time=T, location=L)   -> LLR = +3.0
  dea_detection = DEA_match(time=T, location=L)        -> LLR = +2.5

  combined_LLR_for_this_observation = max(4.0, 3.0, 2.5) = +4.0
  NOT: 4.0 + 3.0 + 2.5 = +9.5
```

**Rule 2: Independence requires different sensors or different times.** True independent evidence comes from:
- Different satellites (Himawari vs GK-2A at the same time: independent, different viewing angles)
- Different sensor types (Himawari AHI vs VIIRS: independent, different orbits, different resolutions)
- Same satellite, different times (Himawari frame at T vs T+10min: semi-independent, temporal persistence)

**Rule 3: Track provenance.** Every piece of evidence in the event store must record:
- Source satellite
- Observation time
- Processing pipeline (our custom, FIRMS, DEA)
- Whether it is a PRIMARY observation or DERIVED from a primary

### On rule-based ladder vs Bayesian: USE RULE-BASED for 22 days

The Bayesian log-odds framework is elegant but:
- Requires careful LLR calibration (we have no empirical data for NSW April conditions)
- Double-counting bugs are subtle and hard to catch
- Debugging "why did this event get confidence 0.73?" is painful during a live competition

A simple rule-based confidence ladder is:

```
LEVEL 1 - PROVISIONAL (report immediately):
  Single AHI frame, passes contextual tests

LEVEL 2 - LIKELY (report with moderate confidence):
  AHI persistent 2/3 frames, OR
  AHI single frame + GK-2A independent detection

LEVEL 3 - CONFIRMED (report with high confidence):
  AHI detection + VIIRS/MODIS detection within spatial match radius, OR
  AHI persistent 3/3 frames AND growing intensity, OR
  Any Landsat/Sentinel-2 confirmation

LEVEL 4 - HIGH CONFIDENCE:
  Multiple independent sensor confirmations (AHI + VIIRS + FIRMS NRT all agree)

RETRACTED:
  Single AHI frame, NOT confirmed in next 2 frames, no LEO confirmation within 6 hours
```

This is transparent, debuggable, and correct. It can be implemented in a day. Bayesian scoring can replace it later if time permits, but the ladder is the MVP.

### On the provisional-to-confirmed alert lifecycle:

**Event states (simplified from original):**

```
PROVISIONAL -> LIKELY -> CONFIRMED -> MONITORING -> CLOSED
     |            |
     +-> RETRACTED +-> RETRACTED
```

- **PROVISIONAL:** First detection. Report immediately with low confidence. Include lat/lon, time, sensor, anomaly magnitude.
- **LIKELY:** Passed persistence or independent confirmation. Upgrade report.
- **CONFIRMED:** LEO sensor confirmation or multiple independent detections. Upgrade report. This is the "real" alert.
- **MONITORING:** Fire confirmed, providing 15-min characterization updates for 12 hours per Rule 9.
- **RETRACTED:** Failed persistence, no confirmation. Mark as retracted in next report. NOT a false positive if we clearly labeled it PROVISIONAL.
- **CLOSED:** 12 hours elapsed or fire extinguished.

**Key insight from the all-teams call:** "Low confidence detections still count if correct." This means PROVISIONAL detections that turn out to be real fires score points. Retractions of false positives are not heavily penalized as long as they were clearly labeled as provisional.

### On the event store:

**Keep it simple. DynamoDB or even SQLite.**

Required fields per event:
- event_id (UUID)
- status (PROVISIONAL/LIKELY/CONFIRMED/MONITORING/RETRACTED/CLOSED)
- first_detection_time (ISO 8601)
- latest_detection_time
- centroid_lat, centroid_lon
- location_uncertainty_m
- detections[] (array of individual sensor detections with provenance)
- confidence_level (LEVEL 1-4)
- reported (boolean -- has this been included in a report?)

Skip:
- Full Bayesian log-odds tracking
- Complex geometry (alpha hulls, perimeters) -- use simple buffer circles
- FRP estimation (decorative at geostationary resolution)
- Rate of spread estimation (unreliable from sparse hotspot centroids)

---

## 4. Ops Realist Assessment

### On judge portal priority (#2): STRONGLY AGREE

The external review is right that the judge portal is THE product. Re-reading the R&R carefully:

- **Rule 4:** "Teams must provide Judges and XPRIZE unrestricted access and visibility to their system... Teams may provide logins, access to portals or websites, or a screen share of the system working."
- **Rule 7:** "Daily reports shall be output in OGC format."
- **Rule 8:** "Teams must provide the most accurate time and location of initial ignition possible."
- **Assumption 8:** "Judges will be using Esri products for the comparative analysis of teams' systems."
- **Clarification from call:** "Judges won't score how well you interface with ESRI, but will score OGC data quality and delivery speed. Real-time judging happens through your own system."

The judges experience our system through TWO interfaces:
1. **Our system/portal** -- real-time viewing during burns
2. **OGC data in ArcGIS** -- comparative analysis across teams

Both must work. Both must look credible. A system that detects fires but cannot show them to judges is worth zero.

**What the judge portal MUST show (Week 1 deliverable):**
- Map of NSW with current fire detections, color-coded by confidence level
- Time of detection, sensor source, confidence tier for each detection
- Clear PROVISIONAL vs CONFIRMED labeling
- Auto-refresh every 60 seconds (or push-based)
- Export to OGC-compliant GeoJSON with one click (or auto-generated)

**What it does NOT need (can add later):**
- Fire perimeter polygons (just use circles/points)
- FRP charts
- Rate of spread arrows
- Historical playback
- Multi-layer map controls

**Technology choice:** Simple web app (Leaflet.js or MapLibre GL JS + a REST API). NOT ArcGIS Online as primary -- ArcGIS is for daily report submission only. Our portal should be self-hosted and fast.

### On OGC export:

The R&R specifies OGC format for daily reports. The simplest compliant format is GeoJSON (OGC standard since 2016). Each fire event becomes a Feature with:

```json
{
  "type": "Feature",
  "geometry": {"type": "Point", "coordinates": [151.2, -33.8]},
  "properties": {
    "event_id": "...",
    "detection_time": "2026-04-10T14:23:00+10:00",
    "confidence": "CONFIRMED",
    "sensor_sources": ["Himawari-9 AHI", "VIIRS NOAA-21"],
    "location_uncertainty_m": 2000,
    "intensity_estimate": "moderate"
  }
}
```

This can be ingested into ArcGIS Online directly. Build the GeoJSON export in Week 1.

### On 22-day feasibility: TIGHT but achievable with revised scope

The revised priority list is buildable because it drops the hardest items (CUSUM, ML, full Bayesian fusion) and focuses on:
1. Data plumbing (Himawari ingestion) -- well-understood, AWS docs exist
2. Simple contextual detection -- algorithm is documented in our domain briefs
3. Rule-based confidence -- trivial logic
4. Web portal -- standard web development
5. OGC export -- GeoJSON is easy

**The critical path is:**
- Week 1: Himawari pipeline + contextual detection + portal + OGC export
- Week 2: DEA/FIRMS ingestion + event store + persistence logic + daily report automation
- Week 3: Testing, tuning thresholds, fixing bugs, CUSUM if time permits
- Week 4: Travel, final testing, competition

This is realistic for a small team working full-time.

### On partnership emails (#6): YES, send them TODAY

The emails cost 2-3 hours total to write and send. The potential upside is significant:
- BoM HimawariRequest: 10-15% chance of 2.5-min cadence (game-changing)
- OroraTech: 10-20% chance of commercial thermal alerts (fills our biggest gap)
- GA/BoM VIIRS: 20-30% chance of faster VIIRS data
- Earth Fire Alliance: Not viable (FireSat not operational)

**Send these emails TODAY:**
1. BoM (satellites@bom.gov.au) -- HimawariRequest Target Area + faster Himawari feed
2. OroraTech sales -- trial/pilot during competition window
3. GA (earth.observation@ga.gov.au) -- faster DEA Hotspots access or raw data feed

**Do NOT send:**
4. Earth Fire Alliance (FireSat not ready)
5. FarEarth/Pinkmatter (Landsat real-time is fantasy at this timeline)
6. CfAT/Viasat (commercial GSaaS adds complexity we cannot absorb)

### On minimum viable product that a judge would find credible:

A judge is a fire management professional. They need to see:
1. **A map showing fire detections in near-real-time.** Points on a map, color-coded red/orange/yellow by confidence. Refreshes automatically.
2. **Clear timestamps.** When was this fire first detected? How long ago?
3. **Sensor attribution.** Which satellite saw this? At what resolution?
4. **Confidence levels that make sense.** PROVISIONAL/LIKELY/CONFIRMED is intuitive. P(fire) = 0.73 is not.
5. **OGC-compliant daily reports.** GeoJSON files they can load into ArcGIS.
6. **Responsiveness.** When a burn is ignited, how quickly does a dot appear on our map?

### What would embarrass us if we shipped it:

1. **A system that detects fires but has no way for judges to see them.** This is the #1 risk if we build detection first and portal last.
2. **A portal that shows zero detections during a live burn.** If our Himawari pipeline is broken and we have no fallback, judges see nothing.
3. **Massive false positive spam.** 50 alerts per day when there are 2-3 actual fires. This destroys credibility.
4. **Reports in non-OGC format.** If judges cannot load our data into ArcGIS, they cannot compare us to other teams.
5. **"Under construction" or TODO placeholders visible to judges.** Ship a simple, complete product rather than a complex, broken one.
6. **No fallback.** If our custom Himawari processing fails, we should be able to fall back to DEA Hotspots + FIRMS immediately. The fallback must be pre-built, not improvised during the competition.

**The MVP fallback system:** Even if our entire custom detection pipeline fails, we should have a system that:
- Polls DEA Hotspots WFS every 5 minutes
- Polls FIRMS API every 5 minutes
- Deduplicates by spatial proximity
- Displays on the portal
- Exports to GeoJSON

This is buildable in 1-2 days and should be built FIRST as insurance.

---

## 5. Points of Agreement Across All Four Assessments

1. **Alert policy must change.** All four perspectives agree: holding first detections for 20-30 minutes is wrong for a speed competition. Report provisional alerts immediately.

2. **Judge portal is Week 1, not Week 4.** Without a way for judges to see our detections, nothing else matters.

3. **CUSUM is not the centerpiece.** It is a useful supplementary technique but not the competitive differentiator we claimed. Demote to optional.

4. **Scope must be cut aggressively.** Focus on Himawari + DEA Hotspots + FIRMS. Everything else is stretch.

5. **Send partnership emails today.** Low cost, potential high reward. But design nothing around their success.

6. **Build the fallback first.** DEA Hotspots + FIRMS polling is our insurance policy. Build it before the custom pipeline.

7. **Rule-based confidence over Bayesian.** Simpler, debuggable, buildable in a day.

8. **Fix the double-counting problem.** One observation = one evidence contribution, regardless of how many pipelines process it.

---

## 6. Points of Disagreement and Resolution

### Disagreement 1: Keep or drop GK-2A?

- **External review says:** Drop it (too many sensors).
- **Sensor strategist says:** Keep it -- trivial incremental cost once Himawari works, and it provides genuinely independent confirmation.

**Resolution:** KEEP GK-2A, but only as a cross-check feed. Do NOT build a separate GK-2A detection pipeline. Instead, ingest GK-2A fire detections from FIRMS (if available) or run the same contextual algorithm on GK-2A data only after the Himawari pipeline is stable (Week 2+). It is a Week 2 item, not Week 1.

### Disagreement 2: How aggressive with provisional alerts?

- **Detection architect says:** Report ALL contextual detections immediately, even single-frame moderate anomalies.
- **Ops realist says:** Be cautious -- massive false positive spam destroys credibility with judges.

**Resolution:** Tiered approach:
- **Saturated pixels / extreme anomalies (BT > 360K night, BT > 400K):** Report immediately as HIGH confidence. Near-zero FP risk.
- **Strong contextual detections (BTD > mean + 5*sigma):** Report immediately as PROVISIONAL. Low FP risk.
- **Marginal contextual detections (BTD > mean + 3.5*sigma but < 5*sigma):** Hold for one additional frame (10 min). If persists, report as PROVISIONAL.

This balances speed against credibility. The 10-min hold for marginal detections is a compromise.

### Disagreement 3: Characterization claims (perimeter, ROS, intensity)

- **External review says:** "Perimeter" and "ROS" from sparse hotspot centroids is decorative, not operational.
- **Fusion specialist says:** Skip complex characterization entirely for MVP.
- **Ops realist says:** Judges want "fire behavior including perimeter, direction and rate of spread, and intensity" per Assumption 1 in the R&R.

**Resolution:** Provide SIMPLE characterization that is honest about its limitations:
- **Location:** Point with uncertainty circle (not a perimeter polygon)
- **Size estimate:** "Detection covers approximately X km2 based on number of hot pixels" (not a precise area)
- **Intensity:** Qualitative (low/moderate/high) based on BT anomaly magnitude
- **Direction/ROS:** Only if we have 3+ sequential detections showing centroid movement. Otherwise: "insufficient data for spread estimate."

Label everything clearly. "Estimated" not "measured." Judges will respect honesty more than overconfident claims.

---

## 7. Final Recommended Priority List

### Priority 1: Build the fallback system (Days 1-2)
- DEA Hotspots WFS polling (every 5 min)
- FIRMS API polling (every 5 min, requires MAP_KEY)
- Simple deduplication by spatial proximity (2 km grid)
- GeoJSON export
- Basic web portal (Leaflet.js map, auto-refresh, shows detections as colored dots)
- **This is our insurance policy. If everything else fails, this works.**

### Priority 2: Himawari raw pipeline + contextual detection (Days 2-7)
- AWS account in us-east-1
- Subscribe to Himawari SNS notifications
- SQS queue with filter for B07/B14, NSW segments
- HSD decode + BT conversion (use satpy or custom decoder)
- Static masks (land/water, industrial sites)
- Sun glint rejection
- Contextual threshold fire detection (adapted GOES FDC for AHI)
- Cloud mask (Tier 1: simple BT thresholds)
- Alert generation with lat/lon, confidence, timestamp

### Priority 3: Event store + confidence ladder + portal integration (Days 5-10)
- Event store (DynamoDB or SQLite)
- Provenance tracking (which satellite, which pipeline, observation time)
- Rule-based confidence ladder (PROVISIONAL -> LIKELY -> CONFIRMED)
- Portal shows custom Himawari detections alongside DEA/FIRMS fallback
- Retraction logic for single-frame transients
- OGC GeoJSON export with proper schema

### Priority 4: DEA/FIRMS integration as confirmation layer (Days 7-12)
- Cross-match DEA Hotspots detections with our Himawari events
- Cross-match FIRMS detections (VIIRS, MODIS, Landsat)
- Upgrade confidence on cross-sensor match
- De-duplicate same-observation evidence (fix double-counting)
- GK-2A cross-check (if Himawari pipeline is stable)

### Priority 5: Daily report automation (Days 10-14)
- Generate daily report per XPRIZE template (due 20:00 AEST daily)
- Include all detected fires, sensor sources, confidence levels
- GeoJSON/GeoPackage attachment for ArcGIS ingestion
- Automate as much as possible (template fill + manual review)

### Priority 6: Send partnership emails (Day 1)
- BoM: HimawariRequest Target Area + faster Himawari internal feed
- OroraTech: trial/pilot during competition window
- GA: faster DEA Hotspots access or priority API
- Time cost: 2-3 hours. Do it today.

### Priority 7: CONOPS + Finals Application (Days 7-13, due March 31)
- CONOPS document
- System diagram
- AI/ML Plan (describe contextual detection + planned ML; TRL-7 claim is for the full pipeline)
- Quad chart
- Personnel list
- ROM cost

### Priority 8 (stretch): ML classifier (Week 3 if time)
- Lightweight CNN on AHI fire candidates
- Train on FIRMS-labeled fire/non-fire patches
- Reduces false positives by ~80%
- Only implement if FP rate is concerning after Week 2 testing

### Priority 9 (stretch): CUSUM temporal detection (Week 3 if time)
- Kalman filter + CUSUM as shadow layer
- Run in parallel with contextual detection
- Log detections for analysis but do not alert unless confirmed by contextual
- Pre-initialize from 2 weeks of Himawari archive before competition

---

## 8. Week 1 Checklist (March 18-24)

### Day 1 (Today, March 18)
- [ ] Send partnership emails: BoM, OroraTech, GA (3 emails, 2-3 hours)
- [ ] Set up AWS account in us-east-1 (if not already done)
- [ ] Register for FIRMS MAP_KEY (if not already done)
- [ ] Start DEA Hotspots WFS polling client (Python script, ~2 hours)
- [ ] Start FIRMS API polling client (Python script, ~2 hours)

### Days 2-3 (March 19-20)
- [ ] Complete fallback system: DEA + FIRMS -> deduplication -> GeoJSON export
- [ ] Deploy basic web portal (Leaflet.js map of NSW, shows DEA/FIRMS detections)
- [ ] Subscribe to Himawari SNS topic (NewHimawariNineObject)
- [ ] Set up SQS queue with message filtering for fire-relevant bands
- [ ] Benchmark Himawari HSD decode speed (satpy vs custom)

### Days 4-5 (March 21-22)
- [ ] Implement HSD decode + BT conversion for B07/B14 (NSW segments only)
- [ ] Implement Tier 1 cloud mask
- [ ] Implement static masks (land/water, from pre-computed shapefiles)
- [ ] Implement sun glint rejection

### Days 6-7 (March 23-24)
- [ ] Implement contextual threshold fire detection on AHI
- [ ] Test end-to-end: SNS notification -> SQS -> decode -> detect -> alert
- [ ] Measure actual Himawari AWS NODD latency (critical question)
- [ ] Integrate custom Himawari detections into web portal
- [ ] Begin event store implementation

### Ongoing (all week)
- [ ] Monitor DEA Hotspots + FIRMS polling for reliability
- [ ] Collect sample Himawari data for threshold tuning
- [ ] Begin drafting CONOPS for Finals Application (due March 31)
- [ ] Track responses from partnership emails
- [ ] Over-declare ALL potential EO sources in CONOPS (Himawari, GK-2A, FY-4B, VIIRS, MODIS, Sentinel-2/3, Landsat, ECOSTRESS, OroraTech, FIRMS, DEA Hotspots)

### Week 1 Exit Criteria
By end of March 24, we should have:
1. A working fallback system (DEA + FIRMS on a map)
2. Himawari data flowing through our pipeline (even if detection is incomplete)
3. Measured Himawari latency from AWS NODD
4. Partnership emails sent
5. CONOPS draft started
6. A portal that a judge could look at and understand

---

## 9. Key Risks in the Revised Plan

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | Himawari custom pipeline not ready by Week 2 | MODERATE | HIGH | Fallback system (DEA + FIRMS) provides basic capability |
| 2 | False positive rate > 5% with immediate provisional alerts | MODERATE | HIGH | Tiered alerting (only extreme anomalies immediate), emergency threshold raising |
| 3 | Portal not usable by judges | LOW | CRITICAL | Build portal FIRST (Priority 1-2), iterate daily |
| 4 | AWS NODD Himawari latency > 15 min | MODERATE | MODERATE | Switch to JAXA P-Tree; use DEA Hotspots as primary |
| 5 | OGC export format incompatible with ArcGIS | LOW | HIGH | Test GeoJSON import into ArcGIS Online before competition |
| 6 | No partnership emails succeed | HIGH | MODERATE | System works entirely on public data; partnerships are pure upside |
| 7 | CONOPS deadline missed (March 31) | LOW | CRITICAL | Start drafting in parallel with engineering work |
| 8 | Too few engineering hours for scope | HIGH | HIGH | The revised scope is the minimum; cut ML and CUSUM first |
