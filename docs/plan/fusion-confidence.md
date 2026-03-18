# Fusion, Confidence, and Event Tracking System Design

**Updated:** 2026-03-18 (revised priorities)

## 1. Confidence System: Rule-Based Ladder

### 1.1 Why Rule-Based (Not Bayesian)

The v1.0 plan used a Bayesian log-odds framework. External review identified two critical problems:

1. **Double-counting:** The same Himawari observation processed by our pipeline (+4.0 LLR), FIRMS (+3.0 LLR), and DEA Hotspots (+2.5 LLR) was summed as +9.5 LLR. These are NOT independent observations -- they are three processing chains applied to the SAME satellite data.

2. **Calibration vacuum:** The LLR values require empirical calibration for NSW April conditions. We have no such data. Mis-calibrated LLRs produce either overconfident or underconfident results that are hard to debug during a live competition.

The rule-based ladder is transparent, debuggable, and correct. It can be implemented in a day. Bayesian scoring can replace it later if time permits.

### 1.2 Confidence Levels

```
LEVEL 1 - PROVISIONAL (report immediately):
  Single AHI frame, passes contextual tests
  OR: Single DEA/FIRMS detection (fallback system)

LEVEL 2 - LIKELY (report with moderate confidence):
  AHI persistent 2/3 frames, OR
  AHI single frame + GK-2A independent detection, OR
  DEA Hotspots detection + FIRMS detection (different sources agreeing)

LEVEL 3 - CONFIRMED (report with high confidence):
  AHI detection + VIIRS/MODIS detection within spatial match radius, OR
  AHI persistent 3/3 frames AND growing intensity, OR
  Any Landsat/Sentinel-2 confirmation via FIRMS

LEVEL 4 - HIGH CONFIDENCE:
  Multiple independent sensor confirmations (AHI + VIIRS + FIRMS NRT all agree)

RETRACTED:
  Single AHI frame, NOT confirmed in next 2 frames, no LEO confirmation within 6 hours
```

### 1.3 Special Cases

**Saturated pixels (BT >= 400 K):** Skip directly to LEVEL 3 (CONFIRMED). Near-zero false positive risk. These are unambiguously fire.

**Extreme anomalies (BT_B7 > 360 K night):** Start at LEVEL 2 (LIKELY). Very strong thermal signal, upgrade on next confirming observation.

---

## 2. Provenance Tracking (Fixes Double-Counting)

Provenance tracking is a first-class concept in the revised system. Every piece of evidence in the event store must carry provenance metadata.

### 2.1 Core Rules

**Rule 1: One observation = one evidence contribution.**

When the same satellite observation is processed by multiple pipelines, take the MAXIMUM confidence contribution, not the sum.

```
For a given Himawari observation at time T, location L:
  our_detection = contextual_fire_test(AHI_data)     -> contributes to LEVEL 1+
  firms_detection = FIRMS_match(time=T, location=L)   -> contributes to LEVEL 1+
  dea_detection = DEA_match(time=T, location=L)        -> contributes to LEVEL 1+

  Combined contribution for this observation = best of the three
  NOT: all three stacked as independent evidence
```

**Rule 2: Independence requires different sensors or different times.**

True independent evidence comes from:
- **Different satellites** (Himawari vs GK-2A at the same time): independent, different viewing angles -> can upgrade confidence
- **Different sensor types** (Himawari AHI vs VIIRS): independent, different orbits, different resolutions -> strong upgrade
- **Same satellite, different times** (Himawari frame at T vs T+10min): semi-independent, temporal persistence -> moderate upgrade

**Rule 3: Every detection record includes:**

```python
{
    "detection_id": "uuid",
    "source_satellite": "Himawari-9",       # Which satellite
    "observation_time": "2026-04-10T14:20:00Z",  # When the satellite observed
    "processing_pipeline": "custom",        # "custom" | "FIRMS" | "DEA"
    "is_primary": true,                     # Primary observation or derived?
    "observation_key": "H9_20260410_1420",  # Unique key for deduplication
    "confidence_from_source": "nominal",    # What the source pipeline reported
    "lat": -33.85,
    "lon": 151.21,
    "bt_anomaly_k": 25.3,                  # Brightness temp anomaly (if available)
}
```

### 2.2 Deduplication Logic

When a new detection arrives, check if we already have evidence from the same `observation_key` (same satellite + same observation time):

```
IF observation_key already exists for this event:
    Keep the detection with highest confidence_from_source
    Mark the duplicate as DERIVED (is_primary = false)
    Do NOT upgrade confidence level based on a duplicate
ELSE:
    Add as new PRIMARY evidence
    Evaluate whether this upgrades the event confidence level
```

### 2.3 What Counts as Independent for Confidence Upgrades

| Evidence Pair | Independent? | Upgrades Confidence? |
|--------------|-------------|---------------------|
| Our AHI detection + FIRMS AHI detection (same time) | NO (same observation) | NO |
| Our AHI detection + DEA Hotspots AHI detection (same time) | NO (same observation) | NO |
| Our AHI detection at T + Our AHI detection at T+10min | SEMI (same satellite, different time) | YES (persistence) |
| Our AHI detection + GK-2A detection (same time) | YES (different satellite) | YES |
| Our AHI detection + VIIRS DEA detection | YES (different sensor) | YES (strong) |
| DEA Hotspots VIIRS + FIRMS VIIRS (same overpass) | NO (same observation) | NO |
| FIRMS VIIRS + FIRMS MODIS (different sensors, same time) | YES | YES |

---

## 3. Event Lifecycle

### 3.1 States

```
PROVISIONAL -> LIKELY -> CONFIRMED -> MONITORING -> CLOSED
     |            |
     +-> RETRACTED +-> RETRACTED
```

**PROVISIONAL:** First detection. Report immediately with low confidence. Include lat/lon, time, sensor, anomaly magnitude. This is the "we see something, it might be fire" state.

**LIKELY:** Passed persistence test (2/3 frames) OR received independent confirmation (GK-2A detection). Upgrade report. This is "we're fairly sure this is fire."

**CONFIRMED:** LEO sensor confirmation (VIIRS/MODIS match) OR 3/3 frame persistence with growing intensity. Upgrade report. This is "this is fire."

**MONITORING:** Fire confirmed, providing characterization updates every 15 minutes for 12 hours per Rule 9. Active tracking.

**RETRACTED:** Failed persistence (detected in 1 frame, absent in next 2), no LEO confirmation within 6 hours. Mark as retracted in next report. NOT a false positive if we clearly labeled it PROVISIONAL.

**CLOSED:** 12 hours elapsed since last detection, or fire extinguished (no detections for multiple VIIRS passes).

### 3.2 State Transition Rules

```
PROVISIONAL -> LIKELY:
  - Persistent in 2/3 AHI frames (20-min window), OR
  - GK-2A independent detection within spatial match radius

PROVISIONAL -> RETRACTED:
  - Not detected in next 2 AHI frames AND
  - No LEO confirmation within 6 hours

LIKELY -> CONFIRMED:
  - VIIRS/MODIS detection within spatial match radius, OR
  - Persistent 3/3 AHI frames AND growing BT anomaly

LIKELY -> RETRACTED:
  - Detected in 2 frames then absent in 3+ frames AND
  - No LEO confirmation within 6 hours

CONFIRMED -> MONITORING:
  - Automatic transition after first characterization update

MONITORING -> CLOSED:
  - 12 hours since last detection, OR
  - No detections in 3+ consecutive VIIRS passes
```

### 3.3 Key Insight from All-Teams Call

"Low confidence detections still count if correct." This means:
- PROVISIONAL detections that turn out to be real fires score points
- Retractions of false positives are not heavily penalized as long as they were clearly labeled as provisional
- Speed matters more than waiting for certainty

---

## 4. Cross-Resolution Combination

### 4.1 The Resolution Hierarchy

Our core sensors span different resolutions:

| Sensor | Pixel Size | Fire Localization | Min Detectable |
|--------|-----------|-------------------|----------------|
| Himawari AHI | 3-4 km | ~3 km uncertainty | ~1,000-4,000 m2 |
| VIIRS I-band (via DEA/FIRMS) | 375 m-1.6 km | ~0.5 km uncertainty | ~100-500 m2 |

When a 3 km Himawari pixel detects a fire, we know the fire is somewhere within ~13 km2. A VIIRS detection narrows this to ~0.14 km2.

### 4.2 Spatial Matching Algorithm

**Step 1: Buffer the coarser detection by its uncertainty radius**

```
AHI detection at (lat, lon):
  buffer_radius = sqrt((pixel_size/2)^2 + geoloc_error^2)
  At NSW: buffer_radius ~ 2000 m (pixel ~3500 m, geoloc ~1000 m)
```

**Step 2: Search for finer-resolution detections within the buffer**

```
For each DEA/FIRMS detection:
  distance = haversine(AHI_lat, AHI_lon, detection_lat, detection_lon)
  IF distance < buffer_radius:
    MATCH (candidate for association)
```

**Step 3: Temporal window check**

```
AHI -> VIIRS (DEA Hotspots): max offset = 3 hours (covers overpass gap)
AHI -> FIRMS NRT:            max offset = 6 hours (FIRMS can be delayed)
```

**Step 4: Location refinement on match**

When a finer-resolution sensor confirms a coarser detection:
- Update the event centroid to the finer-resolution position
- Shrink the uncertainty circle to the finer sensor's uncertainty
- Log the multi-sensor match in the event evidence trail

### 4.3 Handling Conflicting Detections

Scenario: AHI detects fire at location A, but the nearest VIIRS detection is 4 km away at location B.

Decision tree:
1. If distance(A, B) < AHI_buffer + VIIRS_buffer (~2.5 km): MATCH (same fire, use VIIRS position)
2. If distance(A, B) > combined buffers: TWO SEPARATE EVENTS (fire may have spread, or multiple ignitions)
3. If AHI detects but VIIRS does not (within buffer): MAINTAIN AHI detection, do not reject. Fire may be below VIIRS threshold at that scan angle.

---

## 5. False Positive Control (<5% Target)

### 5.1 Layered Filtering (Core MVP -- 4 Layers)

Each filter is applied in sequence. The order is designed so that cheap, high-impact filters run first:

```
Layer 1: Static masks (pre-computed, ~0 runtime cost)
  - Land/water mask (reject water pixels except known gas flares)
  - Urban mask (raise thresholds by +5 K for urban pixels)
  - Industrial site mask (reject known persistent hot spots from FIRMS STA)
  - VZA mask (reject pixels with VZA > 65 deg)

Layer 2: Geometric filters (fast computation)
  - Sun glint angle check (reject if glint angle < 10-12 deg)
  - Solar zenith angle (apply day/night thresholds correctly)

Layer 3: Contextual detection (Pass 1, ~1 second)
  - Background statistics + adaptive thresholds
  - This is where most false positives are eliminated

Layer 4: Temporal persistence (~10-20 minutes for marginal detections)
  - Require 2/3 frames for LIKELY confidence
  - Sun glint shifts between frames; real fires persist
  - Eliminates ~80% of remaining single-frame false positives
```

### 5.2 Optional Additional Layers (Week 3)

```
Layer 5: ML classifier (Pass 2, ~0.5 second) -- OPTIONAL
  - Trained on known false positive types
  - Catches complex patterns (cloud edges, partial cloud, mixed terrain)

Layer 6: Cross-sensor confirmation (hours) -- inherent in confidence ladder
  - VIIRS/MODIS cross-check via DEA/FIRMS
  - False positives at this stage are extremely rare
```

### 5.3 Expected False Positive Rates by Layer

| After Layer | Estimated FP Rate | FP per Scan (NSW, 100K pixels) |
|-------------|-------------------|-------------------------------|
| Raw candidates (no filtering) | ~1% | ~1,440 |
| After Layer 3 (contextual) | ~0.1% | ~144 |
| After Layer 4 (temporal persistence) | ~0.003% | ~4 |
| After Layer 5 (ML, if implemented) | ~0.0006% | <1 |

Target: <5% false positive rate among REPORTED fires. If we report ~5-20 real fires per day, we need fewer than 1 false positive per day. The layered approach should achieve this.

### 5.4 Emergency FP Reduction

If our false positive rate exceeds 5% during the competition:

1. **Raise persistence threshold:** Require 3/3 frames instead of 2/3 (20 min delay increase)
2. **Night-only geostationary alerting:** Suppress daytime AHI-only detections (eliminate sun glint, hot soil)
3. **Require VIIRS confirmation:** Only report fires confirmed by at least one LEO sensor (delays reports by hours but virtually eliminates FPs)
4. **Manual review:** Have a team member review each alert before submission (not scalable but last resort)

---

## 6. Event Store

### 6.1 Keep It Simple

DynamoDB or SQLite. Either is sufficient for competition scale.

**Required fields per event:**

```python
{
    "event_id": "uuid",
    "status": "PROVISIONAL",  # PROVISIONAL/LIKELY/CONFIRMED/MONITORING/RETRACTED/CLOSED
    "first_detection_time": "2026-04-10T14:23:00+10:00",
    "latest_detection_time": "2026-04-10T14:43:00+10:00",
    "centroid_lat": -33.85,
    "centroid_lon": 151.21,
    "location_uncertainty_m": 2000,
    "confidence_level": 1,   # 1-4 per confidence ladder
    "detections": [],         # Array of individual detections with provenance
    "reported": false,        # Has this been included in a judge-facing report?
    "report_history": [],     # Timestamps of when this was reported and at what level
}
```

### 6.2 What We Skip

- Full Bayesian log-odds tracking (replaced by rule-based ladder)
- Complex geometry (alpha hulls, perimeters) -- use simple buffer circles around detection points
- FRP estimation (decorative at geostationary resolution; honest about limitations)
- Rate of spread estimation (unreliable from sparse hotspot centroids)

### 6.3 Event Association Rules

When a new detection arrives:

1. **Spatial search:** Find all ACTIVE events within matching radius
   - AHI detection: search radius = 5 km
   - VIIRS/FIRMS detection: search radius = 2 km

2. **Temporal filter:** Event must have had a detection within the last 5 days

3. **Association:** If match found, add detection to nearest event. Update centroid, uncertainty, confidence.

4. **Creation:** If no match, create new event at PROVISIONAL.

5. **Merge check:** After association, check if any two events' uncertainty circles overlap by >50%. If so, merge them.

---

## 7. Characterization (Honest and Simple)

Every 15 minutes, output for each ACTIVE+ event:

| Field | What We Provide | Method |
|-------|----------------|--------|
| Location (lat/lon) | Best available sensor position | Centroid of detections, refined by VIIRS if available |
| Location uncertainty | Circle radius in meters | Based on best sensor resolution |
| Size estimate | "Approximately X km2" | Number of hot pixels x pixel area |
| Intensity | Qualitative: low/moderate/high | Based on BT anomaly magnitude |
| Direction of spread | Only if 3+ sequential detections show movement | Bearing from first to latest centroid |
| Rate of spread | Only if 3+ sequential detections available | Distance / elapsed time |
| Confidence | PROVISIONAL/LIKELY/CONFIRMED | Rule-based ladder |
| Contributing sensors | List | From provenance records |

**What we explicitly do NOT provide:**
- Fire perimeter polygons (use points with uncertainty circles instead)
- Quantitative FRP from geostationary data (too uncertain at 2 km pixels)
- Rate of spread from fewer than 3 detections
- Any claim labeled as "measured" -- everything is "estimated"

---

## 8. OGC Export

### 8.1 Format

GeoJSON (OGC standard since 2016). Each fire event becomes a Feature:

```json
{
  "type": "Feature",
  "geometry": {"type": "Point", "coordinates": [151.2, -33.8]},
  "properties": {
    "event_id": "abc-123",
    "detection_time": "2026-04-10T14:23:00+10:00",
    "confidence": "CONFIRMED",
    "confidence_level": 3,
    "sensor_sources": ["Himawari-9 AHI", "VIIRS NOAA-21"],
    "location_uncertainty_m": 500,
    "intensity_estimate": "moderate",
    "size_estimate_km2": 0.5,
    "status": "MONITORING"
  }
}
```

This can be ingested into ArcGIS Online directly.

### 8.2 Daily Report

Generated daily per XPRIZE template (due 20:00 AEST). Includes:
- All detected fires with coordinates, timestamps, confidence levels
- Sensor sources for each detection
- GeoJSON attachment for ArcGIS ingestion
- Summary statistics (fires detected, false positive rate, system uptime)

---

## 9. Validation Plan

### 9.1 Historical Replay Testing

**Dataset: April periods 2020-2025 (NSW)**
- Focus on April conditions (autumn, NSW-specific)
- Compare detected events against FIRMS reference
- Compute detection rate, delay, false positive rate, spatial accuracy

**Methodology:**
1. Replay Himawari data through the pipeline in chronological order
2. Inject realistic data latency (7-15 min for Himawari, 17 min for DEA Hotspots)
3. Evaluate alert policy (immediate vs held) for FP/true positive tradeoff
4. Tune thresholds for NSW April conditions

### 9.2 Pre-Competition Live Testing

During Week 2-3, run the system live on current Himawari data:
- Monitor real detections against DEA Hotspots ground truth
- Verify portal shows detections correctly
- Test GeoJSON export and ArcGIS import
- Measure actual end-to-end latency
