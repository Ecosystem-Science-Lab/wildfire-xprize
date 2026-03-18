# Red Team Analysis: Stress-Testing the System

## 1. Single Points of Failure

### CRITICAL: Himawari-9 Data Feed

**Risk:** Our continuous monitoring depends entirely on Himawari-9. If Himawari data stops flowing (JMA processing failure, AWS NODD outage, network issue), we lose our trigger layer entirely.

**Evidence:** Himawari-9 experienced an anomaly in October 2025, was offline for ~1 month, and was restored in November 2025. This proves it can fail during critical periods. Additionally, April is shortly after the March equinox -- Himawari undergoes eclipse season maintenance around equinoxes.

**Mitigation:**
- GK-2A (128.2E) as hot standby: same 10-min cadence, AWS NODD mirror, independent operator (KMA)
- FY-4B (123.5E) as tertiary: 15-min cadence
- JAXA P-Tree as alternative Himawari path (different distribution channel)
- DEA Hotspots already ingests Himawari -- if our custom processing fails, fall back to DEA's processed hotspots

**Residual risk:** MODERATE. GK-2A provides genuine redundancy. But if the NODD platform itself is down (AWS us-east-1 outage), both Himawari and GK-2A mirrors fail simultaneously.

### CRITICAL: AWS us-east-1 Availability

**Risk:** All NOAA NODD data lives in us-east-1. Our processing infrastructure is co-located there. A regional AWS outage kills our entire geostationary pipeline.

**Mitigation:**
- JAXA P-Tree (Japan-hosted) as fallback for Himawari data
- DEA Hotspots (Australian-hosted) as fallback for VIIRS/MODIS products
- FIRMS API (NASA-hosted) as fallback for global fire detections
- Consider multi-region deployment (us-west-2 as standby) with cross-region S3 replication for our state data

**Residual risk:** LOW-MODERATE. Multiple non-AWS data paths exist, but they add 15-30 minutes of latency.

### HIGH: Internet Connectivity During Competition

**Risk:** We need internet to receive satellite data and submit results. If connectivity at the competition venue (NSW RFS HQ or field sites) fails, we cannot operate.

**Mitigation:**
- Primary: venue WiFi / wired connection
- Backup: 4G/5G cellular hotspot
- Backup 2: Starlink terminal (if available)
- Our processing runs in AWS, not locally -- we only need enough bandwidth to receive alerts and submit reports

**Residual risk:** LOW. Multiple connectivity options exist in urban/suburban NSW.

### HIGH: CUSUM State Initialization

**Risk:** The Kalman filter + CUSUM temporal detection requires 24-48 hours of clear-sky observations to converge. If we lose our state data (database failure, redeployment), we lose our temporal detection capability and must wait 1-2 days to rebuild it.

**Mitigation:**
- Pre-initialize Kalman states from 2-4 weeks of Himawari archive data before competition starts
- Persist CUSUM state to durable storage (DynamoDB or S3) every 10 minutes
- Backup state snapshots every 6 hours
- If state is lost, fall back to contextual-only detection (no temporal integration) -- still functional but less sensitive

**Residual risk:** LOW with proper preparation. HIGH if we neglect pre-initialization.

---

## 2. Latency Scenarios

### What If Himawari Latency Is 15 Minutes Instead of 7?

**Impact:** Our geostationary detection latency increases from ~10 minutes to ~18 minutes from observation. This pushes us further from the 1-minute-from-overpass target for geostationary scans (which we likely cannot hit anyway). For the 10-minute characterization metric, we may barely make it -- 15 min data latency + 7 sec processing = ~15 min total, exceeding the 10-min target from observation but potentially within 10 min from the previous characterization update.

**Assessment:** MANAGEABLE. Himawari's primary value is continuous monitoring and characterization updates, not 1-minute detection. Even at 15-minute latency, we get characterization updates every 10 minutes (each one 15 minutes old). The judges likely understand that geostationary data has inherent latency.

### What If Himawari Latency Is 30 Minutes?

**Impact:** This would make Himawari worse than FIRMS geostationary fire products (~30 min). Our entire custom AHI processing pipeline would provide no advantage over simply consuming FIRMS Himawari detections.

**Assessment:** CONCERNING but survivable. Fallback: switch to FIRMS Himawari fire detections as primary geostationary source. We lose the ability to run custom algorithms (including CUSUM temporal detection) on raw data, but maintain continuous monitoring.

**Root cause investigation:** If we observe 30-min latency during testing, check whether the bottleneck is JMA processing, JMA->NOAA relay, or NOAA->S3 write. If it is the NOAA relay, try JAXA P-Tree directly (bypasses NOAA).

### What If VIIRS Direct Broadcast Partnership Falls Through?

**Impact:** We lose the 5-15 minute VIIRS path. Our fastest VIIRS data becomes DEA Hotspots (~17 min) or FIRMS NRT (up to 3 hours). We definitely cannot hit 1-minute-from-overpass for any VIIRS pass.

**Assessment:** This is likely our baseline scenario. Direct broadcast partnerships are aspirational. The system must work without them.

**Mitigation:** DEA Hotspots at ~17 minutes is our realistic VIIRS path. Design the scoring strategy around 17-minute VIIRS latency, not 5-minute direct broadcast.

---

## 3. Cloud Cover Scenarios

### What If Cloud Cover Is 80% During Competition?

April in NSW is autumn with variable weather. Cloud fraction of 40-60% is typical, but extended cloudy periods are possible, especially during East Coast Lows.

**Impact at 80% cloud cover:**
- Himawari thermal detection is blocked for 80% of pixels. Only 20% of NSW is observable at any given time.
- VIIRS detection rate drops proportionally -- fires under cloud are invisible.
- Cloud edges become a major false positive risk (warm edge + cold cloud = high BTD).
- CUSUM temporal detection is severely degraded: most pixel time series have large gaps, so accumulated evidence decays.
- Fire detection becomes almost entirely dependent on the 20% clear-sky windows. If a fire is in a clear area, we detect it normally. If under cloud, no satellite system can detect it.

**Mitigations:**
- SWIR bands (1.6-2.2 um) on Sentinel-2 and Landsat penetrate thin cloud better than TIR. But thick cloud blocks everything.
- Smoke detection via TROPOMI aerosol index or OMPS can identify fires under thin cloud/smoke, but with very coarse resolution (5+ km) and hours of latency.
- SAR (Sentinel-1) penetrates cloud but cannot detect active fire -- only useful for burn scar mapping days later.
- Increase cloud mask buffer from 2 pixels to 3-4 pixels to reduce cloud-edge false positives.
- Accept that the competition window may have "good days" and "bad days" -- focus resources on maximizing performance during clear periods.

**Honest assessment:** At 80% cloud cover, no space-based EO system performs well. This is a fundamental limitation that ALL teams face equally. Our best strategy is to minimize false positives (which increase with cloud cover) and maximize detections during clear windows.

### What About Prescribed Burns Under Clear Skies?

XPRIZE will likely coordinate burns with weather to ensure satellite observability. The burns are their product too -- they want teams to have a fair chance. Expect that most burns will be timed for relatively clear conditions.

---

## 4. Partnership Failure Scenarios

### Scenario: Only Public Cloud-Mirror Data Available

If ALL partnerships fail (no GA, no BoM, no FarEarth, no OroraTech), we operate with:

| Source | Access | Latency | Status |
|--------|--------|---------|--------|
| Himawari-9 | AWS NODD (public) | 7-15 min | Available NOW |
| GK-2A | AWS NODD (public) | Similar | Available NOW |
| VIIRS | FIRMS NRT API (public) | Up to 3 hours | Available NOW |
| MODIS | FIRMS NRT API (public) | Up to 3 hours | Available NOW |
| Landsat | USGS RT (public) | 4-6 hours | Available NOW |
| Sentinel-2 | Copernicus (public) | 100 min - 3 hours | Available NOW |
| DEA Hotspots | WFS (public, no registration) | ~17 min | Available NOW |

**Assessment:** This is still a viable system. We have:
- Continuous geostationary monitoring via AWS NODD (our Himawari pipeline)
- ~17-minute VIIRS/MODIS data via DEA Hotspots
- Hours-latency high-resolution data via Copernicus/USGS

**What we lose:**
- 1-minute-from-overpass scoring for LEO passes (can't hit it at 17+ min latency)
- Sub-5-minute VIIRS data
- Real-time Landsat detection

**Key point:** The no-partnership system still detects fires. It just can't score on the 1-minute metric for LEO overpasses. Our competitive edge shifts entirely to:
1. Best-in-class geostationary detection (Himawari custom processing)
2. Temporal integration (CUSUM) detecting smaller fires than single-frame approaches
3. Low false positive rate (multi-layer filtering)
4. Superior characterization (continuous updates via Himawari)

---

## 5. False Positive Rate Exceedance

### What If FP Rate > 5%?

**Scenario:** During the competition, we report 50 fire detections, and 4+ are false positives (8% FP rate).

**Emergency fallback protocol (escalating):**

1. **Immediate (within 1 hour):** Raise BTD threshold by 5 K for all sensors. This reduces sensitivity but cuts FPs.

2. **Within 2 hours:** Switch to night-only geostationary alerting during the problematic period. Night detection has near-zero sun glint and lower background variability.

3. **Within 4 hours:** Require 3/3 frame persistence (instead of 2/3). Adds 10 minutes to detection time but eliminates most transient FPs.

4. **Within 6 hours:** Require VIIRS confirmation before reporting any Himawari-only detection. This means Himawari detections are held in queue for up to 12 hours until a VIIRS pass confirms or denies. Dramatically reduces FP rate to near-zero, but delays most reports by hours.

5. **Last resort:** Manual review of every alert before submission. One team member reviews each detection in real-time. Not scalable for >10 fires/day but acceptable for a 2-week competition.

### Root Causes to Investigate If FP Rate Is High

- Hot bare ground in western NSW (use land cover mask)
- Industrial sites not in our static mask (check against current facilities database)
- Sun glint geometry unique to April solar angles at NSW latitudes
- Cloud-edge artifacts during partly cloudy conditions
- Agricultural burning (these ARE real fires -- if the competition counts them, they are not FPs)

---

## 6. XPRIZE Rules We Might Be Misunderstanding

### Rule 1: "1 Minute to Identify All Fires"

**Our interpretation:** 1 minute from satellite overpass, each overpass gets its own clock.

**Risk of misinterpretation:** What if "1 minute" is aspirational language and the actual scoring is a continuous metric -- how quickly do you detect, not a binary pass/fail at 1 minute? The R&R language says "the ambition is to identify all fires within 1 min of ignition, however this will be driven by overpass timings of particular satellites."

**Impact:** If 1-minute is a hard cutoff, we fail it for all Himawari detections and most VIIRS detections. If it is a graded metric (faster detection = higher score), then our 10-15 minute Himawari latency still earns partial credit.

**Recommendation:** Design for the graded interpretation. Optimize for fastest possible detection, but don't sacrifice accuracy for marginal speed gains.

### Rule 8: "Detect All Fires Within the Defined Target Area"

**Our interpretation:** Report every fire we detect, not just competition fires.

**Risk:** If we report agricultural burns, prescribed burns, and industrial heat sources, do these count as false positives even though they ARE heat sources? The R&R says "detect all fires" without specifying wildfire vs. prescribed fire.

**Clarification from 2026-03-17 call:** "Report EVERY fire detected, not just competition fires." This suggests we should report all fires, and any correct detection counts favorably. But incorrect detections (non-fire heat sources) would be false positives.

**Recommendation:** Report all fire detections. Use our industrial site mask to suppress KNOWN non-fire sources. But do NOT suppress agricultural or prescribed burns -- these are real fires and should be reported.

### Rule 3: "Declaration of EO Sources"

**Risk:** We must declare ALL satellite data sources used. If we add a data source mid-competition (e.g., OroraTech), we need to have declared it in advance.

**Recommendation:** In the CONOPS submission (due March 31, 2026), declare every potential data source, even aspirational ones. Include Himawari, GK-2A, FY-4B, VIIRS, MODIS, Sentinel-2, Sentinel-3, Landsat, ECOSTRESS, DEA Hotspots, FIRMS, OroraTech, and anything else we might use. Over-declaring is safe; under-declaring risks disqualification.

### Rule 7: OGC Format Requirement

**Risk:** Our real-time alerts must be convertible to OGC format for ArcGIS integration. If our output format is incompatible with Esri products, we lose points on integration scoring.

**Recommendation:** Implement OGC-compliant output from day one:
- GeoJSON for real-time alerts (OGC-compatible)
- WFS endpoint serving fire detections
- GeoPackage for daily reports
- Test ArcGIS Online ingestion before competition

---

## 7. Competition Scenarios That Would Embarrass Us

### Scenario A: Small Fire (<100 m2), Clear Sky, All Satellites Available

A small prescribed burn is ignited at 14:00 AEST on a clear day. VIIRS (NOAA-21) passes at 13:00, VIIRS (S-NPP) at 13:30. The next VIIRS pass is not until ~01:00 (11 hours away).

**Problem:** At 100 m2, the fire is below Himawari's single-frame detection threshold (~1,000-4,000 m2). VIIRS passed before ignition. We must wait for either:
- The fire to grow to >1,000 m2 (Himawari can detect it) -- could take hours
- CUSUM temporal integration (6-28 hours for 100 m2 fire)
- Next VIIRS pass at ~01:00 AEST (11 hours later)

**Our detection time:** 30 minutes to 11 hours, depending on fire growth rate.

**Other teams:** A team with OroraTech commercial data (~200 m resolution, 30-min revisit) could detect this in <30 minutes. A team with direct broadcast VIIRS from the next overpass could detect it in ~3 hours at the 01:00 pass.

**Assessment:** This is our weakest scenario. Small fires between VIIRS passes rely entirely on either Himawari (insensitive at small size) or CUSUM (slow for very small fires). This is inherent to using public geostationary data at 2 km resolution.

### Scenario B: Nighttime Fire Ignition

**Our advantage:** Nighttime fire detection is actually EASIER than daytime:
- No sun glint (zero daytime false positives)
- Lower background temperatures (higher contrast)
- Himawari nighttime BT_3.9 is purely thermal (no reflected solar)
- VIIRS night passes have higher sensitivity

This is a scenario where we should perform well relative to the field.

### Scenario C: Multiple Simultaneous Fires

**Risk:** If XPRIZE ignites 5+ fires simultaneously across NSW, we need to detect and track all of them. Our event tracking system handles this natively (independent events by location), but our reporting pipeline must scale.

**Mitigation:** Event store is in-memory with O(1) spatial lookups. Reporting templates are pre-built. The bottleneck would be human review if we are doing manual QC.

### Scenario D: Rapid Fire Spread (10+ km/h)

**Risk:** Fast-moving grass fires can spread 10+ km/h in high winds. Within 10 minutes (one Himawari cycle), the fire perimeter could move 1.5 km -- potentially into adjacent Himawari pixels.

**Impact on our system:** The CUSUM temporal detector is pixel-based. A fire that moves out of a pixel will show a brief anomaly then disappear from that pixel's CUSUM. The adjacent pixel's CUSUM will start from zero.

**Mitigation:** The contextual threshold (Pass 1) detects the fire as it enters new pixels. CUSUM is supplementary for small fires; fast-moving fires that are visible to single-frame detection are caught immediately.

---

## 8. Competitive Analysis

### What Would Other Teams Do Differently?

**Teams with commercial satellite data (OroraTech, Planet, etc.):**
- Could have <10 minute revisit thermal imagery at ~200 m resolution
- This gives much better small-fire detection between VIIRS passes
- We cannot match this with public data alone

**Teams with proprietary ground station access:**
- Could process VIIRS data within 1-2 minutes of overpass (FarEarth-style)
- This gives genuine 1-minute-from-overpass scoring
- We can only match this with a partnership we haven't secured

**Teams with large ML research groups:**
- Could train massive models on years of fire data
- Could use foundation models (e.g., Prithvi, ClimaX) for fire detection
- Our lightweight CNN is competitive for inference speed but may underperform on accuracy

**Teams with Australian fire agency connections:**
- Could get real-time prescribed burn notifications
- Could access BoM internal Himawari feeds (potentially faster)
- Our NAU university status is an asset but not an Australian institution

### Our Weakest Competitive Position

1. **Small fire detection between VIIRS passes.** Commercial thermal cubesats (OroraTech) provide ~30-min revisit at ~200 m. We have 10-min revisit at 2 km (Himawari) and ~4-hour revisit at 375 m (VIIRS). The gap is significant.

2. **1-minute-from-overpass scoring.** Without direct broadcast access, we cannot hit this for LEO passes. Teams with ground station partnerships score here and we do not.

3. **On-ground presence in Australia.** Teams based in Australia have easier partnership access and understanding of local conditions.

### Our Strongest Competitive Position

1. **Temporal integration (CUSUM).** If implemented correctly, this is novel for fire detection from geostationary data. No other team is likely doing Kalman filter + CUSUM on Himawari. This could detect 200-500 m2 fires that are invisible to single-frame algorithms.

2. **Multi-sensor fusion at scale.** Our Bayesian log-odds framework combining Himawari, GK-2A, VIIRS, MODIS, and high-res data is comprehensive. Most teams probably focus on 1-2 sensors.

3. **False positive control.** Our 6-layer filtering pipeline is systematic. Many teams will struggle with the <5% FP requirement.

4. **Continuous characterization.** Himawari gives us fire updates every 10 minutes, 24/7. Teams without geostationary processing can only update when LEO passes arrive (every 4-12 hours).

---

## 9. Minimum Viable System

If we had to build the simplest system that still has a chance of winning, what would it be?

### Architecture: "DEA Hotspots + FIRMS + Smart Reporting"

```
DEA Hotspots (WFS) ──┐
                      ├──> Deduplication ──> Confidence ──> OGC Report
FIRMS API (CSV)  ────┘         Engine          Scoring       Generator
```

**Components:**
1. Poll DEA Hotspots WFS every 5 minutes for NSW fire detections
2. Poll FIRMS API every 5 minutes for VIIRS/MODIS/Himawari detections
3. Deduplicate by spatial proximity (2 km grid) and time (30 min window)
4. Assign confidence based on:
   - Number of independent sources detecting the fire
   - FIRMS confidence level
   - DEA Hotspots confidence level
5. Generate OGC-compliant reports (GeoJSON/GeoPackage)
6. Submit to ArcGIS Online

**What this gives us:**
- Continuous fire monitoring (via DEA Hotspots, which ingests Himawari)
- ~17-minute minimum latency (DEA Hotspots)
- VIIRS/MODIS confirmation (via FIRMS, with 3-hour latency)
- Near-zero false positive rate (both sources already filter FPs)
- Minimal infrastructure (no AWS account needed, just API polling)

**What this does NOT give us:**
- 1-minute-from-overpass scoring
- Custom fire detection algorithms
- Temporal integration for small fires
- Advantage over any other team that ingests the same public products

**Honest assessment:** This MVP would place us in the middle of the pack. We would detect most large fires but miss small fires, have slow detection times, and show no innovation. It is a viable backup plan but not a winning strategy.

### Recommended Minimum Viable WINNING System

Add to the MVP:
1. **Custom Himawari AHI processing via AWS NODD** (our contextual threshold + temporal persistence filter). This gives us 7-15 minute fire detection independently of DEA Hotspots.
2. **CUSUM temporal integration** on Himawari data. This is our differentiator.
3. **Bayesian confidence scoring** combining all sources. This keeps FP rate low.

This is achievable with:
- 1 engineer building the AWS pipeline (Lambda + S3)
- 1 engineer building the Himawari fire detection algorithm
- 1 engineer building the CUSUM system
- 1 person handling ArcGIS integration and reporting

Timeline: 3-4 months of focused development, plus 2-3 months of testing.

---

## 10. Summary of Top Risks

| # | Risk | Likelihood | Impact | Mitigation Status |
|---|------|-----------|--------|-------------------|
| 1 | Himawari data feed fails | LOW | HIGH | GK-2A + JAXA P-Tree backup |
| 2 | AWS us-east-1 outage | LOW | HIGH | Multi-path fallback (JAXA, FIRMS, DEA) |
| 3 | Partnerships fail, public data only | HIGH | MODERATE | System works without partnerships |
| 4 | FP rate > 5% | MODERATE | HIGH | 6-layer filtering + emergency protocols |
| 5 | Cloud cover > 70% | MODERATE | HIGH | Cannot mitigate (physics limit); same for all teams |
| 6 | Small fires (<500 m2) missed by Himawari | HIGH | MODERATE | CUSUM temporal detection (partial mitigation) |
| 7 | CUSUM state lost | LOW | MODERATE | Pre-init + persistent storage |
| 8 | OGC/ArcGIS integration failure | LOW | HIGH | Test early, use standard formats |
| 9 | Competition rules misunderstood | LOW | HIGH | Attend all pre-competition calls, over-declare sources |
| 10 | Competitor has commercial satellite data | HIGH | MODERATE | Cannot match; differentiate on algorithms |
