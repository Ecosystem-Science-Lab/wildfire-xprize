# Multi-Sensor Data Fusion for Wildfire Detection

## Scope and Relevance to XPRIZE (NSW, Australia -- April 2026)

This domain brief covers how to combine detections from multiple satellite sensors into a unified wildfire detection pipeline that detects fires quickly while keeping false positives below 5%. The competition context dictates:

- **Himawari-9 AHI** is the primary geostationary sensor (10-min full disk, 2 km fire bands) -- the fast trigger layer
- **VIIRS** (S-NPP, NOAA-20, NOAA-21) provides 375 m active fire detections ~4x/day at NSW latitudes -- the refine/confirm layer
- **MODIS** (Terra, Aqua) provides 1 km fire detections ~2x/day -- supplemental confirmation
- **Landsat 8/9 OLI** (30 m, ~16-day revisit per satellite, 8 combined) and **Sentinel-2** (20 m SWIR, ~5-day revisit) -- high-res confirmation for small fires
- **FIRMS NRT** provides cross-checking against the global operational consensus

## Architecture: Trigger-Refine-Confirm Pipeline

The pipeline is a three-stage cascade that trades latency against certainty:

```
Stage 1: TRIGGER (Geostationary -- seconds to minutes)
  Input: Himawari AHI Band 7 (3.9 um) + Band 14 (11.2 um), every 10 min
  Method: Per-pixel thermal anomaly detection vs diurnal baseline
  Output: Candidate event with uncertainty ellipse (~2 km radius)
  Latency: <15 min from observation

Stage 2: REFINE (Temporal persistence -- 10-30 min)
  Input: 2-3 consecutive AHI scans of the same candidate
  Method: Require persistence OR increasing intensity across frames
  Output: Refined candidate with confidence upgrade
  Filter: Reject transients (sun glint, cloud edge heating)

Stage 3: CONFIRM (Cross-sensor -- minutes to hours)
  Input: VIIRS/MODIS overpass data, Landsat/Sentinel-2 if available
  Method: Spatial matching with resolution-aware uncertainty
  Output: Confirmed fire event with high-confidence score
  Bonus: FIRMS cross-check for independent corroboration
```

### Why Three Stages?

Single-sensor approaches suffer from the speed-accuracy tradeoff:
- **Geostationary alone**: Fast (10 min) but coarse (2 km pixels). Commission errors from sun glint, hot bare ground, cloud edges, industrial heat. Without filtering, false positive rates can exceed 10%.
- **Polar-orbiting alone**: Better spatial resolution (375 m VIIRS) but infrequent (~4 passes/day for NSW). Misses rapid onset fires between passes.
- **High-res alone**: Excellent detail (30 m) but revisit times of 5-16 days make real-time detection impossible.

The cascade lets geostationary data provide speed while polar-orbiting and high-res data provide accuracy.

## Stage 1: Geostationary Trigger -- Detail

### Per-Pixel Diurnal Baseline

Each land pixel has a characteristic thermal signature that varies with time of day, season, land cover, and weather. Fire detection isolates deviations from this baseline.

**Approaches (increasing sophistication):**

1. **Contextual (spatial)**: Compare pixel to its neighbors in the same frame. Used by MOD14, ABI FDC. Fast, no historical data needed.
   - Thresholds: BT_3.9 > BT_3.9_mean + 3*sigma AND BT_diff > BT_diff_mean + 3*sigma

2. **Multi-temporal (Kalman filter)**: Model each pixel's diurnal temperature cycle (DTC) and detect anomalies as deviations from the predicted state. Detects ~60-80% more fires than contextual alone, but higher false alarm rate and requires full-day history.

3. **Hybrid contextual + temporal**: Use spatial context for the first scan of the day, transition to temporal after sufficient history accumulates. This is our recommended approach.

**Concrete thresholds (adapted from MOD14/ABI FDC for AHI):**

| Test | Daytime | Nighttime |
|------|---------|-----------|
| Absolute MIR threshold | BT_3.9 > 360 K | BT_3.9 > 320 K |
| MIR anomaly vs context | BT_3.9 > mean + 3.5*sigma | BT_3.9 > mean + 3.5*sigma |
| BTD anomaly vs context | BTD > BTD_mean + 3.5*sigma_BTD | BTD > BTD_mean + 3.5*sigma_BTD |
| BTD absolute minimum | BTD > BTD_mean + 6 K | BTD > BTD_mean + 6 K |
| Sun glint block zone | Glint angle < 10 deg | N/A |

### Uncertainty Ellipse

A geostationary detection localizes the fire to a pixel footprint, not a point. The uncertainty ellipse captures:
- **Pixel size**: 2 km at nadir, growing with view zenith angle (VZA). At NSW latitudes (~33 S), VZA from Himawari is ~30-35 deg, giving effective pixel size ~2.5-3 km.
- **Geolocation error**: Typically 0.5-1.5 km for geostationary data.
- **Combined uncertainty**: Model as an ellipse with semi-major axis = sqrt(pixel_size^2 + geoloc_error^2), oriented along the scan direction.

## Stage 2: Temporal Refinement -- Detail

### Persistence Check

Require the candidate to appear in at least 2 of 3 consecutive AHI scans (20-30 min window). This eliminates:
- **Transient sun glint**: Changes with solar geometry between scans
- **Cloud-edge artifacts**: Clouds move, exposing/hiding warm surfaces
- **Sensor noise**: Random hot pixels don't persist

### Intensity Trend

If the thermal anomaly is increasing across frames (BT_3.9 rising, BTD growing), upgrade confidence even if it only appears in 2 frames. A growing fire is strong evidence of a real detection.

### Temporal Filtering (from GOES ABI FDC approach)

The ABI FDC algorithm defines "temporally filtered" fire pixels as those with co-located detections within a 12-hour window. Each fire category has a temporal equivalent:
- Class 10 (instantaneous good quality) -> Class 30 (temporally filtered good quality)
- Class 11 (saturated) -> Class 31 (temporally filtered saturated)
- Classes 13-15 (decreasing confidence) -> Classes 33-35 (temporally filtered equivalents)

For our pipeline, adapt this to a shorter window (30 min = 3 AHI scans) for rapid confirmation.

## Stage 3: Cross-Sensor Confirmation -- Detail

### Spatial Matching Across Resolutions

The core challenge: matching a 2 km geostationary detection to a 375 m VIIRS detection or a 30 m Landsat pixel.

**Resolution hierarchy:**

| Sensor | Fire Pixel Size | Uncertainty Radius | Min Detectable Fire |
|--------|----------------|-------------------|-------------------|
| Himawari AHI | 2-3 km | ~3 km | ~4,000 m^2 |
| MODIS | 1-5 km (scan-dependent) | ~1.5 km | ~1,000 m^2 |
| VIIRS I-band | 375 m - 1.6 km | ~0.5 km | ~100-500 m^2 |
| Landsat OLI | 30 m | ~50 m | ~4 m^2 |
| Sentinel-2 | 20 m | ~20 m | ~4 m^2 |

**Matching algorithm:**
1. Buffer the geostationary detection point by its uncertainty radius
2. Query polar-orbiting detections within that buffer
3. If a VIIRS/MODIS detection falls within the buffer, confirm with high confidence
4. If a Landsat/Sentinel-2 thermal anomaly falls within the buffer, confirm with very high confidence
5. If no polar-orbiting detection is available within 6 hours, maintain the geostationary detection at its refined confidence level

### Temporal Windows for Cross-Sensor Matching

| Sensor Pair | Maximum Time Offset | Rationale |
|------------|-------------------|-----------|
| AHI -> VIIRS | +/- 3 hours | Fire may grow/shift; VIIRS passes are infrequent |
| AHI -> MODIS | +/- 3 hours | Same as VIIRS |
| AHI -> Landsat | +/- 6 hours | Very infrequent; any temporal corroboration valuable |
| VIIRS -> MODIS | +/- 30 min | Often near-simultaneous (similar orbits) |
| VIIRS -> FIRMS NRT | +/- 4 hours | FIRMS has 3-hour processing latency |

## Confidence Scoring

### Bayesian Framework

Combine evidence from multiple sources using log-odds:

```
log_odds(fire) = prior_log_odds
    + LLR_geostationary      (from AHI anomaly strength)
    + LLR_temporal            (from persistence across frames)
    + LLR_polar_orbiting      (from VIIRS/MODIS detection or absence)
    + LLR_high_res            (from Landsat/Sentinel-2)
    + LLR_context             (from land use, season, fire weather)
    - penalty_false_positive  (from known FP sources: glint, industry, etc.)
```

Where LLR = log-likelihood ratio for each evidence source. Convert back to probability:
```
P(fire) = sigmoid(log_odds(fire))
```

### Confidence Tiers (for output)

| Tier | P(fire) Range | Action | Typical Evidence |
|------|--------------|--------|-----------------|
| **High** | > 0.85 | Alert immediately | AHI persistent + VIIRS confirm |
| **Nominal** | 0.50 - 0.85 | Alert with caveat | AHI persistent, no polar confirm yet |
| **Low** | 0.20 - 0.50 | Monitor, do not alert | AHI single frame, moderate anomaly |
| **Rejected** | < 0.20 | Discard | Failed persistence or FP filter |

### FIRMS Confidence Mapping

FIRMS assigns confidence differently per sensor:
- **MODIS**: Numeric 0-100%, where 0-29% = low, 30-79% = nominal, 80-100% = high
- **VIIRS**: Categorical low/nominal/high based on:
  - Low: sun glint areas, temperature anomaly < 15 K in MIR
  - Nominal: free of glint, temperature anomaly > 15 K
  - High: saturated MIR pixels (day or night)

## False Positive Sources and Mitigation

| Source | Detection Signature | Mitigation |
|--------|-------------------|-----------|
| **Sun glint** | Hot MIR during day, changes with geometry | Glint angle < 10 deg block; 2-frame persistence (glint shifts) |
| **Hot bare ground** | Elevated MIR, desert/arid, midday peak | Land cover mask; BTD threshold (ground heats MIR and TIR, fire heats MIR >> TIR) |
| **Industrial heat** | Persistent year-round hot spots | Static thermal anomaly mask (FIRMS STA); 5+ detections on 400 m grid = static |
| **Volcanic activity** | Persistent, geographically fixed | Volcano database overlay; persistence > 30 days = volcanic |
| **Cloud edges** | Warm/cold boundary artifacts | Cloud mask dilation; temporal check (clouds move, fire does not) |
| **Sensor noise / SAMA** | Spurious hot pixels in South Atlantic Magnetic Anomaly | SAMA region mask; VIIRS already filters low-conf nighttime in SAMA region |
| **Burn scars** | Residual heat post-fire | BTD check (burn scars heat MIR less than active fire); temporal decay check |

## Event Tracking

### State Machine

A fire event progresses through states:

```
CANDIDATE -> ACTIVE -> GROWING -> STABLE -> DECLINING -> EXTINGUISHED
    |                                                         |
    +---> REJECTED (false positive filter)                    +---> ARCHIVED
```

### Event Association Rules

When a new detection arrives:
1. **Spatial search**: Find all active events within a configurable radius (default: 5 km for geostationary, 2 km for VIIRS)
2. **Temporal search**: Event must have had a detection within the last 5 days (following FEDS algorithm)
3. **If match found**: Update existing event (extend geometry, update confidence, record new detection)
4. **If no match**: Create new event in CANDIDATE state
5. **Merge check**: If two active events' geometries overlap, merge them

### Geometry Representation

Use alpha hulls (not convex hulls) around detection points to model fire shape. Alpha hulls better capture:
- Irregular fire perimeters
- Multiple fire heads
- Gaps within the fire footprint

## Operational Systems Reference

### FIRMS (NASA)
- Global NRT fire data from MODIS + VIIRS + Landsat
- 3-hour latency globally, real-time for US/Canada
- REST API with CSV/JSON output
- Static thermal anomaly mask for industrial/volcanic filtering

### GWIS (Copernicus/JRC)
- Eight daily updates from MODIS + VIIRS
- Integrates fire danger forecasts, burnt area, emissions
- Harmonized multi-sensor active fire dataset including geostationary (Himawari, GOES, Meteosat)

### HMS (NOAA)
- Automated fire detection + human analyst quality control
- Analysts review every automated detection, delete false alarms, add missed fires
- Uses land use masks, power plant locations, stable night lights for FP filtering
- Key insight: even sophisticated algorithms need human QC for operational reliability

### OroraTech
- Commercial system fusing 35+ satellite sources
- < 10 min alert latency with geostationary; < 30 min global coverage
- On-board processing for LEO satellites (reduces downlink latency)
- Demonstrates viability of multi-sensor fusion at operational scale

## Key Parameters Summary

| Parameter | Recommended Value | Source/Rationale |
|-----------|------------------|-----------------|
| AHI scan interval | 10 min | Full disk cadence |
| Persistence window | 2 of 3 consecutive scans (20-30 min) | Balance speed vs FP reduction |
| Cross-sensor time window | +/- 3 hours (VIIRS/MODIS) | Covers overpass timing gaps |
| Spatial match radius (AHI) | 3 km | Pixel size + geolocation error |
| Spatial match radius (VIIRS) | 1 km | Pixel size + geolocation error |
| Event inactivity timeout | 5 days | FEDS algorithm standard |
| Min confidence for alert | 0.50 (nominal) | Below 5% FP target |
| Sun glint block angle | < 10 deg | ABI FDC standard |
| Static anomaly threshold | 5+ detections/year on 400 m grid | FIRMS STA mask |
| MIR saturation temperature (VIIRS I4) | ~358-367 K | Sensor-dependent; auto high-confidence |
