# Red Team Analysis: Stress-Testing the System

**Updated:** 2026-03-18 (revised priorities, incorporates external review findings)

## 1. External Review Findings (Validated Risks)

An external review (ChatGPT Pro, 2026-03-17) stress-tested our v1.0 plan and identified critical issues. These have been validated by four internal specialist assessments and incorporated into the revised plan.

### VALIDATED: CUSUM Was Overclaimed

**Finding:** CUSUM was positioned as our "competitive edge" but detection delays of 2-11 hours for 200-500 m2 fires mean it adds nothing for fires detectable in a single frame and takes too long for fires that VIIRS would catch anyway.

**Status:** ADDRESSED. CUSUM demoted to optional Week 3 stretch goal. Competitive positioning reframed around system robustness, speed-to-provisional-alert, and false positive control.

### VALIDATED: Bayesian Double-Counting

**Finding:** The same Himawari observation processed by our pipeline (+4.0 LLR), FIRMS (+3.0 LLR), and DEA Hotspots (+2.5 LLR) was summed as independent evidence, inflating confidence.

**Status:** ADDRESSED. Bayesian log-odds replaced with rule-based confidence ladder. Provenance tracking ensures one observation = one evidence contribution. See `fusion-confidence.md`.

### VALIDATED: No Fallback System

**Finding:** If the custom Himawari pipeline failed during competition, there was no backup. A system that detects fires but cannot show them to judges is worth zero.

**Status:** ADDRESSED. Fallback system (DEA Hotspots + FIRMS polling -> portal) is now Priority 1, built FIRST before any custom detection code. This is our insurance policy.

### VALIDATED: Judge Portal Deprioritized

**Finding:** The portal was scheduled for Week 3-4. The portal IS the product -- judges experience our system through it.

**Status:** ADDRESSED. Portal is now Priority 1-2, built in the first 2-3 days alongside the fallback system.

### VALIDATED: Overclaiming on Characterization

**Finding:** "Perimeter" and "rate of spread" from sparse geostationary hotspot centroids is decorative, not operational.

**Status:** ADDRESSED. Characterization now uses honest uncertainty: points with circles (not perimeter polygons), qualitative intensity (not quantitative FRP), direction/ROS only with 3+ sequential detections.

### VALIDATED: Scope Too Broad

**Finding:** Eight sensor tiers with 22 days is not realistic.

**Status:** ADDRESSED. Core stack cut to Himawari + DEA Hotspots + FIRMS. GK-2A is Week 2 cross-check. All other sensors dropped from active processing (consumed via FIRMS point products only).

---

## 2. Single Points of Failure

### CRITICAL: Himawari-9 Data Feed

**Risk:** Our continuous monitoring depends on Himawari-9. If Himawari data stops flowing, we lose our trigger layer.

**Evidence:** Himawari-9 experienced an anomaly in October 2025, was offline for ~1 month. April is shortly after the March equinox -- eclipse season maintenance.

**Mitigation (STRENGTHENED in revised plan):**
- **PRIMARY MITIGATION: Fallback system.** DEA Hotspots + FIRMS polling continues to detect fires independently of our custom Himawari processing. If Himawari goes down, the fallback system keeps the portal populated.
- GK-2A (128.2E) as hot standby: same 10-min cadence, AWS NODD mirror, independent operator (KMA)
- JAXA P-Tree as alternative Himawari data path (different distribution channel)
- DEA Hotspots itself ingests Himawari -- GA's Himawari processing is independent of ours

**Residual risk:** LOW. The fallback system ensures judges always see detections, even if custom processing is down.

### CRITICAL: AWS us-east-1 Availability

**Risk:** NOAA NODD data lives in us-east-1. Our processing is co-located. A regional outage kills our geostationary pipeline.

**Mitigation:**
- JAXA P-Tree (Japan-hosted) as fallback for Himawari data
- DEA Hotspots (Australian-hosted) as fallback for VIIRS/MODIS products
- FIRMS API (NASA-hosted) as fallback for global fire detections
- The fallback system (DEA + FIRMS polling) does not depend on AWS us-east-1 if hosted elsewhere

**Residual risk:** LOW-MODERATE. Multiple non-AWS data paths exist, but they add 15-30 minutes of latency.

### HIGH: Portal Availability

**Risk:** If the judge portal goes down during a live burn, judges see nothing.

**Mitigation:**
- Simple static-file-based portal (Leaflet.js + REST API) with minimal failure modes
- Deploy on reliable hosting (AWS or similar)
- Test extensively before competition
- Pre-build a static GeoJSON export that can be manually emailed to judges as last resort

**Residual risk:** LOW with proper testing and monitoring.

### MODERATE: Internet Connectivity During Competition

**Risk:** We need internet to receive satellite data and submit results.

**Mitigation:**
- Primary: venue WiFi / wired connection
- Backup: 4G/5G cellular hotspot
- Backup 2: Starlink terminal (if available)
- Processing runs in AWS, not locally -- we only need bandwidth for alerts and report submission

**Residual risk:** LOW. Multiple connectivity options exist in urban/suburban NSW.

---

## 3. Latency Scenarios

### What If Himawari Latency Is 15 Minutes Instead of 7?

**Impact:** Our geostationary detection latency increases from ~10 minutes to ~18 minutes from observation. For immediate provisional alerts on strong anomalies, we are ~18 minutes from observation.

**Assessment:** MANAGEABLE. Even at 15-minute latency, we get alerts faster than DEA Hotspots (~17 min for VIIRS). Himawari's primary value is continuous monitoring (every 10 min), not absolute speed.

### What If Himawari Latency Is 30 Minutes?

**Impact:** Custom AHI processing provides no advantage over consuming FIRMS Himawari detections (~30 min).

**Assessment:** CONCERNING but survivable. Fallback: switch to FIRMS Himawari fire detections as primary geostationary source. We lose custom detection but maintain continuous monitoring.

**Root cause investigation:** If we observe 30-min latency during testing, check whether the bottleneck is JMA processing, JMA->NOAA relay, or NOAA->S3 write. If it is the NOAA relay, try JAXA P-Tree directly.

### What If All Partnerships Fail?

**Impact:** We operate with public data only. No 2.5-min HimawariRequest cadence, no OroraTech alerts, no faster DEA Hotspots.

**Assessment:** This is the baseline scenario the system is designed for. Partnerships are pure upside. System works entirely on public data.

**What we lose:** Any chance of 1-minute-from-overpass scoring, commercial thermal coverage for small fires, faster VIIRS data.

**What we keep:** Custom Himawari detection (7-15 min), DEA Hotspots VIIRS (17 min), FIRMS safety net, fallback system, judge portal.

---

## 4. Cloud Cover Scenarios

### What If Cloud Cover Is 80% During Competition?

April in NSW is autumn with variable weather. Cloud fraction of 40-60% is typical, but extended cloudy periods are possible.

**Impact at 80% cloud cover:**
- Himawari thermal detection blocked for 80% of pixels. Only 20% of NSW observable.
- VIIRS detection rate drops proportionally
- Cloud edges become a major false positive risk
- All satellite-based detection is severely degraded

**Mitigations:**
- Increase cloud mask buffer from 2 pixels to 3-4 pixels to reduce cloud-edge FPs
- Accept that "good days" and "bad days" will occur -- maximize performance during clear periods

**Honest assessment:** At 80% cloud cover, no space-based EO system performs well. This limitation affects ALL teams equally. Our best strategy is minimizing false positives during cloudy periods.

### What About Prescribed Burns Under Clear Skies?

XPRIZE will likely coordinate burns with weather to ensure satellite observability. Expect most burns timed for relatively clear conditions.

---

## 5. False Positive Rate Exceedance

### What If FP Rate > 5%?

**Increased risk from revised plan:** The move to immediate provisional alerts increases FP exposure relative to the v1.0 plan, which held detections for 20-30 minutes.

**Mitigated by:** Tiered alerting (only extreme anomalies are truly immediate; marginal detections get a 10-min hold). The 4-layer filtering pipeline still runs before any alert is issued.

**Emergency fallback protocol (escalating):**

1. **Immediate (within 1 hour):** Raise BTD threshold by 5 K for all sensors
2. **Within 2 hours:** Night-only geostationary alerting during the problematic period
3. **Within 4 hours:** Require 3/3 frame persistence instead of 2/3
4. **Within 6 hours:** Require VIIRS confirmation before reporting any Himawari-only detection (delays reports by hours but near-zero FP rate)
5. **Last resort:** Manual review of every alert

### Root Causes to Investigate If FP Rate Is High

- Hot bare ground in western NSW (check land cover mask coverage)
- Industrial sites not in our static mask (compare against current facilities databases)
- Sun glint geometry unique to April solar angles at NSW latitudes
- Cloud-edge artifacts during partly cloudy conditions
- Agricultural burning (these ARE real fires -- verify scoring rules)

---

## 6. Competition Scenarios

### Scenario A: Small Fire (<100 m2), Clear Sky, Between VIIRS Passes

A small burn is ignited at 14:00 AEST. VIIRS just passed. Next VIIRS is ~01:00 (11 hours).

**Our response:** At 100 m2, the fire is below Himawari's single-frame detection threshold. We must wait for either fire growth to >1,000 m2, or next VIIRS pass at ~01:00.

**Assessment:** This is our weakest scenario. A team with OroraTech could detect this in <30 minutes. We cannot match commercial thermal cubesats for small fires between VIIRS passes.

**Revised plan impact:** No worse than v1.0 for this scenario. CUSUM (even if implemented as stretch goal) would take 6-28 hours for 100 m2 -- too slow to help.

### Scenario B: Nighttime Fire Ignition

**Our advantage:** Nighttime fire detection is EASIER than daytime:
- No sun glint
- Lower background temperatures (higher contrast)
- Himawari nighttime BT_3.9 is purely thermal
- VIIRS night passes have higher sensitivity

The immediate alerting policy works particularly well at night because the FP risk is much lower.

### Scenario C: Multiple Simultaneous Fires

**Risk:** If 5+ fires ignite simultaneously, our event tracking system handles this natively (independent events by location).

**Revised plan impact:** Simpler event store (no Bayesian updates per event) is actually faster to process for multiple simultaneous events.

### Scenario D: System Failure During Live Burn

**Our advantage (NEW in revised plan):** The fallback system (DEA + FIRMS polling) runs independently of the custom Himawari pipeline. If our detection code crashes, the portal still shows DEA/FIRMS detections within minutes. Judges still see something.

This was the #1 risk in v1.0 (no fallback). It is now mitigated.

---

## 7. XPRIZE Rules Risks

### Rule 1: "1 Minute to Identify All Fires"

**Our position:** We cannot hit 1-minute-from-overpass for any data path (Himawari: 7-15 min, DEA: 17 min). If this is a hard cutoff, we score zero on this metric. If it is graded (faster = higher score), our 7-15 minute Himawari latency earns partial credit.

**Recommendation:** Optimize for fastest possible detection within our data constraints. Do not sacrifice accuracy for marginal speed gains.

### Rule 3: Declaration of EO Sources

**Risk:** Under-declaring data sources risks disqualification.

**Recommendation:** In the CONOPS submission (due March 31), over-declare every potential source: Himawari, GK-2A, FY-4B, VIIRS, MODIS, Sentinel-2/3, Landsat, ECOSTRESS, OroraTech, FIRMS, DEA Hotspots. Over-declaring is safe.

### Rule 7: OGC Format Requirement

**Risk:** If GeoJSON export is incompatible with ArcGIS, judges cannot compare us to other teams.

**Mitigation:** Build GeoJSON export in Week 1. Test ArcGIS Online import before competition.

### Rule 8: "Detect All Fires Within the Target Area"

**Our position:** Report ALL fires detected. Prescribed burns are real fires -- report them. Any correct detection helps score.

---

## 8. Competitive Analysis (Updated)

### What Other Teams Likely Have That We Do Not

**Teams with commercial satellite data (OroraTech, Planet):**
- <10 minute revisit thermal imagery at ~200 m resolution
- Much better small-fire detection between VIIRS passes
- We cannot match this with public data alone

**Teams with proprietary ground station access:**
- Process VIIRS data within 1-2 minutes of overpass
- Genuine 1-minute-from-overpass scoring
- We can only match this with a partnership we haven't secured

**Teams with Australian fire agency connections:**
- Real-time prescribed burn notifications
- BoM internal Himawari feeds (potentially faster)
- Our NAU university status is an asset but not an Australian institution

### Our Competitive Position (Revised)

**Previous strongest position:** Temporal integration (CUSUM) and multi-sensor Bayesian fusion.

**Revised strongest position:**
1. **System robustness.** Fallback system ensures we always show detections. Most teams will have a single pipeline with no backup.
2. **False positive control.** 4-layer filtering pipeline + tiered alerting. Many teams will struggle with the <5% FP requirement.
3. **Continuous characterization.** Himawari gives us fire updates every 10 minutes, 24/7.
4. **Transparent confidence reporting.** PROVISIONAL/LIKELY/CONFIRMED is intuitive and honest. Judges respect credibility.
5. **Speed to first alert.** Immediate provisional alerts on strong anomalies (7-15 min from observation). Faster than waiting for persistence.

**What we explicitly do NOT claim:**
- Best small-fire detection (commercial cubesats beat us)
- Fastest LEO detection (direct broadcast teams beat us)
- Most algorithmically sophisticated (CUSUM/ML are stretch goals, may not ship)

---

## 9. Risk Register (Updated)

| # | Risk | Likelihood | Impact | Mitigation | Status |
|---|------|-----------|--------|-----------|--------|
| 1 | Himawari custom pipeline not ready by Week 2 | MODERATE | HIGH | Fallback system (DEA + FIRMS) provides basic capability from Day 1 | NEW - primary mitigation |
| 2 | False positive rate > 5% with immediate provisional alerts | MODERATE | HIGH | Tiered alerting + 4-layer filtering + emergency protocols | UPDATED - tiered approach |
| 3 | Portal not usable by judges | LOW | CRITICAL | Build portal FIRST (Priority 1), iterate daily | UPDATED - elevated priority |
| 4 | AWS NODD Himawari latency > 15 min | MODERATE | MODERATE | Switch to JAXA P-Tree; DEA Hotspots as primary geostationary | UNCHANGED |
| 5 | OGC export format incompatible with ArcGIS | LOW | HIGH | Test GeoJSON import into ArcGIS Online before competition | UNCHANGED |
| 6 | No partnership emails succeed | HIGH | MODERATE | System works entirely on public data; partnerships are pure upside | UNCHANGED |
| 7 | CONOPS deadline missed (March 31) | LOW | CRITICAL | Start drafting in parallel with engineering work | NEW |
| 8 | Too few engineering hours for scope | HIGH | HIGH | Revised scope is the minimum; ML and CUSUM explicitly stretch goals | UPDATED - scope cut |
| 9 | Cloud cover > 70% during competition | MODERATE | HIGH | Cannot mitigate (physics); same for all teams | UNCHANGED |
| 10 | Competitor has commercial satellite data | HIGH | MODERATE | Cannot match; differentiate on robustness and FP control | UPDATED - revised competitive positioning |
| 11 | Double-counting inflates confidence | LOW | MODERATE | ADDRESSED: provenance tracking, one obs = one evidence contribution | NEW - resolved |
| 12 | Overclaiming on characterization | LOW | MODERATE | ADDRESSED: honest uncertainty, no decorative perimeters/ROS | NEW - resolved |
| 13 | Fallback system (DEA + FIRMS) has outage | LOW | HIGH | Multiple independent data paths; manual GeoJSON submission as last resort | NEW |

### Risks Removed or Downgraded from v1.0

| Original Risk | Change | Reason |
|--------------|--------|--------|
| CUSUM state lost (DB failure) | REMOVED | CUSUM is now a stretch goal, not core |
| Small fires (<500 m2) missed by Himawari | DOWNGRADED to accepted limitation | CUSUM was the mitigation but is now stretch; this is an inherent public-data limitation |
| Timeline too aggressive (23 days) | DOWNGRADED | Revised scope is more realistic; 22 days for MVP is tight but achievable |

---

## 10. Minimum Viable System That Would Not Embarrass Us

A judge is a fire management professional. They need to see:

1. **A map showing fire detections in near-real-time.** Points on a map, color-coded by confidence. Auto-refresh.
2. **Clear timestamps.** When was this fire first detected? How long ago?
3. **Sensor attribution.** Which satellite saw this?
4. **Confidence levels that make sense.** PROVISIONAL/LIKELY/CONFIRMED is intuitive.
5. **OGC-compliant daily reports.** GeoJSON files they can load into ArcGIS.
6. **Responsiveness.** When a burn is ignited, a dot appears on our map within minutes.

### What Would Embarrass Us

1. A system with no detections visible to judges during a live burn (MITIGATED: fallback system)
2. Massive false positive spam (MITIGATED: tiered alerting + filtering)
3. Reports in non-OGC format (MITIGATED: GeoJSON from Week 1)
4. Overclaiming capabilities we cannot deliver (MITIGATED: honest characterization)
5. "Under construction" placeholders visible to judges (MITIGATED: simple, complete product)
6. No fallback when primary system fails (MITIGATED: DEA + FIRMS fallback built first)
