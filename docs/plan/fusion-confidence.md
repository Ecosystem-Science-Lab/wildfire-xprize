# Fusion, Confidence, and Event Tracking System Design

## 1. Trigger-Refine-Confirm Pipeline

### 1.1 Stage 1: TRIGGER (0-10 minutes)

**Source:** Himawari AHI contextual fire detection (Pass 1 + Pass 2 from detection pipeline)

**Output:** Fire candidate with:
- Location: pixel center (lat/lon in AHI fixed grid)
- Uncertainty ellipse: semi-major axis = sqrt((pixel_size/2)^2 + geoloc_error^2) ~ 2.5-3.0 km at NSW latitudes
- Single-frame confidence: LOW (0.20-0.50) or NOMINAL (0.50-0.85) or HIGH (>0.85)
- Brightness temperature anomaly magnitude
- Day/night flag

**Action:** Create a CANDIDATE event in the event store. Do NOT alert unless HIGH confidence (saturated pixel or extreme anomaly > 40 K above background). For LOW/NOMINAL, wait for refinement.

**Timing:** Every 10 minutes from Himawari. Alert latency for HIGH confidence fires: ~7-15 minutes from observation (dominated by upstream data latency).

### 1.2 Stage 2: REFINE (10-30 minutes)

**Source:** 2-3 consecutive Himawari AHI frames + CUSUM temporal detection

**Tests applied:**

1. **Persistence check:** Require detection in at least 2 of 3 consecutive frames (20-30 minute window). Single-frame detections are flagged as TRANSIENT and downgraded to LOW confidence.

2. **Intensity trend:** If the BTD anomaly is increasing across frames, upgrade confidence by +0.15. A growing fire is strong evidence of a real detection vs. a transient artifact.

3. **CUSUM temporal detection:** If the CUSUM statistic exceeds the threshold (h = 5 sigma) for this pixel, upgrade confidence by +0.20. This catches fires too small for single-frame detection.

4. **GK-2A cross-check:** If GK-2A independently detects a fire in the same pixel (within spatial matching radius), upgrade confidence by +0.25. Two independent geostationary detections from different viewing angles is very strong evidence.

**Output:** Refined candidate with updated confidence and state transition:
- CANDIDATE -> ACTIVE (if confidence > 0.50 after refinement)
- CANDIDATE -> REJECTED (if single-frame transient with no supporting evidence)

**Action:** For ACTIVE events with confidence > 0.50, generate NOMINAL alert. Include uncertainty ellipse, BT anomaly magnitude, and evidence trail.

### 1.3 Stage 3: CONFIRM (30 minutes to hours)

**Source:** VIIRS/MODIS overpass detections, Landsat/Sentinel-2 if available, FIRMS NRT cross-check

**Confirmation logic:**

1. **VIIRS confirmation (+3.0 to +4.0 log-odds):** A VIIRS active fire detection within the Himawari uncertainty ellipse is the strongest confirmation signal. VIIRS high-confidence = +4.0, nominal = +3.0, low = +1.0.

2. **VIIRS non-detection (-1.5 log-odds):** If VIIRS passes over the candidate location and does NOT detect a fire, this is weak negative evidence. The fire may be too small for VIIRS at that scan angle, or may have self-extinguished. Apply only -1.5 log-odds (not a hard rejection).

3. **Landsat/Sentinel-2 confirmation (+4.5 to +5.0 log-odds):** High-resolution detection at a known fire candidate location is near-definitive confirmation.

4. **FIRMS NRT match (+3.0 log-odds):** Independent operational fire product detects fire at same location.

5. **DEA Hotspots match (+2.5 log-odds):** Australian operational system confirmation.

**Output:** Confirmed fire event with HIGH confidence, precise VIIRS-derived location (375 m vs 2 km), and FRP estimate from M13 band.

---

## 2. Cross-Resolution Combination

### 2.1 The Resolution Hierarchy Problem

Our sensors span 3 orders of magnitude in resolution:

| Sensor | Pixel Size | Fire Localization | Min Detectable |
|--------|-----------|-------------------|----------------|
| Himawari AHI | 3-4 km | ~3 km uncertainty | ~1,000-4,000 m2 |
| MODIS | 1-5 km | ~1.5 km uncertainty | ~1,000 m2 |
| VIIRS I-band | 375 m-1.6 km | ~0.5 km uncertainty | ~100-500 m2 |
| Landsat OLI | 30 m | ~50 m uncertainty | ~4 m2 |
| Sentinel-2 MSI | 20 m | ~20 m uncertainty | ~4 m2 (SWIR) |

When a 3 km Himawari pixel detects a fire, we know the fire is somewhere within ~13 km2. A VIIRS detection narrows this to ~0.14 km2. A Landsat detection pinpoints to ~900 m2.

### 2.2 Spatial Matching Algorithm

**Step 1: Buffer the coarser detection by its uncertainty radius**

```
AHI detection at (lat, lon):
  buffer_radius = sqrt((pixel_size/2)^2 + geoloc_error^2)
  At NSW: buffer_radius ~ 2000 m (pixel ~3500 m, geoloc ~1000 m)
```

**Step 2: Search for finer-resolution detections within the buffer**

```
For each VIIRS/MODIS/Landsat detection:
  distance = haversine(AHI_lat, AHI_lon, detection_lat, detection_lon)
  IF distance < buffer_radius:
    MATCH (candidate for association)
```

**Step 3: Temporal window check**

```
AHI -> VIIRS:   max offset = 3 hours (covers overpass gap)
AHI -> MODIS:   max offset = 3 hours
AHI -> Landsat: max offset = 6 hours (very sparse, any match valuable)
VIIRS -> MODIS: max offset = 30 min (often near-simultaneous)
```

**Step 4: Location refinement on match**

When a finer-resolution sensor confirms a coarser detection:
- Update the event centroid to the finer-resolution position
- Shrink the uncertainty ellipse to the finer sensor's uncertainty
- Log the multi-sensor match in the event evidence trail

### 2.3 Handling Conflicting Detections

Scenario: AHI detects fire at location A, but the nearest VIIRS detection is 4 km away at location B.

Decision tree:
1. If distance(A, B) < AHI_buffer + VIIRS_buffer (~2.5 km): MATCH (same fire, use VIIRS position)
2. If distance(A, B) > combined buffers: TWO SEPARATE EVENTS (fire may have spread, or multiple ignitions)
3. If AHI detects but VIIRS does not (within buffer): MAINTAIN AHI detection, do not reject. Fire may be below VIIRS threshold at that scan angle.

---

## 3. Confidence Scoring System

### 3.1 Bayesian Log-Odds Framework

Each piece of evidence contributes a log-likelihood ratio (LLR) to the cumulative fire probability:

```
log_odds(fire) = prior + sum(LLR_evidence_i) - sum(LLR_penalty_j)
P(fire) = 1 / (1 + exp(-log_odds))
```

**Prior:** log(0.001/0.999) = -6.9 (base rate: 0.1% of pixels are fire at any time during fire season)

### 3.2 LLR Table

| Evidence | LLR | Rationale |
|----------|-----|-----------|
| **Positive evidence** | | |
| AHI strong anomaly (BTD > mean + 6*sigma) | +4.0 | Very strong thermal signal |
| AHI moderate anomaly (BTD > mean + 4*sigma) | +2.5 | Moderate signal |
| AHI weak anomaly (BTD > mean + 3*sigma) | +1.0 | Marginal signal |
| Persistent 3/3 frames | +2.0 | Real fires persist |
| Persistent and growing | +2.5 | Intensifying = real fire |
| CUSUM threshold exceeded | +2.0 | Temporal integration detection |
| GK-2A independent detection | +2.5 | Independent sensor confirmation |
| VIIRS high confidence match | +4.0 | Gold standard LEO fire product |
| VIIRS nominal match | +3.0 | Good LEO confirmation |
| VIIRS low confidence match | +1.0 | Marginal LEO confirmation |
| MODIS detection match | +2.5 | Secondary LEO confirmation |
| Landsat thermal anomaly | +5.0 | Near-definitive at 30 m |
| Sentinel-2 SWIR anomaly | +4.5 | Very high resolution confirmation |
| FIRMS NRT match | +3.0 | Independent operational product |
| DEA Hotspots match | +2.5 | Australian operational system |
| Fire weather elevated | +0.5 | Environmental context |
| Vegetation present (land cover) | +0.5 | Fuel available |
| Recent lightning (24h, 10km) | +1.0 | Ignition source |
| **Negative evidence / penalties** | | |
| AHI no anomaly when expected | -2.0 | Should see fire if real |
| Transient (1/3 frames) | -1.5 | Likely artifact |
| VIIRS overpass, no detection | -1.5 | Weak negative (fire may be small) |
| Sun glint zone | -3.0 | Common false positive source |
| Known industrial site (STA mask) | -4.0 | Persistent anthropogenic heat |
| Water body | -2.0 | Fire unlikely on water |
| Desert/bare soil (daytime) | -1.0 | Hot ground false positive risk |
| Urban area | -1.0 | Urban heat island risk |

### 3.3 Confidence Tiers and Actions

| Tier | P(fire) | Action | Typical Evidence |
|------|---------|--------|-----------------|
| HIGH | > 0.85 | Alert immediately, include in report | AHI persistent + VIIRS confirm, OR saturated pixel |
| NOMINAL | 0.50-0.85 | Alert with caveat "unconfirmed", monitor | AHI persistent, awaiting LEO pass |
| LOW | 0.20-0.50 | Internal monitoring only, do not report | Single AHI frame, moderate anomaly |
| REJECTED | < 0.20 | Suppress from output, log for audit | Failed persistence, known FP source |

### 3.4 Confidence Over Time

Confidence evolves as evidence accumulates:

```
T+0 min:   AHI single frame, moderate anomaly -> P = 0.15 (LOW)
T+10 min:  AHI second frame, anomaly persists  -> P = 0.45 (LOW, borderline)
T+20 min:  AHI third frame, anomaly growing    -> P = 0.72 (NOMINAL) -> ALERT
T+90 min:  VIIRS passes, high-confidence match  -> P = 0.97 (HIGH) -> UPDATE ALERT
T+120 min: FIRMS NRT confirms                   -> P = 0.99 (HIGH)
```

---

## 4. False Positive Reduction Strategy

### 4.1 Layered Filtering (Order Matters)

Each filter is applied in sequence. The order is designed so that cheap, high-impact filters run first:

```
Layer 1: Static masks (pre-computed, ~0 runtime cost)
  - Land/water mask (reject water pixels except known gas flares)
  - Urban mask (raise thresholds by +5 K for urban pixels)
  - Industrial site mask (reject known persistent hot spots)
  - VZA mask (reject pixels with VZA > 65 deg)

Layer 2: Geometric filters (fast computation)
  - Sun glint angle check (reject if glint angle < 10-12 deg)
  - Solar zenith angle (apply day/night thresholds correctly)

Layer 3: Contextual detection (Pass 1, ~1 second)
  - Background statistics + adaptive thresholds
  - This is where most false positives are eliminated

Layer 4: ML classifier (Pass 2, ~0.5 second)
  - Trained on known false positive types
  - Catches complex patterns (cloud edges, partial cloud, mixed terrain)

Layer 5: Temporal persistence (Pass 3 / Stage 2, ~10-30 minutes)
  - Require 2/3 frames for nominal confidence
  - Sun glint shifts between frames; real fires persist
  - Eliminates ~80% of remaining single-frame false positives

Layer 6: Cross-sensor confirmation (Stage 3, hours)
  - VIIRS/MODIS cross-check is the final arbiter
  - False positives at this stage are extremely rare
```

### 4.2 Expected False Positive Rates by Layer

| After Layer | Estimated FP Rate | FP per Day (NSW, 100K pixels) |
|-------------|-------------------|------------------------------|
| Raw candidates (no filtering) | ~1% | ~1,440 per scan = ~207K/day |
| After Layer 3 (contextual) | ~0.1% | ~144 per scan = ~20K/day |
| After Layer 4 (ML) | ~0.02% | ~30 per scan = ~4,300/day |
| After Layer 5 (temporal) | ~0.003% | ~4 per scan = ~576/day |
| After Layer 6 (cross-sensor) | ~0.0005% | <1 per scan = ~70/day |

Target: <5% false positive rate among REPORTED fires. If we report ~5-20 real fires per day during the competition, we need fewer than 1 false positive per day. The layered approach should achieve this.

### 4.3 Emergency FP Reduction

If our false positive rate exceeds 5% during the competition:

1. **Raise persistence threshold:** Require 3/3 frames instead of 2/3 (20 min delay increase)
2. **Night-only geostationary alerting:** Suppress daytime AHI-only detections (eliminate sun glint, hot soil)
3. **Require VIIRS confirmation:** Only report fires confirmed by at least one LEO sensor (delays all reports by hours but virtually eliminates FPs)
4. **Manual review:** Have a team member review each alert before submission (not scalable but last resort)

---

## 5. Event Tracking

### 5.1 Event Lifecycle

```
NEW DETECTION
    |
    v
CANDIDATE -----> REJECTED (FP filter, Layer 1-4)
    |
    | (persistence confirmed, 2/3 frames)
    v
ACTIVE --------> REJECTED (FP filter, cross-sensor negative)
    |
    | (area or FRP increasing)
    v
GROWING
    |
    | (FRP stable or decreasing)
    v
STABLE / DECLINING
    |
    | (no detections for 5 days)
    v
EXTINGUISHED --> ARCHIVED
```

### 5.2 Event Association Rules

When a new detection arrives, associate it with an existing event or create a new one:

1. **Spatial search:** Find all ACTIVE/GROWING/STABLE events within matching radius
   - AHI detection: search radius = 5 km
   - VIIRS detection: search radius = 2 km
   - Landsat/S2: search radius = 1 km

2. **Temporal filter:** Event must have had a detection within the last 5 days

3. **Association:** If match found, add detection to nearest event. Update centroid, geometry, confidence.

4. **Creation:** If no match, create new CANDIDATE event.

5. **Merge check:** After association, check if any two events' geometries overlap by >30%. If so, merge them into one event.

### 5.3 Geometry Representation

- **1 detection:** Point with uncertainty buffer (radius = sensor uncertainty)
- **2 detections:** LineString with buffer
- **3+ detections:** Concave hull (alpha shape, alpha ratio = 0.3) around detection points
- Update geometry with each new detection
- Compute area in km2 using equirectangular approximation at NSW latitudes (1 deg lat ~ 111 km, 1 deg lon ~ 93 km at 33S)

### 5.4 Fire Characterization (For 10-Minute Reports)

Every 15 minutes (or more frequently), output for each ACTIVE+ event:

| Field | Source | Method |
|-------|--------|--------|
| Location (lat/lon) | Best available sensor | Centroid of detections |
| Location uncertainty | Sensor resolution | Uncertainty ellipse |
| Fire perimeter | All detections | Concave hull geometry |
| Estimated area (m2) | Hull area or FRP-based | Alpha shape area |
| Fire intensity (FRP, MW) | VIIRS M13 or AHI B7 | Wooster MIR radiance method |
| Intensity trend | Time series of FRP | Linear slope over last 5 detections |
| Direction of spread | Sequential detection centroids | Bearing from first to latest |
| Rate of spread (m/h) | Centroid displacement / time | Distance / elapsed time |
| Confidence | Bayesian log-odds | P(fire) and tier |
| Contributing sensors | Event detection list | List of unique sensors |

---

## 6. Validation Plan

### 6.1 Historical Replay Testing

**Dataset: Black Summer 2019-2020 (NSW)**
- Period: October 2019 - March 2020
- Known fires: NIFC/FIRMS fire archive, NSW RFS records
- Satellite data: Himawari-8 archive (nearly identical to Himawari-9), VIIRS archive, Landsat archive
- Ground truth: Burned area products (MCD64A1, Sentinel-2 dNBR), fire agency records

**Methodology:**
1. Replay Himawari-8 data through the pipeline in chronological order
2. Inject realistic data latency (7-15 min for Himawari, 3 hours for FIRMS)
3. Compare detected events against FIRMS/MCD64A1 reference
4. Compute detection time (our alert timestamp - satellite observation time)
5. Compute false positive rate (our alerts not corroborated by any reference within 6 hours)

**Metrics:**
- Detection rate: fraction of FIRMS detections we also detect
- Detection delay: time from first FIRMS detection to our first alert
- False positive rate: fraction of our alerts with no FIRMS/MCD64A1 match
- Spatial accuracy: distance between our centroid and FIRMS point
- FRP correlation: our FRP estimate vs FIRMS FRP

### 6.2 April-Specific Testing

Black Summer was during summer (Nov-Feb). April conditions differ:
- Lower background temperatures
- Different solar geometry
- Different cloud patterns
- Lower fire frequency

**Additional test periods:**
- April 2020 (post-Black Summer, some fires still burning)
- April 2021, 2022, 2023 (normal autumn fire activity in NSW)
- April 2024, 2025 (most recent data for algorithm validation)

### 6.3 Prescribed Burn Validation

Contact NSW RFS for prescribed burn records during April periods. Prescribed burns have:
- Known ignition time and location
- Known fire size (typically small: 10-500 ha)
- Controlled conditions

This provides the most accurate ground truth for timing and localization validation.

---

## 7. Training Data Construction

### 7.1 Positive Samples (Fire)

| Dataset | Period | Fires | Resolution | Use |
|---------|--------|-------|-----------|-----|
| FIRMS VIIRS (S-NPP, NOAA-20) | 2012-2025 | ~100K/yr over NSW | 375 m | Primary training labels |
| FIRMS MODIS (Terra, Aqua) | 2000-2025 | ~50K/yr over NSW | 1 km | Supplementary labels |
| FIRMS Himawari-9 | 2022-2025 | ~10K/yr over NSW | 2 km | Geostationary labels |
| MCD64A1 Burned Area | 2000-2025 | Monthly | 500 m | Area validation |
| NSW RFS fire records | 2010-2025 | Variable | Point/polygon | Ground truth |
| DEA Hotspots archive | 2003-2025 | ~50K/yr | Variable | Australian-specific labels |

### 7.2 Negative Samples (Non-Fire)

For each positive fire pixel, sample:
- 10 random clear-sky land pixels from the same scene (geographic diversity)
- 3 known false positive types:
  - Sun glint pixels (identified by glint angle < 15 deg AND high BT_MIR)
  - Hot bare ground (identified by land cover = barren AND BT_MIR > 310 K)
  - Cloud edges (identified by adjacency to cloud mask AND elevated BTD)
  - Industrial sites (from FIRMS Static Thermal Anomaly mask)

### 7.3 Class Balance Strategy

- Target ratio: 1:3 (fire:non-fire) for training
- Oversample fire pixels from underrepresented conditions (nighttime, low FRP, cloudy scenes)
- Use focal loss with gamma=2 to focus on hard examples
- Stratify by sensor, time-of-day, season, and land cover type

### 7.4 Label Quality

FIRMS confidence levels map to label quality:
- VIIRS high confidence -> positive label weight = 1.0
- VIIRS nominal -> weight = 0.8
- VIIRS low -> weight = 0.5 (or exclude from training)
- FIRMS geostationary (provisional) -> weight = 0.6

For AHI model training, co-locate VIIRS fire detections with Himawari frames within +/- 5 minutes to create labeled AHI patches.
