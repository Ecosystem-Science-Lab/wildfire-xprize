# Development Context and Lessons Learned

**Date:** March 20, 2026
**Session scope:** March 19-20, 2026 intensive development sprint
**Purpose:** Capture institutional knowledge from the first major engineering session so that future sessions (or team members) can pick up where we left off without re-discovering hard-won lessons.

---

## 1. System Built (March 19-20, 2026)

We built a complete Himawari-9 AHI fire detection pipeline from scratch: download, decode, detect, filter, and ingest into an event store. The system processes a single 10-minute observation in approximately 3-6 seconds of compute time (after data arrives from AWS S3).

### Module inventory

| Module | Path | Purpose |
|--------|------|---------|
| `config.py` | `src/himawari/config.py` | All tunable detection parameters as Pydantic models. CUSUMConfig nested inside HimawariConfig. |
| `downloader.py` | `src/himawari/downloader.py` | Lists and downloads Himawari HSD segment files from AWS NODD S3 (`noaa-himawari9`). Filters for B07/B14 and NSW segments (0810, 0910). |
| `decoder.py` | `src/himawari/decoder.py` | Decodes HSD binary format to brightness temperature arrays using `satpy`. Crops to NSW bounding box. Returns BT7, BT14, lats, lons, obs_time. |
| `masks.py` | `src/himawari/masks.py` | NSW bounding box mask, cloud mask (BT14 < 270K threshold), cloud adjacency buffer (2-pixel dilation). |
| `static_masks.py` | `src/himawari/static_masks.py` | Water mask (hybrid global-land-mask ocean + GSHHS 3km inland water). Industrial mask (24 known NSW thermal hotspot sites with 4km buffer). Both cached per grid shape. |
| `detection.py` | `src/himawari/detection.py` | Core contextual fire detection algorithm. Vectorized numpy/scipy. Absolute thresholds, candidate selection, expanding-window background characterization, contextual fire tests, confidence assignment, glint/industrial downgrade. |
| `cusum.py` | `src/himawari/cusum.py` | CUSUM temporal fire detection. Per-pixel 6-parameter Kalman-filtered harmonic diurnal model with BT14 weather covariate. Dual-rate CUSUM (slow k=0.5, fast k=1.5). Bayesian fire probability via sigmoid mapping. State persistence to .npz files. |
| `persistence.py` | `src/himawari/persistence.py` | Temporal persistence filter. Rolling buffer of last 3 frames. Requires fire pixel to appear in 2-of-3 frames. HIGH confidence detections bypass. Haversine distance matching at 4km threshold. |
| `converter.py` | `src/himawari/converter.py` | Converts fire_mask array pixels to Detection model objects with lat/lon, confidence, timestamp, source metadata. |
| `training_store.py` | `src/himawari/training_store.py` | Records per-pixel CUSUM diagnostics (z-scores, fire probability, CUSUM statistics, BT14 anomaly, Kalman weight) to daily Parquet files for calibration. Samples 1% of background pixels plus all interesting pixels (P(fire) > 0.01). |
| `pipeline.py` | `src/himawari/pipeline.py` | Orchestrator. Ties together download, decode, mask, detect, CUSUM, temporal filter, merge, and ingest. Manages module-level singletons for temporal filter, CUSUM detector, and training store. Exposes CUSUM heatmap data for portal API. |
| `poller.py` | `src/himawari/poller.py` | Polls S3 for new Himawari observations on a configurable interval. Triggers `process_observation` for each new timestamp. |
| `models.py` | `src/models.py` | Pydantic Detection and Source models shared across all data sources (Himawari, DEA, FIRMS). |
| `dedup.py` | `src/dedup.py` | Spatial deduplication and event store ingestion. Matches new detections against existing events by distance. |
| `db.py` | `src/db.py` | SQLite database (WAL mode) for event store and detection records. |
| `events.py` | `src/events.py` | Event lifecycle management. Confidence ladder: PROVISIONAL -> LIKELY -> CONFIRMED -> MONITORING -> CLOSED (+ RETRACTED). |
| `export.py` | `src/export.py` | OGC GeoJSON export of fire events. RFC 7946 compliant. |
| `polling/dea_hotspots.py` | `src/polling/dea_hotspots.py` | DEA Hotspots WFS polling client. Parses VIIRS fire detections for NSW. |
| `polling/firms.py` | `src/polling/firms.py` | NASA FIRMS API polling client. Parses VIIRS/MODIS fire detections. |
| `polling/scheduler.py` | `src/polling/scheduler.py` | Async polling scheduler for DEA, FIRMS, and Himawari data sources. |

### Key scripts

| Script | Path | Purpose |
|--------|------|---------|
| `bulk_download.py` | `scripts/bulk_download.py` | Bulk download of Himawari archive from S3. Downloaded Mar 1-19, 2026 data (~23GB, 2705 files). |
| `preinit_cusum.py` | `scripts/preinit_cusum.py` | Pre-initialize CUSUM Kalman filter state from archived Himawari data. Processes chronologically to build per-pixel diurnal models. |
| `calibration_extract.py` | `scripts/calibration_extract.py` | Extract BT time series for specific fire pixels and neighborhoods. Used for Wollemi fire analysis. |
| `validate_pipeline.py` | `scripts/validate_pipeline.py` | Run detection pipeline on archived data and compare against FIRMS reference detections. Checkpointed (resumes from last processed observation). |
| `download_weather.py` | `scripts/download_weather.py` | Download SILO gridded weather data for all FIRMS fire event locations. |
| `daily_report.py` | `scripts/daily_report.py` | Generate daily competition report in required format. |

### Key processing numbers

- NSW AHI grid: approximately 500x700 pixels (~350,000 pixels after NSW crop)
- Processing time per observation: ~3-6 seconds (detection only, excluding download)
- CUSUM state file: ~58 MB (350K pixels x 6-param Kalman state + dual CUSUM + BT14 EMA)
- HSD segment file size: ~6 MB per band per segment (4 files per observation)
- Himawari data latency from AWS NODD: ~13-15 minutes from satellite observation

---

## 2. Detection Approaches Implemented

### 2a. Contextual (Spatial, Single-Frame) Detection

**What it does:** Adapted VNP14IMG/GOES FDC algorithm for AHI spectral response. For each 10-minute frame:
1. Absolute threshold screening (BT7 >= 400K saturated, or BT7 > 320K night / 360K day)
2. Candidate selection (BT7 > 290K night + BTD > 10K; BT7 > 315K day + BTD > 22K)
3. Expanding-window background characterization (11x11 to 31x31)
4. Five contextual tests: BT7 sigma, BTD sigma, BTD floor, BT7 absolute floor, BT14 longwave (day only)
5. Confidence: HIGH (absolute), NOMINAL (strong BTD anomaly > 15K), LOW (moderate anomaly)
6. Glint-zone and industrial-site downgrades (NOMINAL -> LOW, not rejection)

**Current status:** Fully implemented and running on live data. Produces ~0-5 contextual detections per frame under typical March conditions (low fire season).

**What works:** Background characterization is fast (uniform_filter convolution trick). Expanding windows handle heterogeneous terrain. The BT14 longwave contextual test catches daytime MIR-only anomalies from reflected sunlight. Industrial mask catches known thermal hotspots without rejecting real fires.

**What needs work:** Thresholds are not calibrated against real April NSW fire data. The validation pipeline run (in progress) will determine detection rate and false alarm rate against FIRMS reference data.

### 2b. CUSUM Temporal Detection

**What we built:** A sophisticated per-pixel Bayesian CUSUM detector:
- 6-parameter Kalman-filtered harmonic diurnal model: BTD_pred = T_mean + a1*cos(wt) + b1*sin(wt) + a2*cos(2wt) + b2*sin(2wt) + beta*BT14_anom
- The beta coefficient is the key innovation: captures weather-driven BTD shifts via BT14 covariate, keeping residuals flat during heat waves
- Dual-rate CUSUM: S_slow (k=0.5, for small fires over hours) and S_fast (k=1.5, for large fires in minutes)
- Bayesian fire probability: P(fire) = sigmoid(prior_log_odds + scale * S_max)
- Soft Kalman weighting: gain scaled by (1 - P(fire)) to freeze background model during fire
- Joseph form covariance update for numerical stability with softened gain
- BT14 rejection: suppresses candidates where BT14 is also anomalously warm (weather, not fire)
- Adjacency filter: requires at least one neighboring pixel also flagged
- State persistence: full Kalman/CUSUM state saved to .npz after every frame

**What we learned:** See Section 3 below. The CUSUM needs weeks of training data to converge, and with only days of archive data available, it was producing thousands of false positives during initialization. This confirmed the system plan's assessment: CUSUM is a stretch goal, not load-bearing.

### 2c. Temporal Persistence Filter

**What it does:** Rolling buffer of last 3 observation frames. A fire pixel must appear within 4km of the same location in at least 2 of the last 3 frames to pass. HIGH confidence (absolute threshold) detections bypass the filter entirely.

**Why it matters:** This is the single highest-impact false positive reducer. Sun glint artifacts, cloud-edge anomalies, and sensor noise are transient -- they appear in one frame and disappear. Real fires persist. The 10-minute delay for marginal detections is acceptable under the competition scoring model.

**Status:** Fully implemented and integrated into the pipeline.

### 2d. Masks

| Mask | Method | Notes |
|------|--------|-------|
| Water (ocean) | `global-land-mask` library, ~1km | Fast vectorized lookup. Catches coastline precisely. |
| Water (inland) | GSHHS GeoTIFF, ~3km | Lakes, reservoirs, major rivers. Loaded via rasterio. Must download separately (~500KB). |
| Industrial | 24 hardcoded NSW sites, 4km buffer | Coal power (Bayswater, Eraring, Vales Point, Mt Piper), steelworks (BlueScope), smelters (Tomago), gas power, mines, sugar mills. Downgrade only, not rejection. |
| Cloud | BT14 < 270K threshold | Simple but effective. Misses thin/warm clouds. |
| Cloud adjacency | 2-pixel binary dilation | Catches cloud edges that the threshold misses. |
| NSW bounding box | Lat/lon range check | Crops to NSW state boundaries to reduce processing. |
| Sun glint | Glint angle < 12 degrees | Computed from solar/satellite geometry. Confidence downgrade, not rejection. |

---

## 3. Key Findings from Real Data

### 3a. Wollemi Fire Analysis

We extracted and analyzed time series data for the Wollemi fire (a FIRMS-detected fire in the Blue Mountains area). Key findings:

- **Intermittent sub-pixel signal.** The fire pixel showed ~3-sigma BTD spikes interspersed with completely normal values. This is expected for a sub-pixel fire at AHI resolution: the fire fraction of the pixel area is so small that atmospheric turbulence, viewing angle changes, and fire intensity fluctuations cause the signal to appear and disappear frame-to-frame.
- **Pixel location ambiguity.** The FIRMS-reported fire location did not always map to the same AHI pixel. The 375m VIIRS detection could fall in any of 4-6 adjacent 2km AHI pixels. This means we cannot simply extract "the fire pixel" -- we need to check the neighborhood.
- **Background discrimination requires training.** With only 1 day of CUSUM training data, the fire pixel was indistinguishable from its neighbors in terms of Kalman model quality. The diurnal model had not converged. With 2+ weeks of training, per-pixel diurnal parameters would differ enough to make the fire signal stand out.

### 3b. CUSUM Performance Issues

- **5000+ false positives during initialization.** Before pixels accumulated 48+ clear-sky observations (the min_init_observations threshold), the Kalman models were poorly constrained, producing large residuals that triggered CUSUM. Even with the initialization gate, the first few days of processing on archive data generated thousands of candidates.
- **Kalman convergence needs weeks.** The 6-parameter harmonic model needs to see at least 2-3 full diurnal cycles under varied weather conditions to produce stable predictions. The harmonic coefficients (a1, b1, a2, b2) need clear-sky observations at many times of day. Cloud cover during certain hours creates gaps that slow convergence further.
- **Process noise tuning is delicate.** Too high: the model chases fire anomalies and never triggers CUSUM. Too low: the model cannot adapt to seasonal changes and drifts out of calibration. The current setting (0.001 K/step for T_mean) gives ~0.14K/day drift, which is a reasonable compromise.

### 3c. The 10 m-squared Detection Limit

A 10 m-squared fire at NSW viewing geometry (35-43 degree VZA, ~3.5 km effective pixel size) produces approximately 0.11K of BT7 signal above background. With daytime observation noise of ~0.5K and nighttime noise of ~0.3K, this is:
- Daytime: SNR ~ 0.22 (completely undetectable in a single frame)
- Nighttime: SNR ~ 0.37 (still undetectable)

Even CUSUM accumulating over many frames cannot reliably detect fires this small. At 200 m-squared, the signal rises to ~2.2K, giving SNR of 4-7, which is detectable. The practical Himawari detection floor is approximately 200-1000 m-squared depending on fire temperature, background conditions, and day/night.

**Implication:** We must rely on LEO sensors (VIIRS at 375m, Landsat at 100m) for small fire detection. Himawari's role is continuous monitoring of fires once they reach detectable size, plus early warning for fires in the 200-1000 m-squared range between LEO passes.

---

## 4. External Reviews

### 4a. ChatGPT Deep Research Review (March 17)

A ChatGPT Pro deep analysis of our CUSUM implementation identified 4 critical bugs, all subsequently fixed:

1. **Stale fire probability (Bug 1).** CUSUM update used S values from the previous frame, so fire_confidence was always one frame behind. Fix: update S_slow/S_fast before computing fire_confidence.

2. **Cloud decay used total gap time (Bug 2).** CUSUM decay during cloud gaps used total time since last clear observation, causing massive decay even for short cloudy periods. Fix: use incremental dt from last_update_time, which advances every frame.

3. **Standard Kalman covariance with softened gain (Bug 3).** The P update used the standard form P = (I - KH)P, but with the Bayesian-weighted gain L = (1-P(fire))*K, this form is numerically unstable. Fix: Joseph form P = (I - LH)P(I - LH)^T + L*R*L^T.

4. **BT14 contamination (Bug 4).** The BT14 EMA was updated before computing the BT14 anomaly for the current frame, so a fire warming BT14 would shrink its own anomaly on the detection frame. Fix: compute BT14 anomaly from OLD (pre-update) EMA, then update EMA only for low-confidence pixels.

### 4b. Domain Expert Reviews

Multiple domain expert consultations (satellite remote sensing, fire detection algorithms, ML for remote sensing) consistently recommended:

- **Focus on calibration over new architectures.** Our existing contextual + CUSUM system has the right components. The gap is not algorithmic sophistication but empirical calibration against real NSW fire data.
- **Random Forest over deep learning for our timeline.** Maeda-style RF using contextual features as inputs is proven on Australian AHI fires with ~90% precision/recall. Deep learning (MSSTF) was trained on Chinese fires with 20% FAR and requires GPU training we cannot do in time.
- **Per-overpass scoring changes the strategy.** The XPRIZE scoring model evaluates detection at each satellite overpass, not just fastest-to-detect. This means every sensor pass counts, and we need an overpass prediction schedule.

---

## 5. Key Decisions Made

### Skip MSSTF deep learning
**Why:** Zhang 2025 MSSTF was trained on 6 Chinese fire events. The 20% false alarm rate is too high for our <5% target. The model requires GPU training on simulated data that may not transfer to Australian conditions. The timeline does not allow for retraining and validation.

### Maeda-style RF is the right ML intervention
**Why:** Maeda 2022 demonstrated ~90% precision and recall on early-stage Australian fire detection from Himawari AHI using a Random Forest classifier. Key insight: the 4 contextual parameters (our existing features!) contribute more to accuracy than all 9 band values combined. The RF uses exactly the features we already compute (BTD sigma, BTD floor, BT7 sigma, BT14 test), plus band values, SZA, and weather data (which we have from SILO/Open-Meteo). Training takes minutes on CPU with sklearn.

### LEO sensors for small fires, Himawari for continuous monitoring
**Reframing:** The original plan was Himawari-centric ("our competitive edge is custom geostationary processing"). Real data analysis showed this is partially correct but incomplete. Himawari cannot detect fires smaller than ~200-1000 m-squared. VIIRS (375m), Landsat (100m), and Sentinel-3 SLSTR (1km) are the small-fire detectors. Himawari's unique value is 144 scans/day continuous coverage and 10-minute characterization updates.

### CUSUM is background/stretch, not load-bearing
**Why:** CUSUM needs 2-4 weeks of initialization to converge. Even when converged, it adds detection capability only for fires in the narrow 200-500 m-squared range, and takes 20-60+ minutes to accumulate enough evidence. The contextual detector catches most fires that CUSUM would catch, just one frame later (10 minutes). CUSUM's main value is the fire probability heatmap on the portal, not primary detection.

### Per-overpass scoring means we need every sensor we can get
**Key insight from all-teams call (March 17):** "1-minute detection is measured from satellite overpass, not fire ignition." Each overpass gets its own scoring clock. A Sentinel-3 SLSTR pass at 10:00 AEST is a separate scoring opportunity from a VIIRS pass at 13:00 AEST. We should poll every accessible fire product, even at multi-hour latency, because it counts for daily report scoring.

---

## 6. Data Assets Created

### FIRMS fire catalog
- **1384 fire events** in NSW from FIRMS (VIIRS/MODIS/Landsat), spanning Nov 2025 - Mar 2026
- Used for validation pipeline reference and calibration target

### Weather data
- **SILO gridded daily weather** downloaded for all FIRMS fire event locations
- Variables: max/min temperature, rainfall, evaporation, VPD, radiation
- Stored in `data/weather/silo/`
- Used as training features for planned RF classifier

### Himawari archive
- **~23 GB, 2705 files** cached in `data/himawari_cache/`
- Covers approximately March 1-19, 2026
- B07 (3.9um) and B14 (11.2um), NSW segments (0810, 0910)
- Used for CUSUM pre-initialization and validation pipeline

### CUSUM state
- **~58 MB state file** (`data/cusum_state.npz`) from pre-initialization run
- 350K pixels, ~1 day of training (insufficient for reliable detection -- needs 2-4 weeks)
- State version 3 (6-param Kalman, dual CUSUM, BT14 EMA with variance tracking)

### Calibration extractions
- **37 calibration CSV files** in `data/calibration/`
- Time series of BT7, BT14, BTD, and neighborhood statistics for specific fire pixels
- Background grassland reference extraction
- Used for Wollemi fire analysis and threshold tuning

### Validation pipeline output (in progress)
- **367 MB raw detections CSV** (`data/validation/detections_raw.csv`)
- Checkpoint file for resumable processing
- Separate CUSUM validation state (~65 MB)
- Run in progress against archived Himawari data, comparing detections to FIRMS reference

### Detection database
- **SQLite event store** (`data/detections.db`, ~550 KB + WAL)
- Contains all ingested detections and events from live and archive processing
- WAL mode for crash-safe concurrent reads/writes

---

## 7. Reference Papers

### Maeda 2022 (Sensors) -- "Early Stage Forest Fire Detection from Himawari-8 AHI Images Using a Modified MOD14 Algorithm Combined with Machine Learning"

**What it contributes to our approach:**
- Demonstrates that a Random Forest classifier using MOD14 contextual parameters as features achieves ~90% precision and ~93% recall on early-stage Australian fires from Himawari-8 AHI
- The 4 contextual parameters (equivalent to our BTD sigma test, BTD floor test, BT7 sigma test, and BT14 test) have the highest feature importance -- more than all 9 band values combined
- Adding weather data (max/min temperature, humidity, effective humidity) and SZA as features provides a small (<1%) but consistent accuracy improvement
- Trained on 2016-2019 Australian fires, tested on 2020-2021 -- directly applicable to our domain
- Average detection time: 18 minutes after estimated fire occurrence
- **Key implementation detail:** Maeda skips the "potential fire pixel" candidate selection step from MOD14, feeding ALL pixels into the RF classifier. This is critical for early-stage fires where the signal is too weak for threshold-based candidate selection. We should consider the same approach.

### Zhang 2025 (IJAEOG) -- "Near-real-time wildfire detection approach with Himawari-8/9 geostationary satellite data integrating multi-scale spatial-temporal feature"

**What it contributes to our approach:**
- State-of-the-art deep learning approach achieving 88.25% fire accuracy with 20.82% FAR on Chinese fires
- Demonstrates the value of multi-scale spatial-temporal feature fusion (MKAC + LSTT modules)
- Uses BTD (BT07 - BT14) as the primary input feature -- same as our system
- Training on simulated data (synthetic fire pixels with random ignition times) is an interesting approach we could adapt for RF training data augmentation
- **Why we are NOT implementing this:** Trained on 6 Chinese fire events, 20% FAR exceeds our 5% target, requires GPU training and temporal sequences of 72 frames (12 hours), and the training domain does not match NSW Australia. The approach validates that spatial-temporal integration matters, but RF on contextual features is a better fit for our timeline and accuracy requirements.

---

## 8. Remaining Risks and Open Questions

1. **Validation results are not yet available.** The pipeline is running on archived data but has not completed. Until we have detection rate and FAR numbers, we cannot calibrate thresholds or assess competitive viability.

2. **CUSUM may never converge well enough.** By competition start (April 9), we will have ~4 weeks of training data. Whether this is sufficient for reliable sub-threshold detection remains to be seen. The system does not depend on CUSUM working.

3. **No live end-to-end test yet.** The system has been tested on archived data but not in a 48-hour real-time operational test. Failure modes (S3 outages, polling gaps, database corruption) have not been stress-tested.

4. **DEA Hotspots and FIRMS integration is built but lightly tested.** The fallback system (polling + dedup + ingest) works but has not been run continuously for multiple days.

5. **Judge portal exists in skeleton form but needs polish.** The Leaflet.js map with auto-refresh is functional but lacks the CUSUM heatmap overlay, FFDI weather context, and time slider that would differentiate our portal from a basic map.
