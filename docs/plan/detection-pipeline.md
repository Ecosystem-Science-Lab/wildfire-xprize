# Detection Pipeline Design

**Updated:** 2026-03-18 (revised priorities)

## 1. Pipeline Architecture Overview

The detection pipeline processes satellite data through two core passes. The entire chain must complete within 5 seconds of data arrival for geostationary data. ML classifier and CUSUM temporal detection are optional enhancements for Week 3.

### Minimum Viable Pipeline (Week 1 Deliverable)

```
Data Arrival
    |
    v
[Pass 0: Decode + Subset]     <1 sec
    |
    v
[Pass 1: Contextual Threshold] <2 sec
    |
    v
Alert Policy Decision
    |
    +---> Strong anomaly: IMMEDIATE provisional alert
    +---> Marginal anomaly: HOLD for 10-min confirmation frame
    |
    v
Event Store / Fusion Engine
```

### Optional Enhancements (Week 3 Stretch Goals)

```
After Pass 1 candidates:
    |
    v
[Pass 2: ML Classifier]        <1 sec (candidates only)  -- OPTIONAL
    |
    v
[Pass 3: CUSUM Temporal]       <1 sec (update state)     -- OPTIONAL
    |
    v
Alert / Fusion Engine
```

---

## 2. Pass 0: Preprocessing (Minimum Viable)

### 2.1 What We MUST Do (Hot Path)

For each sensor, the minimum preprocessing to enable fire detection:

**Himawari AHI (every 10 minutes):**
- Decode HSD format -> extract Band 7 (3.9 um) and Band 14 (11.2 um) for NSW segments only (Segments 8-9, covering ~21-47S)
- Convert raw counts to brightness temperature using calibration coefficients embedded in HSD header
- Apply fixed land/water mask (pre-computed, stored in memory)
- NO atmospheric correction needed -- BT differences cancel most atmospheric effects
- NO reprojection -- work in native AHI fixed grid

**VIIRS (via DEA Hotspots / FIRMS):**
- Parse CSV/GeoJSON point products directly (no image processing needed)
- No raw VIIRS processing in core pipeline -- this is a dropped scope item
- If a direct broadcast partnership materializes, raw VIIRS processing becomes relevant, but it is not load-bearing

**Other sensors:**
- Landsat, Sentinel-2, MODIS: consumed only via FIRMS point products in the core pipeline
- No custom processing of raw imagery from these sensors

### 2.2 What We Skip (Key Insight)

Atmospheric correction is NOT needed for fire detection. The fire signal (tens of kelvin BT anomaly) is orders of magnitude larger than atmospheric effects (~0.5-2 K). All operational fire detection algorithms (MOD14, VNP14IMG, ABI FDC) work on uncorrected brightness temperatures. Skipping atmospheric correction saves ~5-10 seconds per scene and eliminates dependency on ancillary data (NWP fields, ozone profiles, etc.).

Orthorectification is not needed for geostationary data (fixed grid). For VIIRS, the built-in geolocation is sufficient (~375 m accuracy).

### 2.3 Cloud Masking Strategy

Cloud masking must be fast but conservative (miss a cloud = false fire detection; mask a fire = missed detection). We use a two-tier approach:

**Tier 1 (fast, ~100 ms per scene):**
- BT_11 < 265 K -> cloud (thick cloud is very cold)
- BT_11 < 285 K AND visible reflectance > 0.4 (daytime) -> cloud
- This catches ~80% of cloud pixels with minimal compute

**Tier 2 (contextual, applied during fire detection):**
- Reject fire candidates within 2 pixels of any Tier 1 cloud pixel
- Use BT_11 spatial standard deviation to detect cloud edges (high variability = edge)
- Accept that ~5-10% of cloud pixels will be missed -- the temporal persistence filter handles transient false alarms from missed cloud edges

For VIIRS, use the operational VIIRS cloud mask (VCM) flags embedded in the fire product. For FIRMS/DEA point data, cloud masking is already applied upstream.

---

## 3. Pass 1: Contextual Threshold Detection

### 3.1 Himawari AHI Algorithm

Adapted from GOES ABI FDC (Schmidt et al., 2013) and VNP14IMG (Schroeder et al., 2014), tuned for AHI spectral response and Australian conditions.

**Step 1: Absolute threshold screening**

```
Nighttime (solar zenith > 85 deg):
  IF BT_B7 > 320 K  ->  HIGH CONFIDENCE FIRE (skip contextual)
  IF BT_B7 >= 400 K ->  SATURATED FIRE (highest confidence)

Daytime (solar zenith < 85 deg):
  IF BT_B7 > 360 K  ->  HIGH CONFIDENCE FIRE
  IF BT_B7 >= 400 K ->  SATURATED FIRE
```

**Step 2: Sun glint rejection (daytime only)**

```
Compute glint angle theta_g from solar and sensor geometry
IF theta_g < 10 deg  ->  REJECT (sun glint)
IF theta_g < 25 deg AND visible reflectance (B3) > 0.4  ->  REJECT
```

**Step 3: Candidate selection**

```
BTD = BT_B7 - BT_B14

Nighttime candidates:
  BT_B7 > 295 K  AND  BTD > 10 K

Daytime candidates:
  BT_B7 > 310 K  AND  BTD > 20 K
```

These are deliberately conservative -- they cast a wide net that subsequent filtering will narrow.

**Step 4: Contextual background characterization**

For each candidate pixel, compute background statistics from a window of valid (non-fire, non-cloud, non-water) neighbors:

```
Window sizes: start 11x11, expand to 31x31 if needed
Minimum valid background pixels: 10 or 25% of window
Statistics: mean(BT_B7), std(BT_B7), mean(BTD), std(BTD), MAD(BT_B7)
```

**Step 5: Contextual fire tests**

All must pass for NOMINAL confidence:

```
Daytime:
  (1) BT_B7 > BT_B7_mean + 3.5 * std_B7
  (2) BTD > BTD_mean + 3.5 * std_BTD
  (3) BTD > BTD_mean + 6 K    (absolute floor)
  (4) BT_B7 > 310 K           (absolute floor)

Nighttime:
  (1) BT_B7 > BT_B7_mean + 3.0 * std_B7
  (2) BTD > BTD_mean + 3.0 * std_BTD
  (3) BTD > BTD_mean + 6 K
  (4) BT_B7 > 295 K
```

**Step 6: Confidence assignment**

```
HIGH:     Saturated B7 (>= 400 K) OR absolute threshold fires
NOMINAL:  Passes all contextual tests with BTD anomaly > 15 K
LOW:      Passes contextual tests but BTD anomaly 6-15 K, or in glint zone
```

### 3.2 Australian Threshold Adjustments

NSW in April (autumn) has different conditions than the tropics or CONUS:

| Parameter | Standard (Tropical) | NSW April Adjustment | Rationale |
|-----------|-------------------|---------------------|-----------|
| Night BT_B7 candidate | 295 K | 290 K | Cooler autumn nights |
| Day BT_B7 candidate | 310 K | 315 K | Less hot bare ground in autumn, reduce FP |
| BTD day minimum | 20 K | 22 K | Higher threshold for hot NSW soils |
| Background window | 11x11 to 31x31 | 11x11 to 21x21 | NSW landscape is more heterogeneous |
| Glint angle | 10 deg | 12 deg | Slightly wider glint zone for NSW water bodies |

### 3.3 VIIRS Processing

**Core pipeline:** Consume DEA Hotspots and FIRMS point products. The VNP14IMG algorithm is already applied upstream -- we just ingest the detections with their confidence levels.

**Stretch goal (only if direct broadcast partnership materializes):** If processing raw VIIRS data, implement the VNP14IMG algorithm as documented in the ATBD:
- I4 (3.74 um) and I5 (11.45 um) at 375 m resolution
- M13 (4.05 um) at 750 m for FRP retrieval (dual-gain, saturates at 634 K)
- Fixed threshold: night BT_I4 > 320 K -> high confidence
- Contextual window: 11x11 to 31x31 expanding

### 3.4 Landsat and Sentinel-2

**Core pipeline:** Consume via FIRMS point products only. No custom processing of raw imagery.

**Rationale:** Landsat has 2-4 overpasses during the entire 2-week competition (8-day combined revisit) with 4-6 hour latency. The FarEarth/Alice Springs real-time processing partnership is not viable at this timeline. Sentinel-2 has no thermal band and 5-day revisit.

---

## 4. Alert Policy

### 4.1 Immediate Alerting Path

This is the critical change from the v1.0 plan. Instead of holding detections for 20-30 minutes for persistence confirmation, we use a tiered alerting approach:

**Immediate report (no hold):**
- Saturated pixels (BT >= 400 K): Report as HIGH confidence
- Extreme anomalies (BT_B7 > 360 K night, BTD > mean + 5*sigma): Report as PROVISIONAL

**10-minute hold:**
- Marginal contextual detections (BTD > mean + 3.5*sigma but < 5*sigma): Hold for one additional frame
- If persists in next frame: Report as PROVISIONAL
- If disappears: Discard (transient artifact)

**False positive risk assessment:**
- The filtering pipeline (static masks, geometric filters, contextual detection) runs in <5 seconds BEFORE any alert. Most false positives are eliminated before the alert stage.
- The clarification from the all-teams call says "low confidence detections still count if correct." The downside of a false positive is much less than the downside of a delayed true positive.
- Emergency FP reduction protocols remain available if our rate exceeds 5%.

### 4.2 Latency Budget (Immediate Alerting Path)

| Stage | Time Budget | Cumulative |
|-------|-------------|-----------|
| SNS notification receipt | <0.5 s | 0.5 s |
| S3 object fetch (B07 + B14 for NSW segments) | 1-3 s | 3.5 s |
| HSD decode + BT conversion | 0.5 s | 4.0 s |
| Cloud mask (Tier 1) | 0.2 s | 4.2 s |
| Pass 1: Contextual threshold | 1.0 s | 5.2 s |
| Fusion engine update + alert | 0.5 s | 5.7 s |
| **Total processing** | **~5.7 s** | |

**End-to-end latency:** 7-15 min (upstream data latency) + ~6 s (processing) = **~7-15 min from observation to alert** for immediate-path anomalies.

### 4.3 Latency Budget (10-Minute Hold Path)

Same as above, plus 10 minutes for one additional Himawari frame. Total: **~17-25 min from observation to alert.**

### 4.4 DEA/FIRMS Path Latency

| Stage | Time Budget | Cumulative |
|-------|-------------|-----------|
| API poll + response | 1-5 s | 5.0 s |
| Parse detections | 0.1 s | 5.1 s |
| Match to existing events | 0.2 s | 5.3 s |
| Update confidence | 0.1 s | 5.4 s |
| **Total processing** | **~5.4 s** | |

**End-to-end latency:** ~17 min (DEA Hotspots upstream) + ~5 s (processing) = **~17 min from observation.**

---

## 5. Pass 2: ML Classifier (OPTIONAL -- Week 3 Stretch Goal)

### 5.1 Architecture

A lightweight CNN applied ONLY to candidate pixels from Pass 1. This is not a dense prediction model -- it classifies small patches around each candidate.

**Input:** 32x32 pixel patch (native sensor grid) centered on the candidate pixel, with 3 channels:
- BT_MIR (3.9 um or equivalent)
- BT_TIR (11.2 um or equivalent)
- BTD (MIR - TIR)

**Architecture:**
```
Input: 32x32x3
Conv2D(16, 3x3, ReLU) -> MaxPool(2x2)    # 16x16x16
Conv2D(32, 3x3, ReLU) -> MaxPool(2x2)    # 8x8x32
Conv2D(64, 3x3, ReLU) -> GlobalAvgPool   # 64
Dense(32, ReLU) -> Dropout(0.3)
Dense(1, Sigmoid)                          # P(fire)

Total parameters: ~35,000
Inference time: <5 ms per candidate (CPU), <1 ms (GPU)
```

**Output:** P(fire) in [0, 1]. Candidates with P(fire) > 0.5 proceed; those below are suppressed.

### 5.2 Training Data Strategy

**Positive samples (fire):**
- VIIRS VNP14IMGML active fire product from Black Summer 2019-2020 and subsequent NSW fire seasons
- FIRMS historical fire detections over NSW (2015-2025)
- Co-locate VIIRS fire pixels with contemporaneous Himawari AHI frames to extract AHI patches at known fire locations

**Negative samples (not fire):**
- Random clear-sky land pixels (10:1 negative:positive ratio)
- Hard negatives: sun glint patches, hot bare ground, cloud edges, industrial sites
- Use FIRMS static thermal anomaly (STA) mask to sample persistent hot spots as negatives

### 5.3 When to Implement

Only implement if:
- Core pipeline (Pass 0 + Pass 1 + alert policy) is stable and tested
- FP rate during testing exceeds acceptable levels
- There is engineering time available in Week 3

The ML classifier reduces false positives by ~80% with minimal true fire loss. It is valuable but not essential if contextual detection + persistence gives acceptable FP rates.

---

## 6. Pass 3: Sequential Temporal Detection -- CUSUM (OPTIONAL -- Week 3 Stretch Goal)

### 6.1 Reframed Role

CUSUM was previously positioned as our "competitive edge." External review and internal analysis showed this was overclaimed:

| Fire Area | CUSUM Detection Delay | Assessment |
|---|---|---|
| 200 m2 | ~11 hours | Too slow -- VIIRS will have passed before CUSUM triggers |
| 500 m2 | ~2.3 hours | Marginal value -- covers the VIIRS gap |
| 1,000 m2 | ~0.8 hours | Useful but single-frame contextual detection also catches these |
| 5,000 m2 | 1 frame (instant) | No benefit -- already detectable in single frame |

**Where CUSUM adds genuine value:** Background monitoring during the 10-11 hour VIIRS gap (15:00-01:00 AEST and 03:00-13:00 AEST). If a 500 m2 fire ignites at 16:00, CUSUM might flag it by 18:00 -- 7 hours before the next VIIRS pass.

**Recommendation:** Implement as shadow layer in Week 3 if time permits. Run in parallel with contextual detection. Log detections for analysis but do not alert unless confirmed by contextual.

### 6.2 Implementation (If Built)

**Per-pixel state (maintained for all NSW land pixels, ~100,000 pixels):**

```python
State per pixel:
  - DTC parameters: [T_mean, a1, b1, a2, b2]  (harmonic model)
  - Kalman covariance: P (5x5 matrix)
  - CUSUM statistic: S (scalar, resets to 0)
  - Last clear-sky observation time
  - Consecutive anomaly count
```

**Background model (Kalman filter with harmonic DTC):**

```
State transition: F = I (parameters drift slowly)
Process noise: Q = diag([0.01, 0.001, 0.001, 0.0005, 0.0005]^2) K^2
Observation: H = [1, cos(wt), sin(wt), cos(2wt), sin(2wt)]
  where w = 2*pi/24, t = local solar time in hours
Observation noise: R = (0.3 K)^2 night, (0.5 K)^2 day
```

**CUSUM detector:**

```
For each clear-sky observation:
  1. Compute residual: r = BT_observed - BT_predicted
  2. Normalize: z = r / sigma_predicted
  3. Update CUSUM: S = max(0, S + z - k_ref)
  4. If S >= h: FIRE CANDIDATE (temporal detection)
  5. If z < 3.0: update Kalman state (observation is fire-free)

Parameters:
  k_ref = 0.25 sigma (reference value, half the minimum shift)
  h = 5 sigma = 2.0 K (decision threshold)
  Expected ARL_0 = ~930 frames = ~6.5 days (false alarm interval)
```

**Pre-initialization:** Compute Kalman states from 2-4 weeks of Himawari archive data before competition starts. This is required for CUSUM to function from day one.

---

## 7. Minimum Viable Processing Per Sensor Type

| Sensor | Core Pipeline Processing | Additional (Stretch) |
|--------|------------------------|---------------------|
| Himawari AHI | Decode HSD, BT conversion, cloud mask, contextual fire test, alert policy | ML classifier (Pass 2), CUSUM (Pass 3) |
| VIIRS (DEA Hotspots) | Parse GeoJSON, spatial match to events | None needed |
| VIIRS (FIRMS) | Parse CSV, spatial match to events | None needed |
| VIIRS (raw) | NOT in core pipeline | VNP14IMG algorithm if partnership materializes |
| Landsat | Via FIRMS only | NOT processing raw imagery |
| Sentinel-2 | Via FIRMS/DEA only | NOT processing raw imagery |
| GK-2A | Week 2: same contextual algorithm as Himawari | Cross-check feed only |

---

## 8. Open Questions

1. **AHI HSD decode speed**: Can we decode a single-band NSW segment in <0.5 seconds? Need to benchmark with `satpy` vs custom C decoder.

2. **Optimal alert threshold tuning**: The 3.5-sigma vs 5-sigma split for immediate vs held alerts needs empirical validation on April-period Himawari data. Test during Week 1.

3. **Computational architecture**: Lambda vs ECS for 5-second processing? Lambda cold start (~100-500 ms for Python) may be acceptable with provisioned concurrency. ECS with always-on containers eliminates cold start risk.

4. **VZA-dependent thresholds**: At NSW latitudes, Himawari VZA is ~35-43 deg. Should detection thresholds scale with VZA? Nice to have, not essential for MVP.
