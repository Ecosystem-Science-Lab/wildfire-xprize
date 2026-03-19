# Concept of Operations (CONOPS)
# NAU Wildfire Detection System

**Team:** NAU Ecosystem Science Lab (Northern Arizona University)
**Competition:** XPRIZE Wildfire Track A Finals, Round 3
**Document Version:** 1.0
**Date:** March 19, 2026
**Finals Application Deadline:** March 31, 2026

---

## 1. Executive Summary

**Team Name:** NAU Ecosystem Science Lab
**System Name:** NAU Wildfire Detection System
**Primary Affiliation:** Northern Arizona University, School of Informatics, Computing, and Cyber Systems

The NAU Wildfire Detection System is a satellite-based wildfire detection and intelligence platform designed for the XPRIZE Track A Finals in New South Wales, Australia (April 9--21, 2026). The system provides continuous, automated fire detection across the full ~800,000 km^2 NSW target area by combining custom processing of Himawari-9 AHI geostationary imagery with confirmation from polar-orbiting VIIRS/MODIS sensors via DEA Hotspots and NASA FIRMS.

Our key differentiator is **dual-mode detection from public geostationary data**: a spatial contextual algorithm provides immediate detection of fires larger than ~1,000 m^2 from any single 10-minute Himawari-9 frame, while a temporal CUSUM (Cumulative Sum) algorithm with Bayesian probability estimation accumulates evidence across frames to detect smaller fires (200--500 m^2) that are invisible to single-frame analysis. Both algorithms feed a unified event store with transparent confidence tracking and provenance-aware multi-source fusion.

The system operates entirely on publicly available satellite data sources, requires no commercial subscriptions, and deploys as a self-contained Docker container on AWS infrastructure. The judge-facing portal provides a real-time interactive map with automatic refresh, OGC-compliant GeoJSON export, and daily reporting automation.

---

## 2. System Overview

### 2.1 Architecture

```
+===========================================================================+
|                        SATELLITE DATA SOURCES                             |
|                                                                           |
|  +------------------+   +------------------+   +------------------+       |
|  | Himawari-9 AHI   |   | VIIRS (NOAA-21,  |   | MODIS (Aqua,    |       |
|  | 10-min cadence   |   |  S-NPP, NOAA-20) |   |  Terra)         |       |
|  | 2km MWIR/TIR     |   |  375m, ~6 pass/d |   |  1km, ~4 pass/d |       |
|  +--------+---------+   +--------+---------+   +--------+---------+       |
|           |                      |                      |                 |
+===========|======================|======================|=================+
            |                      |                      |
            v                      v                      v
+===========================================================================+
|                         DATA INGESTION LAYER                              |
|                                                                           |
|  +------------------+   +------------------+   +------------------+       |
|  | AWS S3 (NODD)    |   | DEA Hotspots WFS |   | NASA FIRMS API  |       |
|  | Poll every 2 min |   | Poll every 5 min |   | Poll every 5 min|       |
|  | B07 + B14 segs   |   | GeoJSON parsing  |   | CSV parsing     |       |
|  +--------+---------+   +--------+---------+   +--------+---------+       |
|           |                      |                      |                 |
+===========|======================|======================|=================+
            |                      |                      |
            v                      |                      |
+===========================+      |                      |
|   HIMAWARI PROCESSING     |      |                      |
|   PIPELINE                |      |                      |
|                           |      |                      |
|  +---------------------+  |      |                      |
|  | Decode HSD → BT     |  |      |                      |
|  | (B07 3.9um, B14     |  |      |                      |
|  |  11.2um)            |  |      |                      |
|  +----------+----------+  |      |                      |
|             v              |      |                      |
|  +---------------------+  |      |                      |
|  | Masks: Cloud, Water,|  |      |                      |
|  | Industrial, NSW bbox|  |      |                      |
|  +----------+----------+  |      |                      |
|             v              |      |                      |
|  +---------------------+  |      |                      |
|  | MODE 1: Contextual  |  |      |                      |
|  | Fire Detection      |  |      |                      |
|  | (instant, >=1000m2) |  |      |                      |
|  +----------+----------+  |      |                      |
|             |              |      |                      |
|             v              |      |                      |
|  +---------------------+  |      |                      |
|  | MODE 2: CUSUM       |  |      |                      |
|  | Temporal Detection   |  |      |                      |
|  | (accumulated,        |  |      |                      |
|  |  200-500m2)         |  |      |                      |
|  +----------+----------+  |      |                      |
|             |              |      |                      |
|             v              |      |                      |
|  +---------------------+  |      |                      |
|  | Temporal Persistence |  |      |                      |
|  | Filter (2/3 frames) |  |      |                      |
|  +----------+----------+  |      |                      |
|             |              |      |                      |
+=============|==============+      |                      |
              |                     |                      |
              v                     v                      v
+===========================================================================+
|                       EVENT MANAGEMENT LAYER                              |
|                                                                           |
|  +------------------------------------------------------------------+    |
|  |                    EVENT STORE (SQLite)                           |    |
|  |  - Spatial deduplication (2-5km matching radius)                 |    |
|  |  - Provenance tracking (1 observation = 1 evidence)              |    |
|  |  - Confidence ladder: PROVISIONAL → LIKELY → CONFIRMED →        |    |
|  |    MONITORING → CLOSED (+ RETRACTED)                             |    |
|  +------------------------------------------------------------------+    |
|                                                                           |
+==================================|========================================+
                                   |
                                   v
+===========================================================================+
|                           OUTPUT LAYER                                    |
|                                                                           |
|  +------------------+   +------------------+   +------------------+       |
|  | Judge Portal     |   | GeoJSON Export   |   | Daily Reports   |       |
|  | Leaflet.js map   |   | OGC RFC 7946    |   | 20:00 AEST      |       |
|  | Auto-refresh     |   | ArcGIS-ready    |   | Email delivery  |       |
|  | CUSUM heatmap    |   |                  |   |                 |       |
|  +------------------+   +------------------+   +------------------+       |
|                                                                           |
+===========================================================================+
```

### 2.2 Data Sources

| Source | Sensor | Role | Coverage | Resolution | Cadence |
|--------|--------|------|----------|------------|---------|
| **Himawari-9 AHI** | MWIR (3.9 um) + TIR (11.2 um) | Primary continuous detection + characterization | Full NSW, 24/7 | 2 km (nadir), 3--4 km at NSW latitudes | Every 10 min |
| **VIIRS** (via DEA Hotspots) | I4 (3.74 um) | Primary confirmation | NSW when overpass aligns | 375 m | ~6 passes/day |
| **VIIRS/MODIS** (via FIRMS API) | Multiple thermal bands | Safety net / backup | NSW | 375 m--1 km | 30 min -- 3 hr latency |

All data sources are publicly available and legally obtained. No commercial satellite subscriptions are required.

### 2.3 Detection Modes

The system employs two complementary detection algorithms that run simultaneously on each Himawari-9 observation:

1. **Contextual Fire Detection (Mode 1):** Single-frame spatial anomaly detection adapted from the VIIRS VNP14IMG and GOES ABI FDC algorithms. Identifies fire pixels by comparing MIR brightness temperature and MIR-TIR brightness temperature difference against adaptive background statistics. Provides immediate detection of fires larger than approximately 1,000 m^2.

2. **CUSUM Temporal Detection (Mode 2):** Per-pixel Bayesian CUSUM change detection over a Kalman-filtered harmonic diurnal model with BT14 weather correction. Accumulates evidence of persistent positive BTD anomalies across multiple frames to detect fires as small as 200--500 m^2, which are below the single-frame detection threshold.

### 2.4 Processing Pipeline Summary

| Stage | Processing | Latency |
|-------|-----------|---------|
| S3 data availability | Himawari observation + JMA/NOAA relay | ~13 min after observation |
| Download NSW segments (B07 + B14) | Two S3 GETs | ~1--3 s |
| Decode HSD to brightness temperature | `satpy` or custom decoder | ~0.5 s |
| Cloud, water, industrial masking | Pre-computed + fast threshold | ~0.2 s |
| Contextual fire detection (Mode 1) | Vectorized numpy/scipy | ~1 s |
| CUSUM temporal detection (Mode 2) | Vectorized numpy | ~0.5 s |
| Temporal persistence filter | Rolling buffer check | ~0.01 s |
| Merge + ingest to event store | Deduplication + confidence update | ~0.5 s |
| **Total processing latency** | | **~3--6 s** |
| **End-to-end (observation to alert)** | | **~14 min** |

---

## 3. Detection Methodology

### 3a. Contextual Fire Detection (Mode 1)

**Algorithm:** Modified VNP14IMG-style contextual detection adapted for the spectral response and viewing geometry of Himawari-9 AHI at NSW latitudes.

**Spectral Bands:**
- Band 07 (3.9 um, MIR) -- primary fire-sensitive channel
- Band 14 (11.2 um, TIR) -- background temperature and cloud masking

**Processing Steps:**

1. **Absolute threshold screening:** Pixels with BT_B07 >= 400 K (sensor saturation) are classified as HIGH confidence fires immediately, bypassing all subsequent tests. Extreme anomalies (BT_B07 > 320 K nighttime, > 360 K daytime) are also classified as HIGH confidence.

2. **Candidate selection:** Pixels passing minimum thresholds (nighttime: BT_B07 > 290 K AND BTD > 10 K; daytime: BT_B07 > 315 K AND BTD > 22 K) enter the contextual analysis. These thresholds are tuned for NSW April (autumn) conditions.

3. **Background characterization:** For each candidate, statistics (mean, standard deviation) of BT_B07, BTD, and BT_B14 are computed from valid non-fire, non-cloud, non-water neighbor pixels in an adaptive window (11x11 expanding to 31x31). A minimum of 25% valid background pixels is required.

4. **Contextual fire tests (all must pass):**
   - BT_B07 exceeds background mean + N * sigma (N = 3.5 daytime, 3.0 nighttime)
   - BTD exceeds background mean + N * sigma
   - BTD exceeds background mean + floor (10 K daytime, 8 K nighttime)
   - BT_B07 exceeds absolute floor (310 K daytime, 295 K nighttime)
   - BT_B14 longwave contextual test (daytime only; rejects MIR-only anomalies from reflected sunlight)

5. **Confidence assignment:**
   - HIGH: Saturated or absolute-threshold fires
   - NOMINAL: Passes all contextual tests with strong BTD anomaly (> 15 K above background)
   - LOW: Passes contextual tests with moderate anomaly, or in sun glint zone, or near industrial site

**Sun Glint Handling:** Glint angle is computed from solar/satellite geometry. Pixels with glint angle < 12 degrees receive a confidence downgrade (NOMINAL to LOW) rather than outright rejection, so that real fires near water bodies are not missed.

**Static Masks:**
- Water mask: Global-land-mask (1 km ocean) + GSHHS (3 km inland water bodies)
- Industrial mask: 24 known thermal hotspot sites in NSW (power stations, steelworks, smelters, mines) with 4 km buffer radius -- detections are confidence-downgraded, not rejected

**Expected Performance:** Detects fires larger than approximately 1,000 m^2 (0.1 ha) in a single 10-minute frame under clear-sky conditions. Larger fires (> 5,000 m^2) are detected with HIGH confidence.

### 3b. CUSUM Temporal Detection (Mode 2)

**Algorithm:** Dual-rate Bayesian CUSUM with 6-parameter Kalman-filtered diurnal model.

**Background Model:**
Each pixel maintains a harmonic model of expected BTD as a function of local solar time, plus a BT14 anomaly covariate for weather correction:

```
BTD_predicted = T_mean + a1*cos(wt) + b1*sin(wt) + a2*cos(2wt) + b2*sin(2wt) + beta*(BT14 - BT14_ema)
```

The 6 parameters [T_mean, a1, b1, a2, b2, beta] are continuously estimated via a Kalman filter. The beta coefficient is the key innovation: when a heat wave raises the background land surface temperature (increasing BT14), the model predicts the corresponding BTD shift and keeps residuals flat. Fires raise BTD without proportional BT14 increases, so the residual stays positive and CUSUM accumulates.

**Change Detection:**
Normalized residuals (z = innovation / sigma_predicted) are fed into dual-rate CUSUM statistics:
- **S_slow** (k=0.5, h=12): Tuned for small, slowly developing fires. Detects fires of 200--500 m^2 over 20--60 minutes.
- **S_fast** (k=1.5, h=5): Tuned for large, rapidly developing fires. Confirms fires within minutes.

**Bayesian Probability:**
The CUSUM S statistic is converted to a posterior fire probability via:

```
P(fire | observations) = 1 / (1 + (1/prior_odds) * exp(-alpha * S_max))
```

This replaces hard detection thresholds with smooth probability estimates. Pixels exceeding P(fire) >= 0.5 are flagged as fire candidates. The Kalman gain is weighted by (1 - P(fire)), softly freezing the background model for pixels with high fire probability (protecting against fire contamination of the diurnal model).

**False Alarm Mitigation:**
- BT14 rejection: Candidates where BT14 itself is anomalously warm (z_BT14 > 3.0) are suppressed as weather-driven, unless extreme (z_BT14 > 6.0, possible large fire heating both channels).
- Adjacency filter: Requires at least one neighboring pixel to also be flagged (reduces noise-driven isolated detections).
- Water and industrial suppression mask applied to CUSUM candidates.

**Pre-Initialization:** The Kalman filter requires approximately 4 weeks of clear-sky observations to converge on stable diurnal model parameters. The system will be pre-initialized with Himawari-9 archive data from approximately March 12 through April 8, 2026, ensuring all NSW pixels have converged background models before competition start.

**Expected Performance:** Detects fires of 200--500 m^2 within 20--60 minutes under clear-sky conditions. Provides a per-pixel fire probability heatmap that enables detection of sub-threshold fires invisible to single-frame contextual analysis.

### 3c. Detection Merging and Confirmation

When both contextual and CUSUM algorithms flag the same pixel in the same frame:
- The contextual detection is retained (typically higher confidence).
- If the contextual detection was LOW confidence, it is upgraded to NOMINAL (corroboration bonus).
- CUSUM-only detections (no contextual match) are added as LOW confidence detections.

**Multi-Source Confirmation:**
- DEA Hotspots (VIIRS) and FIRMS API are polled every 5 minutes.
- New LEO detections are spatially matched against existing Himawari events (matching radius: 2--5 km depending on sensor resolution).
- A VIIRS confirmation of a Himawari detection upgrades the event to CONFIRMED status.

**Provenance Rules (prevents double-counting):**
- One satellite observation = one evidence contribution, regardless of how many processing pipelines report it.
- FIRMS and DEA reporting the same VIIRS overpass are not independent evidence -- only the highest-confidence detection counts.
- True independence requires different satellites, different sensor types, or different observation times.

### 3d. Confidence Ladder

```
LEVEL 1 -- PROVISIONAL:
  Single AHI frame passes contextual tests, OR
  Single DEA/FIRMS detection (fallback)

LEVEL 2 -- LIKELY:
  AHI persistent in 2 of 3 frames, OR
  AHI single frame + independent geostationary cross-check

LEVEL 3 -- CONFIRMED:
  AHI detection + VIIRS/MODIS detection within spatial match radius, OR
  AHI persistent 3 of 3 frames with growing intensity

LEVEL 4 -- HIGH CONFIDENCE:
  Multiple independent sensor confirmations

RETRACTED:
  Single AHI frame, not confirmed in next 2 frames,
  no LEO confirmation within 6 hours
```

**Event Lifecycle:**
```
PROVISIONAL --> LIKELY --> CONFIRMED --> MONITORING --> CLOSED
     |              |
     +-> RETRACTED  +-> RETRACTED
```

Events in MONITORING state receive characterization updates every 15 minutes for 12 hours per competition Rule 9. Events that are not confirmed within the retraction window are marked RETRACTED, clearly distinguished from active fires in all reports.

---

## 4. Data Sources and Access

All Earth observation data used by this system is publicly available, legally obtained, and sourced with the knowledge and permission of the data providers (per Rule 2).

### 4.1 Declared EO Sources

| Source | Satellite | Payload | Spectral Range | Resolution | Altitude | Operator | Access Method |
|--------|-----------|---------|----------------|------------|----------|----------|---------------|
| Himawari-9 AHI | Himawari-9 | AHI (Advanced Himawari Imager) | B07: 3.9 um (MWIR), B14: 11.2 um (TIR) | 2 km (nadir) | 35,786 km (GEO, 140.7 deg E) | JMA (Japan) | AWS NODD S3 (public, unsigned) |
| VIIRS (via DEA) | NOAA-21, S-NPP, NOAA-20 | VIIRS (Visible Infrared Imaging Radiometer Suite) | I4: 3.74 um, I5: 11.45 um | 375 m | 824 km (LEO, sun-sync) | NOAA/NASA | DEA Hotspots WFS API (public) |
| VIIRS/MODIS (via FIRMS) | NOAA-21, S-NPP, NOAA-20, Aqua, Terra | VIIRS, MODIS | Multiple thermal bands | 375 m -- 1 km | 705--824 km (LEO) | NOAA/NASA | FIRMS API (registered, MAP_KEY) |

**Calibration Data:** Last known radiometric calibration for Himawari-9 AHI is maintained by JMA with onboard blackbody calibration updated per scan. VIIRS radiometric calibration is maintained by the NASA VIIRS Characterization Support Team (VCST). Calibration coefficients are embedded in the HSD file headers (Himawari) and applied upstream by DEA/FIRMS (VIIRS/MODIS).

**Over-Declaration (per Rule 3):** The system architecture is designed to ingest fire detections from any FIRMS-supported sensor, including Landsat 8/9 OLI-2 and ECOSTRESS via FIRMS point products. If any partnership opportunities materialize before the competition (BoM faster Himawari feed, OroraTech commercial thermal alerts, GA priority DEA access), these additional sources would supplement but not replace the core public data stack.

### 4.2 Overpass Timing and Coverage

**Himawari-9 AHI:** Full-disk scan every 10 minutes, 24 hours per day. 144 observation opportunities per day over NSW. The target area is always within the field of view.

**VIIRS (three satellites):** Approximately 6 overpasses per day over NSW (3 daytime, 3 nighttime). Typical overpass times:
- Nighttime passes: ~01:00--03:00 AEST
- Daytime passes: ~13:00--15:00 AEST

**MODIS (two satellites):** Approximately 4 overpasses per day, partially overlapping with VIIRS timing.

### 4.3 Data Access Architecture

**Himawari-9:** Data is accessed via the NOAA Open Data Dissemination (NODD) program's public S3 bucket (`noaa-himawari9`) in AWS `us-east-1`. The system polls for new observations every 2 minutes, downloading only the specific segment files needed: Band 07 and Band 14 for NSW-covering segments (0810, 0910). Typical file size per band per segment: ~6 MB. Backup access via JAXA P-Tree FTP if AWS S3 is unavailable.

**DEA Hotspots:** Polled every 5 minutes via the Geoscience Australia DEA Hotspots WFS (Web Feature Service) API. No registration or API key required. Queries are filtered to the NSW bounding box. Returns GeoJSON features with lat/lon, confidence, FRP, satellite, and acquisition time.

**FIRMS API:** Polled every 5 minutes via NASA's Fire Information for Resource Management System API. Requires a registered MAP_KEY (obtained). Queries filtered to the NSW area of interest. Returns CSV with detection parameters.

---

## 5. Detection Latency Budget

### 5.1 Contextual Detection (Mode 1) -- Strong Anomaly Path

| Stage | Time | Cumulative | Notes |
|-------|------|-----------|-------|
| Himawari-9 observation | 0 s | 0 s | Satellite captures full-disk scan |
| JMA processing + NOAA relay to S3 | ~13 min | ~13 min | Measured empirically; primary bottleneck |
| S3 poll detection of new data | 0--120 s | ~14 min | Polling interval: 2 min |
| Download 4 segment files (2 bands x 2 segs) | ~1--3 s | ~14 min | Co-located in us-east-1 |
| Decode HSD to brightness temperature | ~0.5 s | ~14 min | satpy or custom decoder |
| Cloud/water/industrial masking | ~0.2 s | ~14 min | Pre-computed + threshold |
| Contextual fire detection (Mode 1) | ~1 s | ~14 min | Vectorized numpy/scipy |
| CUSUM update (Mode 2) | ~0.5 s | ~14 min | Runs in parallel |
| Temporal persistence filter | ~0.01 s | ~14 min | Rolling buffer |
| Event store ingestion + alert | ~0.5 s | ~14 min | SQLite WAL mode |
| **Total: observation to first alert** | | **~14 min** | Strong anomalies reported immediately |

### 5.2 Marginal Detection Path

For fires that produce moderate thermal anomalies (BTD > 3.5 sigma but < 5 sigma), the temporal persistence filter holds the detection for one additional Himawari frame (10 minutes) before reporting:

**Total: observation to alert = ~24 min** (14 min data latency + 10 min hold)

### 5.3 CUSUM Detection Path (Sub-Threshold Fires)

For fires smaller than the single-frame detection limit (200--500 m^2), the CUSUM algorithm accumulates evidence over multiple frames:

| Fire Size | Approximate CUSUM Detection Delay | Total Time from Ignition |
|-----------|----------------------------------|--------------------------|
| 500 m^2 | ~20--40 min (2--4 frames) | ~34--54 min |
| 300 m^2 | ~40--90 min (4--9 frames) | ~54--104 min |
| 200 m^2 | ~60--180 min (6--18 frames) | ~74--194 min |

CUSUM detections are most valuable during the 10--11 hour gaps between VIIRS passes, when no polar-orbiting sensor coverage is available.

### 5.4 VIIRS Confirmation Path

| Stage | Time | Cumulative |
|-------|------|-----------|
| VIIRS overpass of NSW | 0 s | 0 s |
| GA processing + DEA Hotspots availability | ~17 min | ~17 min |
| Our DEA poll detects new data | 0--300 s | ~22 min |
| Parse + spatial match to existing events | ~0.5 s | ~22 min |
| **Total: overpass to confirmation** | | **~22 min** |

---

## 6. False Positive Mitigation

The system targets a false positive rate below 5% among reported fire events, as required by the competition. False positive control is achieved through a layered filtering pipeline, where each layer is independent and applied in sequence:

### Layer 1: Static Masks (pre-computed, ~0 runtime cost)
- **Water mask:** Hybrid of global-land-mask (1 km ocean coastline) and GSHHS (3 km inland water bodies including lakes, reservoirs, and major rivers). Eliminates sun glint on water and thermal anomalies from warm water bodies.
- **Industrial mask:** 24 known persistent thermal hotspot sites in NSW, including coal-fired power stations (Bayswater, Eraring, Vales Point, Mt Piper), steelworks (BlueScope Port Kembla), aluminium smelters (Tomago), gas power stations, chemical plants, and coal mines. Each site has a 4 km buffer. Detections near these sites are confidence-downgraded, not rejected (real fires can start at industrial sites).
- **VZA limit:** Pixels with viewing zenith angle > 65 degrees are rejected (extreme pixel distortion).

### Layer 2: Geometric Filters (fast computation)
- **Sun glint rejection:** Glint angle computed from solar zenith, solar azimuth, and satellite viewing geometry (Himawari-9 at 140.7 deg E). Pixels with glint angle < 12 degrees are flagged and confidence-downgraded.
- **Solar zenith angle classification:** Separate day/night thresholds applied (SZA boundary at 85 degrees).

### Layer 3: Contextual Detection (Mode 1, ~1 second)
- Adaptive background statistics ensure thresholds respond to local conditions.
- Minimum background standard deviation floor (2 K) prevents spurious detections in homogeneous terrain.
- BT14 longwave contextual test (daytime) catches MIR-only anomalies from reflected sunlight.

### Layer 4: Temporal Persistence Filter (~10--20 minutes)
- Fires must appear in at least 2 of the last 3 consecutive Himawari frames to pass (matching within 4 km radius).
- Sun glint and cloud-edge artifacts shift between frames; real fires persist.
- HIGH confidence detections (absolute thresholds) bypass this filter -- they have near-zero false positive rates.

### Layer 5: CUSUM Weather Rejection
- BT14 rejection criterion: CUSUM candidates where BT14 is anomalously warm (z > 3.0 sigma) are suppressed as weather-driven false alarms (heat waves raise both MIR and TIR channels). Exception: extreme BT14 anomalies (z > 6.0) are not suppressed, as large fires can heat both channels.
- Adjacency filter: CUSUM candidates must have at least one adjacent pixel also flagged.

### Layer 6: Cross-Sensor Confirmation (hours)
- VIIRS/MODIS confirmation via DEA Hotspots and FIRMS.
- Events that remain unconfirmed for 6+ hours after a single detection are retracted.

### Expected False Positive Rates

| After Layer | Estimated FP Rate | Estimated FP per Scan |
|-------------|-------------------|----------------------|
| Raw candidates (Layers 1--2) | ~1% of pixels | ~1,000 |
| After contextual detection (Layer 3) | ~0.1% | ~100 |
| After temporal persistence (Layer 4) | ~0.003% | ~3--4 |
| After cross-sensor confirmation (Layer 6) | <0.001% | <1 |

**Emergency FP Reduction Protocols:** If the observed false positive rate exceeds 5% during the competition, the following escalation steps are available:
1. Raise BTD threshold by 5 K
2. Restrict geostationary-only alerting to nighttime (eliminates sun glint and hot soil)
3. Require 3/3 frame persistence instead of 2/3
4. Require VIIRS confirmation before reporting Himawari-only detections
5. Manual review of each alert before submission

---

## 7. Alert and Reporting

### 7.1 Judge Portal

The primary interface for judges is a real-time web portal built with Leaflet.js, accessible via standard web browser at a public URL.

**Portal Features:**
- Interactive map of NSW with satellite imagery basemap, NSW state border overlay
- Fire event markers color-coded by confidence (PROVISIONAL: yellow, LIKELY: orange, CONFIRMED: red)
- CUSUM fire probability heatmap layer showing sub-threshold thermal activity
- Layer control for toggling between detection sources (Himawari, DEA, FIRMS)
- Time slider showing detection history
- Click on any event for details: detection time, confidence level, sensor sources, BT anomaly magnitude, location uncertainty
- Auto-refresh every 30 seconds
- No login required; judges access via provided URL

**Portal API Endpoints:**
- `GET /api/events` -- Active fire events with full metadata
- `GET /api/events/geojson` -- OGC GeoJSON FeatureCollection
- `GET /api/cusum/heatmap` -- CUSUM probability grid for heatmap display
- `GET /api/status` -- System health, uptime, polling status
- `GET /api/detections` -- Raw detection feed

### 7.2 OGC GeoJSON Export

Fire events are exported as OGC-compliant GeoJSON (RFC 7946) FeatureCollections, directly ingestible into ArcGIS Online.

**Example Feature:**
```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [151.2, -33.8]
  },
  "properties": {
    "id": 42,
    "status": "CONFIRMED",
    "centroid_lat": -33.8,
    "centroid_lon": 151.2,
    "location_uncertainty_m": 500,
    "first_detection_time": "2026-04-10T14:23:00+10:00",
    "latest_detection_time": "2026-04-10T16:43:00+10:00",
    "detection_count": 15,
    "sources": "HIMAWARI,DEA",
    "max_frp": 125.3,
    "max_confidence": "high"
  }
}
```

All dates/times in ISO 8601 format (Rule 6). All units in SI (Rule 5). Coordinates in WGS84 [lon, lat] per RFC 7946.

### 7.3 Alert Confidence Tiers

| Tier | Label | Meaning | Typical Source |
|------|-------|---------|---------------|
| LOW | PROVISIONAL | Thermal anomaly detected, awaiting confirmation | Single Himawari frame (moderate anomaly) or CUSUM-only |
| NOMINAL | LIKELY | Fire probable; persistent across frames or independently confirmed | Himawari persistent 2/3 frames |
| HIGH | CONFIRMED | Fire confirmed by multiple independent observations | Himawari + VIIRS match, or 3/3 frame persistence |

### 7.4 Location Uncertainty

All fire locations are reported as point coordinates with explicit uncertainty circles:

| Sensor | Location Uncertainty | Basis |
|--------|---------------------|-------|
| Himawari-9 AHI | 4 km | Pixel size at NSW latitudes (~3.5 km) + geolocation error (~1 km) |
| VIIRS (via DEA/FIRMS) | 0.5--2 km | 375 m pixels, variable with scan angle |

When a VIIRS detection confirms a Himawari event, the centroid is refined to the VIIRS position and the uncertainty circle shrinks accordingly.

### 7.5 Daily Reports

Daily summary reports are generated and submitted by 20:00 AEST each testing day per Rule 10, emailed to wildfire@xprize.org with the required subject format.

**Contents:**
- All fires detected during the reporting period
- EO sources used that day (per Rule 3)
- Detection time, location, confidence, sensor sources for each fire
- OGC GeoJSON file attachment for ArcGIS ingestion
- System performance summary (detections, false positive rate, uptime)

### 7.6 Characterization Updates

For fires in MONITORING status, the system provides updated characterization every 15 minutes (or more frequently) for 12 hours per Rule 9:

| Field | What We Provide | Method |
|-------|----------------|--------|
| Location (lat/lon) | Best available sensor position | Centroid refined by highest-resolution sensor |
| Location uncertainty | Circle radius in meters | Based on best contributing sensor |
| Estimated size | "Approximately X km^2" | Hot pixel count x pixel area |
| Intensity | Qualitative: low / moderate / high | BT anomaly magnitude relative to background |
| Direction of spread | Bearing (degrees), only with 3+ sequential detections | First-to-latest centroid vector |
| Rate of spread | Estimated m/min, only with 3+ sequential detections | Centroid displacement / elapsed time |
| Confidence | PROVISIONAL / LIKELY / CONFIRMED | Rule-based confidence ladder |
| Contributing sensors | Enumerated list | From provenance records |

**Honest Limitations:** All characterization values are labeled "estimated," not "measured." We do not claim precise perimeter polygons from geostationary-resolution data. Direction and rate of spread are only reported when supported by 3 or more sequential detections with measurable centroid movement. Intensity is qualitative, not quantitative FRP from 2 km pixels.

---

## 8. Infrastructure

### 8.1 Deployment Architecture

| Component | Technology | Notes |
|-----------|-----------|-------|
| Runtime | Docker container on AWS EC2/ECS | Self-contained, single-container deployment |
| Language | Python 3.10+ | numpy, scipy, satpy, FastAPI, boto3 |
| Web server | FastAPI + Uvicorn | Async, handles polling loops + HTTP serving |
| Database | SQLite (WAL mode) | Event store, detection records |
| Hosting region | AWS us-east-1 | Co-located with NODD Himawari S3 bucket |
| Portal | Static HTML + Leaflet.js | Served by FastAPI, no separate frontend build |

### 8.2 Dependencies

| Library | Role |
|---------|------|
| `satpy` | Himawari HSD file decoding and BT conversion |
| `numpy`, `scipy` | Vectorized detection algorithms, background statistics |
| `boto3` | AWS S3 access for Himawari data |
| `FastAPI`, `uvicorn` | HTTP server, REST API, WebSocket support |
| `httpx` | Async HTTP client for DEA/FIRMS polling |
| `pydantic` | Data validation and serialization |
| `global-land-mask` | Ocean/land classification |
| `rasterio` | GSHHS inland water mask GeoTIFF reading |
| `pyorbital` | Solar zenith angle and glint angle computation |

### 8.3 Resource Requirements

| Resource | Requirement |
|----------|------------|
| Compute | 2--4 vCPU, standard instance (no GPU required) |
| Memory | ~500 MB (CUSUM state arrays + working memory) |
| Storage | ~5 GB (state files, database, cached data) |
| Network | Standard AWS egress; ~50 MB/observation for Himawari segments |
| Commercial data | None required |
| External services | None beyond public APIs |

### 8.4 Reliability

- **State persistence:** CUSUM Kalman filter state is saved to disk after every observation frame. On process restart, state is restored from the latest checkpoint with no loss of accumulated background model.
- **Fallback system:** DEA Hotspots + FIRMS polling runs as an independent background task. If the custom Himawari processing pipeline crashes, the fallback system continues to populate the judge portal with VIIRS/MODIS detections.
- **Database durability:** SQLite WAL (Write-Ahead Logging) mode ensures crash-safe writes.
- **Monitoring:** `/api/status` endpoint reports system uptime, last successful poll times for each data source, and observation processing count.

---

## 9. Pre-Competition Preparation

### 9.1 Kalman Filter Pre-Initialization (March 12 -- April 8, 2026)

The CUSUM temporal detector requires approximately 4 weeks of continuous Himawari observations to build stable per-pixel diurnal models. Pre-initialization activities:

1. Download 4 weeks of Himawari-9 archive data (B07 + B14, NSW segments) from AWS NODD
2. Process chronologically through the full pipeline, building Kalman filter state for all ~100,000 NSW land pixels
3. Save converged state to disk (CUSUM state file, ~200 MB)
4. Validate: confirm > 90% of pixels have sufficient observations for CUSUM activation (>= 48 clear-sky frames per pixel)

### 9.2 Threshold Calibration

Detection thresholds have been calibrated using:
- Historical FIRMS fire detection records over NSW (April periods, 2020--2025)
- Analysis of 1,384 known NSW fire events for BT anomaly distributions
- Comparison of detection rates and false positive rates across threshold configurations
- NSW-specific adjustments for autumn conditions (cooler nights, reduced hot bare ground, moderate solar geometry)

### 9.3 System Testing

| Test | Timeline | Objective |
|------|----------|-----------|
| Historical replay (April 2024 Himawari data) | Completed | Validate detection pipeline produces expected results against FIRMS reference |
| Live Himawari processing | Ongoing (March 19+) | Measure actual AWS NODD latency, verify end-to-end pipeline |
| DEA/FIRMS polling reliability | Ongoing (March 18+) | Confirm fallback system uptime and detection quality |
| GeoJSON/ArcGIS import test | Before April 1 | Verify OGC export is correctly ingested by ArcGIS Online |
| CUSUM calibration against live data | March 25 -- April 8 | Tune CUSUM thresholds for optimal sensitivity/specificity |
| Full dry run | April 8 | End-to-end test: detection, portal, reporting workflow |

### 9.4 Daily Reporting Workflow Rehearsal

Before competition start, the team will rehearse the complete daily reporting workflow:
1. Generate daily report from template with system data
2. Export GeoJSON and verify ArcGIS Online ingestion
3. Compile detection summary and EO source declarations
4. Submit test report to internal review before live use

---

## 10. Risk Assessment

### 10.1 Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | **Cloud cover > 70% during testing** | MODERATE | HIGH | All satellite-based teams equally affected. 10-minute Himawari cadence exploits gaps between cloud formations. CUSUM continues accumulating during partial cloud coverage. |
| 2 | **AWS NODD Himawari latency exceeds 15 min** | MODERATE | MODERATE | Switch to JAXA P-Tree as primary Himawari source. DEA Hotspots provides independent VIIRS detections regardless of Himawari data path. |
| 3 | **CUSUM false alarms from weather transitions** | LOW-MODERATE | MODERATE | BT14 rejection criterion suppresses weather-driven CUSUM candidates. Emergency protocol: disable CUSUM alerting if FP rate is unacceptable. |
| 4 | **False positive rate exceeds 5%** | LOW-MODERATE | HIGH | 5-step escalation protocol (see Section 6). Tiered alerting limits exposure. Night detection has much lower FP risk than daytime. |
| 5 | **Himawari-9 satellite anomaly or outage** | LOW | HIGH | GK-2A (Korea, 128.2 deg E) provides backup geostationary coverage via same AWS NODD infrastructure. DEA/FIRMS fallback continues independently. |
| 6 | **Process crash during live burn** | LOW | HIGH | CUSUM state persisted to disk every frame; auto-restart restores state. DEA/FIRMS fallback runs independently and keeps portal populated. |
| 7 | **Portal unavailable to judges** | LOW | CRITICAL | Simple architecture minimizes failure modes. GeoJSON files can be manually delivered as backup. |
| 8 | **Small fires (< 100 m^2) between VIIRS passes** | HIGH | MODERATE | Below Himawari detection limit; CUSUM may not accumulate sufficient evidence before fire grows. Accepted limitation of public geostationary data. Cannot compete with commercial thermal cubesats for this scenario. |
| 9 | **OGC export format incompatible with ArcGIS** | LOW | HIGH | Pre-tested before competition. GeoJSON (RFC 7946) is an OGC standard since 2016 and natively supported by ArcGIS Online. |
| 10 | **Internet connectivity loss during testing** | LOW | MODERATE | Processing runs in AWS cloud, not on local machines. Multiple connectivity options: venue WiFi, cellular hotspot, Starlink. |

### 10.2 Operational Conditions

**Time of Day:** The system operates 24/7 with no dependence on solar illumination for fire detection. Nighttime detection is inherently more sensitive (no sun glint, lower background temperatures, higher thermal contrast). The contextual algorithm uses separate day/night thresholds optimized for each regime.

**Weather Conditions:** Cloud masking operates conservatively (BT_B14 < 270 K threshold with 2-pixel adjacency buffer). Under partial cloud cover, the system detects fires in clear-sky gaps between clouds. Under persistent overcast, detection is degraded for all satellite-based systems. The CUSUM background model continues updating during cloud gaps and decays exponentially during extended cloud periods (3-hour time constant).

**Terrain:** The system operates on native Himawari sensor grid projections (no reprojection in the hot path). Complex terrain does not affect geostationary viewing geometry from NSW latitudes. VIIRS viewing geometry varies with scan angle, but geolocation accuracy (~375 m) is maintained by the operational ground processing chain (DEA/FIRMS).

**Smoke:** Post-ignition smoke plumes can obscure MIR signals for very large fires. However, the initial detection occurs before significant smoke development. The BT14 (11.2 um) channel is more penetrating through thin smoke than shorter wavelengths.

---

## 11. Team and Capabilities

### 11.1 Team

**NAU Ecosystem Science Lab**
School of Informatics, Computing, and Cyber Systems
Northern Arizona University
Flagstaff, Arizona, USA

The NAU Ecosystem Science Lab specializes in remote sensing of ecosystem processes, with extensive experience in satellite-based monitoring of vegetation dynamics, land surface temperature, and wildfire impacts across western North American and Australian landscapes.

### 11.2 Technical Capabilities

- **Remote sensing:** Deep expertise in thermal infrared remote sensing, brightness temperature analysis, and fire detection algorithms from geostationary and polar-orbiting platforms.
- **Ecological monitoring:** Operational experience with long-term satellite monitoring systems for vegetation and disturbance detection.
- **Wildfire science:** Research background in fire ecology, fire behavior, and post-fire recovery monitoring in Australian and North American ecosystems.
- **Rapid development:** System developed using AI-assisted coding for accelerated iteration and testing, enabling a small team to build a production-quality detection system within the competition timeline.

### 11.3 System Development Approach

The system was developed with a fallback-first philosophy: the simplest viable detection capability (DEA/FIRMS polling with judge portal) was built and validated before adding custom Himawari processing and advanced detection algorithms. This ensures that the system provides value to judges from day one of competition, with each additional capability layer improving detection speed and sensitivity.

### 11.4 Honest Assessment of Competitive Position

**Where we are strong:**
- System robustness: dual fallback paths ensure judges always see fire detections
- False positive control: six-layer filtering pipeline with transparent confidence tracking
- Continuous characterization: fire updates every 10 minutes, 24/7 from Himawari
- Transparent confidence reporting: intuitive PROVISIONAL/LIKELY/CONFIRMED labels
- Speed to first alert: ~14 minutes from observation for strong anomalies

**Where we face limitations:**
- Small fires (< 100 m^2) between VIIRS passes are below our detection threshold; commercial thermal cubesat constellations may detect these
- We cannot achieve the 1-minute-from-overpass metric with public data pipelines (~14 min Himawari, ~22 min VIIRS)
- Characterization detail is constrained by geostationary resolution (~3--4 km pixels); we provide honest uncertainty rather than decorative precision

---

## Appendix A: Acronyms

| Acronym | Definition |
|---------|-----------|
| AEST | Australian Eastern Standard Time (UTC+10) |
| AHI | Advanced Himawari Imager |
| ArcGIS | Geographic Information System (Esri) |
| BT | Brightness Temperature |
| BTD | Brightness Temperature Difference (BT_MIR - BT_TIR) |
| CONOPS | Concept of Operations |
| CUSUM | Cumulative Sum (statistical change detection method) |
| DEA | Digital Earth Australia (Geoscience Australia) |
| EO | Earth Observation |
| FIRMS | Fire Information for Resource Management System (NASA) |
| FRP | Fire Radiative Power |
| GEO | Geostationary Earth Orbit |
| GeoJSON | Geographic JSON (OGC standard, RFC 7946) |
| GSHHS | Global Self-consistent, Hierarchical, High-resolution Shoreline |
| HSD | Himawari Standard Data (file format) |
| JMA | Japan Meteorological Agency |
| LEO | Low Earth Orbit |
| MIR / MWIR | Mid-Wave Infrared (~3--5 um) |
| MODIS | Moderate Resolution Imaging Spectroradiometer |
| NODD | NOAA Open Data Dissemination |
| NSW | New South Wales, Australia |
| OGC | Open Geospatial Consortium |
| RFS | NSW Rural Fire Service |
| SNS | Simple Notification Service (AWS) |
| SQS | Simple Queue Service (AWS) |
| SZA | Solar Zenith Angle |
| TIR | Thermal Infrared (~8--14 um) |
| TRL | Technology Readiness Level |
| VIIRS | Visible Infrared Imaging Radiometer Suite |
| VZA | Viewing Zenith Angle |
| WAL | Write-Ahead Logging (SQLite) |
| WFS | Web Feature Service (OGC standard) |
