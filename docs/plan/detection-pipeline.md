# Detection Pipeline Design

## 1. Pipeline Architecture Overview

The detection pipeline processes satellite data through three passes, each trading compute time for accuracy. The entire chain must complete within 10 seconds of data arrival for geostationary data, and within 30 seconds for polar-orbiting data.

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
[Pass 2: ML Classifier]        <1 sec (candidates only)
    |
    v
[Pass 3: Temporal Integration]  <1 sec (update state)
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

**VIIRS (6 passes/day):**
- If processing raw SDR/RDR: decode HDF5, extract I4 (3.74 um) and I5 (11.45 um) bands
- If using FIRMS/DEA Hotspots point products: parse CSV/GeoJSON directly (no image processing needed)
- Apply geolocation from embedded ephemeris
- NO atmospheric correction
- Handle bow-tie deletion fill values

**Landsat (opportunistic):**
- If via USGS RT (4-6 hours): download L1 GeoTIFF, extract Band 7 (SWIR2) and Band 10 (TIR)
- Convert DN to reflectance (Band 7) and BT (Band 10) using metadata scaling factors
- If via FarEarth (<10s): process streaming X-band data line-by-line

**Sentinel-2 (opportunistic):**
- Download L1C tile, extract Band 12 (SWIR2, 2.19 um) and Band 4 (Red, 0.665 um)
- Convert DN to TOA reflectance using metadata

### 2.2 What We Skip (Key Insight)

Atmospheric correction is NOT needed for fire detection. The fire signal (tens of kelvin BT anomaly) is orders of magnitude larger than atmospheric effects (~0.5-2 K). All operational fire detection algorithms (MOD14, VNP14IMG, ABI FDC) work on uncorrected brightness temperatures. Skipping atmospheric correction saves ~5-10 seconds per scene and eliminates dependency on ancillary data (NWP fields, ozone profiles, etc.).

Orthorectification is not needed for geostationary data (fixed grid). For VIIRS, the built-in geolocation is sufficient (~375 m accuracy). For Landsat/Sentinel-2, the L1 products include adequate geolocation.

### 2.3 Cloud Masking Strategy

Cloud masking must be fast but conservative (miss a cloud = false fire detection; mask a fire = missed detection). We use a two-tier approach:

**Tier 1 (fast, ~100 ms per scene):**
- BT_11 < 265 K -> cloud (thick cloud is very cold)
- BT_11 < 285 K AND visible reflectance > 0.4 (daytime) -> cloud
- This catches ~80% of cloud pixels with minimal compute

**Tier 2 (contextual, applied during fire detection):**
- Reject fire candidates within 2 pixels of any Tier 1 cloud pixel
- Use BT_11 spatial standard deviation to detect cloud edges (high variability = edge)
- Accept that ~5-10% of cloud pixels will be missed -- the temporal persistence filter (Pass 3) handles transient false alarms from missed cloud edges

For VIIRS, use the operational VIIRS cloud mask (VCM) flags embedded in the fire product. For FIRMS point data, cloud masking is already applied upstream.

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

These are deliberately conservative -- they cast a wide net that Pass 2 and temporal filtering will narrow.

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

### 3.3 VIIRS VNP14IMG Adaptation

If processing raw VIIRS data (direct broadcast scenario), implement the VNP14IMG algorithm as documented in the ATBD. Key parameters:

- I4 (3.74 um) and I5 (11.45 um) at 375 m resolution
- M13 (4.05 um) at 750 m for FRP retrieval (dual-gain, saturates at 634 K)
- Fixed threshold: night BT_I4 > 320 K -> high confidence (class 9)
- Contextual window: 11x11 to 31x31 expanding
- BT4S adaptive scene threshold: 325-330 K range
- Day: BTD > 25 K AND BT_I4 > BT4S
- Night: BTD > 10 K AND BT_I4 > 295 K

If consuming FIRMS or DEA Hotspots point products, the algorithm is already applied -- we just ingest the detections with their confidence levels.

### 3.4 Landsat Active Fire Algorithm

Uses reflective SWIR bands (not thermal), following the LFTA approach:

```
Fire candidate IF:
  B7_reflectance > threshold_B7 (typically 0.15-0.25)
  AND B7/B4 ratio > threshold_ratio (typically 1.5-3.0)
  AND B6_reflectance > threshold_B6
```

This can detect fires as small as ~4 m2 at 30 m resolution. Apply only to Landsat scenes that overlap with the competition area and arrive during the competition window.

### 3.5 Sentinel-2 Fire Detection

No thermal band -- use SWIR bands:

```
Fire candidate IF:
  B12_TOA_reflectance > 0.15
  AND B12/B4 > 2.0
  AND spatial context anomaly (B12 > mean_B12 + 3*std)
```

Limited to daytime, limited sensitivity. Use for confirmation only.

---

## 4. Pass 2: ML Classifier (False Positive Reduction)

### 4.1 Architecture

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

### 4.2 Training Data Strategy

**Positive samples (fire):**
- VIIRS VNP14IMGML active fire product (validated fire pixels) from Black Summer 2019-2020 and subsequent NSW fire seasons
- FIRMS historical fire detections over NSW (2015-2025)
- Co-locate VIIRS fire pixels with contemporaneous Himawari AHI frames to extract AHI patches at known fire locations
- Augment with prescribed burns with known ignition times from NSW RFS records

**Negative samples (not fire):**
- Random clear-sky land pixels from the same scenes as positive samples (10:1 negative:positive ratio)
- Hard negatives: known false positive sources -- sun glint patches, hot bare ground, cloud edges, industrial sites
- Use the FIRMS static thermal anomaly (STA) mask to sample persistent hot spots as negatives

**Sensor-specific models:**
- Train separate models for AHI (2 km), VIIRS (375 m), and MODIS (1 km) due to different spectral responses and pixel sizes
- The AHI model is most critical since it processes 144 scenes/day

**Class balance:**
- Oversample fire class to 1:3 ratio (fire:non-fire)
- Use focal loss to handle remaining imbalance

### 4.3 Inference Optimization

- Pre-compile model with ONNX Runtime for CPU inference (avoids GPU dependency)
- Batch all candidates from a single frame (typically <100 candidates for NSW)
- Total Pass 2 time: <500 ms for a typical Himawari frame with ~50 candidates

---

## 5. Pass 3: Sequential Temporal Detection (Kalman + CUSUM)

### 5.1 Why This Matters

This is potentially our competitive edge. Single-frame geostationary detection requires fires of ~1,000-4,000 m2. Sequential temporal detection using CUSUM can detect fires of 200-500 m2 by integrating evidence across multiple 10-minute frames.

The physics: A 200 m2 fire at 800 K in a 3.5 km AHI pixel produces a BT increase of ~0.15 K -- below the single-frame noise floor (~0.3-0.5 K). But over 6-12 frames (1-2 hours), the cumulative evidence exceeds the detection threshold.

### 5.2 Implementation

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

**Multi-scale CUSUM (run 3 detectors in parallel):**

```
Detector 1: k_ref = 0.05 K, h = 2.0 K  -> very small fires (~50-100 m2), slow detection
Detector 2: k_ref = 0.15 K, h = 2.0 K  -> medium fires (~200-500 m2)
Detector 3: k_ref = 0.50 K, h = 2.0 K  -> larger fires (~1000+ m2), fast detection
```

### 5.3 Expected Performance

| Fire Area (m2) | BT Increase (K) | SNR/frame | CUSUM Detection Delay | Delay (hours) |
|----------------|------------------|-----------|----------------------|---------------|
| 50 | ~0.04 | 0.10 | >200 frames | >33 |
| 100 | ~0.08 | 0.20 | ~170 frames | ~28 |
| 200 | ~0.15 | 0.38 | ~65 frames | ~11 |
| 500 | ~0.35 | 0.88 | ~14 frames | ~2.3 |
| 1,000 | ~0.70 | 1.75 | ~5 frames | ~0.8 |
| 2,000 | ~1.40 | 3.50 | ~2 frames | ~0.3 |
| 5,000 | ~3.50 | 8.75 | 1 frame | ~0.17 |

### 5.4 Comparison: CUSUM vs RST-FIRES (ALICE)

**RST-FIRES ALICE approach:**
- Uses multi-year pixel-level statistics (mean and std) rather than real-time Kalman filter
- Anomaly index: ALICE = (V - mu_V) / sigma_V where mu and sigma are from archive
- Reported 3-70x more sensitive than other SEVIRI fire products
- Simpler to implement (just a lookup table per pixel per time-of-day)
- Weakness: requires multi-year homogeneous archive for each pixel

**Our Kalman + CUSUM approach:**
- Adapts in real-time to current conditions (no historical archive dependency)
- Optimal detection delay (CUSUM is minimax optimal for change detection)
- Handles non-stationary backgrounds (weather transitions, post-fire changes)
- More complex to implement

**Recommendation:** Implement CUSUM as the primary temporal detector. Pre-compute RST-style statistics from 1-2 years of Himawari archive as a cross-check and to initialize the Kalman filter states at competition start.

### 5.5 Cloud Gap Handling

When a pixel is cloud-covered, no observation is available. Strategy:

1. Do NOT update the CUSUM statistic (preserve accumulated evidence)
2. Apply exponential decay during gaps > 2 hours: S = S * exp(-dt / tau_decay) with tau_decay = 3 hours
3. Let the Kalman filter prediction uncertainty grow (P_pred increases during gaps)
4. When observation resumes, the Kalman gain is large (trusts new observation more)

---

## 6. Latency Budget

### 6.1 Geostationary (Himawari) Path

| Stage | Time Budget | Cumulative |
|-------|-------------|-----------|
| SNS notification receipt | <0.5 s | 0.5 s |
| S3 object fetch (B07 + B14 for NSW segments) | 1-3 s | 3.5 s |
| HSD decode + BT conversion | 0.5 s | 4.0 s |
| Cloud mask (Tier 1) | 0.2 s | 4.2 s |
| Pass 1: Contextual threshold | 1.0 s | 5.2 s |
| Pass 2: ML classifier (candidates) | 0.5 s | 5.7 s |
| Pass 3: CUSUM update (all pixels) | 0.3 s | 6.0 s |
| Fusion engine update + alert | 0.5 s | 6.5 s |
| **Total processing** | **~6.5 s** | |

This leaves ~3.5 seconds of margin within our 10-second target.

### 6.2 Polar-Orbiting (VIIRS) Path

**Option A: FIRMS/DEA Hotspots (point product)**

| Stage | Time Budget | Cumulative |
|-------|-------------|-----------|
| API poll + response | 1-5 s | 5.0 s |
| Parse detections | 0.1 s | 5.1 s |
| Match to existing events | 0.2 s | 5.3 s |
| Update confidence scores | 0.1 s | 5.4 s |
| **Total** | **~5.4 s** | |

**Option B: Direct broadcast (raw VIIRS data)**

| Stage | Time Budget | Cumulative |
|-------|-------------|-----------|
| Data receipt from ground station | Variable | - |
| SDR decode + BT conversion | 2-5 s | 5.0 s |
| Cloud mask | 0.5 s | 5.5 s |
| VNP14IMG fire detection | 2.0 s | 7.5 s |
| ML classifier | 0.5 s | 8.0 s |
| Fusion update + alert | 0.5 s | 8.5 s |
| **Total processing** | **~8.5 s** | |

### 6.3 High-Resolution (Landsat/Sentinel-2) Path

Not time-critical (4+ hour latency upstream). Budget 30-60 seconds for processing.

---

## 7. Minimum Viable Processing Per Sensor Type

| Sensor | Must Do | Can Skip | Processing Time |
|--------|---------|----------|-----------------|
| Himawari AHI | Decode HSD, BT conversion, cloud mask, contextual fire test | Atmospheric correction, reprojection, full cloud mask | ~5 s |
| VIIRS (FIRMS) | Parse CSV, spatial match | Everything (already processed) | ~1 s |
| VIIRS (raw) | Decode HDF5, BT conversion, cloud mask, VNP14IMG algorithm | Atmospheric correction, terrain correction | ~8 s |
| Landsat | Decode GeoTIFF, SWIR reflectance, LFTA algorithm | Atmospheric correction (use TOA) | ~15 s |
| Sentinel-2 | Decode JP2, SWIR reflectance, HTA test | Atmospheric correction | ~10 s |
| MODIS | Parse FIRMS CSV or run MOD14 on raw data | Same as VIIRS | ~1-8 s |

---

## 8. Open Questions

1. **AHI HSD decode speed**: Can we decode a single-band NSW segment in <0.5 seconds? Need to benchmark with `satpy` vs custom C decoder.

2. **CUSUM initialization**: How long does the Kalman filter need to converge to a stable DTC model? Likely 24-48 hours of clear-sky observations. Must initialize from archive data before competition starts.

3. **ML model generalization**: Will a model trained on Black Summer 2019-2020 data generalize to April 2026 autumn conditions? Need to validate on April-period historical data.

4. **Optimal channel for CUSUM**: Use BT_3.9 alone, BTD (3.9 - 11.2), or both? BTD removes atmospheric noise but reduces fire signal by ~20-30%. Likely best to run CUSUM on BTD for robustness.

5. **VZA-dependent thresholds**: At NSW latitudes, Himawari VZA is ~35-43 deg. Should detection thresholds scale with VZA? The pixel area increases by 1.8-2.4x, which proportionally increases minimum detectable fire size.

6. **Computational architecture**: Lambda vs ECS for 10-second processing? Lambda cold start (~100-500 ms for Python) may be acceptable with provisioned concurrency. ECS with always-on containers eliminates cold start risk.
