# Forward Plan: 20 Days to Competition

**Date:** March 20, 2026
**Competition start:** April 9, 2026 (20 days away)
**CONOPS deadline:** March 31, 2026 (11 days away)
**Dry run at RFS HQ:** April 8, 2026 (19 days away)
**Arrive Sydney:** April 7, 2026 (18 days away)

---

## Phase 1: Validation and Calibration (Days 1-5, March 20-24)

**Goal: Know exactly how our system performs on real data. Everything else depends on these numbers.**

### 1. Complete validation pipeline run on archived data

The validation pipeline (`scripts/validate_pipeline.py`) is running against ~2700 cached Himawari observations (March 1-19). It compares our contextual and CUSUM detections against 1384 FIRMS fire events as ground truth.

**Deliverables:**
- Detection rate: what fraction of FIRMS fire events do we detect, and at what latency?
- False alarm rate: what fraction of our detections have no FIRMS match within 10km/30min?
- Stratify by: fire size (FRP), day/night, detection method (contextual vs CUSUM), confidence level

**Why this is critical:** Without these numbers, threshold adjustments are guesswork. The validation results go directly into the CONOPS. If detection rate is <50% or FAR is >10%, we know exactly which thresholds to adjust.

**Checkpoint file:** `data/validation/checkpoint.json` enables resumable processing. Raw detections accumulate in `data/validation/detections_raw.csv` (~367 MB so far).

### 2. Threshold calibration

Once validation results are available, analyze which contextual thresholds are too strict (missing fires) or too loose (producing false alarms).

**Adjustable parameters (all in `src/himawari/config.py`):**
- Candidate selection: `candidate_night_bt7_k` (290K), `candidate_day_btd_k` (22K)
- Sigma multipliers: `sigma_day` (3.5), `sigma_night` (3.0)
- BTD floors: `btd_floor_day_k` (10K), `btd_floor_night_k` (8K)
- Background std floor: `min_background_std_k` (2K)
- BT14 contextual offset: `bt14_contextual_offset_k` (-4K)
- Cloud threshold: `cloud_bt14_threshold_k` (270K)

**Process:**
1. For each missed FIRMS fire: extract the AHI pixel values at that location and time. Identify which test failed.
2. For each false alarm: examine what made the pixel pass all tests. Is it hot ground, cloud edge, glint?
3. Adjust thresholds, re-run validation, measure improvement.
4. Iterate until detection rate >70% at FAR <5%, or understand why that target is unreachable.

### 3. Synthetic fire injection (if time permits)

Inject known fire signals into clear-sky background AHI data to generate detection probability curves.

**Method:**
- For a range of fire areas (10, 50, 100, 200, 500, 1000, 5000, 10000 m-squared):
  - Compute the sub-pixel BT7 contribution using the Dozier (1981) dual-temperature model
  - Add the signal to real clear-sky AHI pixels
  - Run the detection pipeline
  - Record: detected (yes/no), confidence level, which test triggered

**Deliverable:** A detection probability vs fire area curve. This is a strong CONOPS exhibit: "We detect 95% of fires > 5000 m-squared, 50% of fires 500-1000 m-squared, and <5% of fires < 100 m-squared from Himawari."

---

## Phase 2: ML Enhancement (Days 5-10, March 24-29)

**Goal: Replace hard thresholds with a learned classifier that adapts to conditions.**

### 4. Build RF training dataset

For each FIRMS fire event in our catalog (1384 events):
- Find the closest Himawari observation in time
- Extract contextual features at the fire pixel location:
  - BT7, BT14, BTD (raw values)
  - Background mean/std for BT7, BTD, BT14 at each window size
  - BT7 sigma deviation, BTD sigma deviation, BTD floor deviation, BT14 test deviation (the 4 Maeda contextual parameters)
  - Solar zenith angle
- Extract weather features from SILO (already downloaded):
  - Max/min temperature, rainfall, VPD, relative humidity
  - Effective humidity (Maeda's formulation: weighted 7-day humidity average)

**Negative samples:**
- Candidates from fire-free days that passed initial thresholds but are not fire (hard negatives)
- Random clear-sky land pixels (easy negatives, 3:1 ratio to positives)
- Industrial site pixels (known non-fire thermal anomalies)
- Cloud-edge and sun-glint pixels that pass candidate selection

**Target: ~5000 positive and ~15000 negative samples in a single DataFrame/CSV.**

The calibration extraction infrastructure (`scripts/calibration_extract.py`) and training store (`src/himawari/training_store.py`) already handle much of this. The main new work is systematically processing all 1384 fire events and constructing the negative sampling pipeline.

### 5. Train Random Forest

- sklearn RandomForestClassifier on the feature matrix
- 100 trees, max_depth=20 (following Maeda's hyperparameters)
- 5-fold cross-validation with **spatial blocking** (fires in different geographic regions go to different folds -- prevents spatial autocorrelation from inflating accuracy)
- Compare precision/recall/F1 to the hard-threshold baseline
- Feature importance analysis: which features drive classification?
- Experiment with probability threshold: predict_proba() > 0.3 vs 0.5 vs 0.7

**Expected outcome (based on Maeda 2022):** ~86-90% precision, ~90-93% recall. The contextual parameters should dominate feature importance. Weather features should provide a small but consistent improvement.

### 6. Integrate RF into pipeline

- Add `rf_classifier.py` module that wraps sklearn RF model
- For each candidate pixel, compute the feature vector and call `rf.predict_proba()`
- Replace the hard contextual threshold logic in `detection.py` with RF probability
- Keep threshold path as fallback (config toggle: `use_rf_classifier: bool = False`)
- A/B test: run both paths on archive data, compare detection rate and FAR

**Risk mitigation:** If RF does not clearly outperform tuned thresholds, keep thresholds as primary. The RF is an enhancement, not a dependency.

### 6b. Chronos-2 experiment (parallel with RF)

Amazon's Chronos-2 is a 120M-parameter time series foundation model that could replace the Kalman harmonic background model with zero-shot temporal prediction. Key advantage: no weeks of pre-initialization needed.

**Experiment:**
- `pip install chronos-forecasting`
- Feed a fire pixel's BTD time series (24h context) + weather covariates
- Compare Chronos-2 predicted BTD vs actual → residual
- Compare residual sigma to Kalman model residual sigma on the same pixels
- If Chronos-2 residuals are tighter, it's a better background model

**Run on candidates only (1000-3000 pixels): 3-10 seconds on A10G GPU.**
NOT feasible for all 262K pixels (15 min). Candidate-stage scorer only.

**What to test on Wollemi fire data:**
- Does Chronos-2 predict the diurnal cycle better than our 6-param harmonic model?
- Is the fire signal (residual) more prominent against the Chronos-2 prediction?
- Can it handle cloud gaps in the time series?

**Available models:** 120M (base), 28M (small, ~2x faster, ~1% less accurate)

**Decision point:** If Chronos-2 residuals are significantly tighter (>20% lower sigma) than Kalman, consider replacing CUSUM's Kalman with Chronos-2 on candidate pixels. If not, stick with calibrated Kalman.

### 6c. Spatial-temporal interaction features

Add features to the RF that capture the MSSTF insight — how spatial anomalies evolve temporally:

- **Spatial anomaly trend:** pixel z-score minus neighbor mean z-score, tracked over 3 frames
- **Neighbor divergence:** is this pixel warming while neighbors are not?
- **Spatial gradient change rate:** has the BTD gradient steepened over the last hour?

These capture fire's spatial signature (growing point anomaly that spreads) vs weather's (uniform regional shift). Simple features, no neural network needed.

### 6d. Cascade architecture evaluation

Test ChatGPT's three-stage cascade idea:
- Stage 0: cheap all-pixel candidate generation (relaxed thresholds) → ~500-3000 candidates
- Stage 1: RF + temporal features on candidates only
- Stage 2: Sequential evidence accumulation (simplified CUSUM or consecutive-frame counter)

Compare against current architecture on archived data. The cascade may reduce false alarms by applying expensive classifiers only to promising pixels.

---

## Phase 3: Multi-Sensor and Infrastructure (Days 10-15, March 29 - April 3)

**Goal: Catch fires from every available satellite and prepare infrastructure for competition.**

### 7. Add Sentinel-3 SLSTR FRP polling

Sentinel-3A and 3B pass over NSW at ~10:00 and ~22:00 AEST -- times NOT covered by VIIRS (which passes at ~01:00-03:00 and ~13:00-15:00). These are independent scoring opportunities.

**Implementation:**
- Register at EUMETSAT Data Store (may already be covered by Copernicus CDSE credentials)
- Poll NRT FRP product every 30 minutes for NSW bounding box
- Parse fire detection GeoJSON/CSV: location, FRP, confidence
- Feed into event store as SLSTR-sourced detections via existing `ingest_batch()`
- Tag with satellite/sensor metadata for provenance tracking

**Effort:** Low (~1 day). The NRT FRP product is pre-processed. We just need a polling client similar to `polling/firms.py`.

**Latency:** ~3 hours from overpass. Too slow for 1-minute or 10-minute scoring. Counts for daily reports.

### 8. Build overpass prediction script

**Why:** Judges score per satellite overpass. We need to know exactly when each satellite passes over NSW to:
- Start polling DEA Hotspots at exactly the right time (overpass + 17 min)
- Tag our reports with specific satellite overpasses
- Know when Landsat passes occur (2-4 dates during competition, extremely high value)
- Display upcoming passes on the judge portal

**Implementation:**
- `pyorbital` + CelesTrak TLEs for all fire-relevant satellites:
  - VIIRS: NOAA-21, S-NPP, NOAA-20
  - MODIS: Terra, Aqua
  - Sentinel-3: 3A, 3B
  - Landsat: 8, 9
  - ISS (for ECOSTRESS, stretch)
- Compute all passes over NSW center (-32.5, 151.0) for April 9-21
- Output JSON schedule: satellite, sensor, rise/max/set times (UTC + AEST), max elevation
- Identify exact Landsat WRS-2 path/row dates for NSW coverage

**Effort:** Low (~1 day). Reference implementation exists in domain briefs.

### 9. CUSUM pre-initialization (ongoing)

Continue running `scripts/preinit_cusum.py` daily on accumulating Himawari archive. By April 9, the Kalman models will have 4+ weeks of training data. This transforms CUSUM from "unreliable early-stage" to "potentially useful supplementary layer."

**Target:** >90% of NSW land pixels have >= 48 clear-sky observations by competition start. Monitor `initialized_fraction` in CUSUM state.

**Risk:** Cloud-persistent areas (e.g., coastal eastern NSW in autumn) may never reach 48 observations. These pixels will not have CUSUM coverage. Contextual detection still works for them.

### 10. GK-2A cross-check (if time)

GK-2A AMI data is on AWS NODD (`noaa-gk2a-pds`). Same S3 access pattern as Himawari. The contextual detection algorithm is the same (different satellite longitude: 128.2E vs 140.7E, requiring updated glint angle geometry).

**Value:** Independent geostationary confirmation from a different viewing angle. If both Himawari and GK-2A detect a fire in the same frame, confidence jumps to LIKELY. Also provides backup if Himawari has a data gap.

**Effort:** Moderate (~2-3 days). Main work is adapting the decoder for GK-2A AMI HSD format and adjusting satellite geometry in glint angle computation.

---

## Phase 4: Competition Readiness (Days 15-20, April 3-8)

**Goal: Bulletproof the system for 13 days of autonomous operation.**

### 11. CONOPS finalization (due March 31)

The CONOPS v1 draft (`docs/conops/CONOPS-v1.md`) exists but needs updating with:
- Validation results (detection rate, FAR, latency histograms)
- Detection probability vs fire area curve (from synthetic injection)
- RF classifier performance (if trained by then)
- Updated sensor list (add SLSTR if implemented)
- Overpass schedule for competition window
- Revised CUSUM assessment (honest about initialization requirements)
- Any partnership responses received by that date

**Also due March 31:** Quad chart, system diagram, AI/ML plan, personnel list, ROM cost.

### 12. End-to-end integration test (48-hour dry run)

Run the complete system in real-time for at least 48 continuous hours before leaving for Sydney.

**Monitor:**
- False alarm rate: count detections per day, check against FIRMS reference
- Missed detections: any FIRMS fire in NSW that we did not detect?
- Latency: time from Himawari observation to detection in event store
- Portal display: do detections appear correctly on the map? Auto-refresh working?
- Daily report generation: does `scripts/daily_report.py` produce valid GeoJSON?
- Memory usage: any leaks from CUSUM state growing unbounded?
- Disk usage: is the validation CSV / training store filling up disk?

**Success criteria:** 48 hours with zero crashes, FAR < 5%, portal continuously accessible.

### 13. Failure mode testing

Deliberately test known failure modes:

| Failure | How to test | Expected behavior |
|---------|-------------|-------------------|
| S3 data gap (Himawari) | Block S3 access for 30 min | CUSUM decays gracefully; DEA/FIRMS fallback continues; portal shows stale-data warning |
| DEA Hotspots down | Block WFS endpoint | FIRMS provides backup VIIRS data; Himawari detections still flow |
| Cloud cover > 90% | Run on a heavily clouded archived observation | No false positives from cloud edges; detection pauses gracefully; portal shows cloud cover overlay |
| Day/night transition | Process observations spanning SZA 80-90 deg | Smooth transition between day/night thresholds; no spike in candidates |
| Industrial false alarms | Check known industrial sites (Bayswater, Eraring) | Detections downgraded to LOW, not reported as fire events |
| Process crash + restart | Kill the main process, restart | CUSUM state loaded from disk; temporal filter buffer lost (acceptable); polling resumes |

### 14. Deployment

| Step | Detail |
|------|--------|
| Docker build | Single-container image with Python 3.10+, satpy, numpy, scipy, FastAPI, boto3, pyorbital, etc. |
| Docker test | Run locally, verify all endpoints (`/api/events`, `/api/status`, `/api/events/geojson`) |
| AWS deployment | EC2 or ECS in `us-east-1` (co-located with Himawari S3 bucket for minimal latency) |
| Instance sizing | t3.xlarge (4 vCPU, 16 GB RAM) -- sufficient for processing + portal serving |
| Health monitoring | `/api/status` endpoint returns last poll times, CUSUM initialization fraction, uptime |
| Alerting | CloudWatch alarm on `/api/status` returning error; email notification to team |
| DNS | Point competition URL to EC2 elastic IP |
| HTTPS | Let's Encrypt or AWS Certificate Manager for SSL |

---

## Key Checkpoints

- [ ] **March 22:** Validation results available (detection rate, FAR, latency numbers)
- [ ] **March 24:** Threshold calibration pass 1 complete; detection rate > 60%, FAR < 8%
- [ ] **March 26:** RF training dataset built (~5000 positive, ~15000 negative samples)
- [ ] **March 28:** RF trained and compared against thresholds on archive data
- [ ] **March 29:** SLSTR FRP polling operational
- [ ] **March 30:** Overpass schedule computed for April 9-21
- [ ] **March 31:** CONOPS submitted (hard deadline)
- [ ] **April 2:** 48-hour dry run started
- [ ] **April 4:** 48-hour dry run completed; all failure modes tested
- [ ] **April 5:** Docker image built and tested locally
- [ ] **April 6:** Deployed to AWS; portal accessible via public URL
- [ ] **April 7:** Arrive Sydney
- [ ] **April 8:** Mandatory dry run at RFS HQ, Homebush

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| CUSUM never converges well enough | HIGH | LOW | Not load-bearing. Keep as supplementary heatmap layer. Contextual + RF carry primary detection. |
| RF does not beat tuned thresholds | MODERATE | LOW | Keep tuned thresholds as primary. RF was always an enhancement, not a requirement. |
| S3 data latency spikes (>20 min) | MODERATE | HIGH | JAXA P-Tree FTP as backup Himawari source. DEA/FIRMS as safety net for VIIRS detections. |
| DEA Hotspots outage during competition | LOW | HIGH | FIRMS provides backup VIIRS data. Multiple data paths for each sensor. |
| False positive rate exceeds 5% | MODERATE | HIGH | 5-step escalation: raise BTD threshold, restrict to nighttime geo, require 3/3 persistence, require VIIRS confirmation, manual review. |
| Cloud cover obscures fires for extended periods | HIGH | MODERATE | 10-minute Himawari cadence exploits brief clear-sky gaps. Same constraint for all teams. Cannot mitigate beyond monitoring. |
| Validation reveals detection rate <30% | LOW-MODERATE | HIGH | Fundamental threshold recalibration needed. May require loosening candidate selection thresholds and accepting higher FAR. |
| Portal goes down during competition | LOW | CRITICAL | Simple architecture (FastAPI + SQLite). Auto-restart via systemd/ECS. GeoJSON files can be manually delivered as backup. |
| Team member unavailable during competition | LOW | MODERATE | System is fully automated. Manual intervention only needed for daily reports and threshold adjustments. |
| Docker deployment issues | LOW | MODERATE | Test Docker build on clean machine before departing. Have fallback: run directly on EC2 with virtualenv. |

---

## What NOT to Do

These are anti-patterns identified through analysis and domain expert review. They are tempting but counterproductive given our timeline:

- **Do not chase 10 m-squared fires on Himawari.** The physics limit is clear: 0.11K signal in 0.3-0.5K noise. Even CUSUM cannot accumulate fast enough. Small fires are LEO sensor territory.

- **Do not implement MSSTF deep learning.** Wrong training domain (China), 20% FAR (4x our target), requires GPU training on simulated data, and the temporal window (72 frames = 12 hours) is not viable for real-time detection. The RF approach achieves comparable accuracy with hours of work instead of weeks.

- **Do not use foundation models as the primary full-frame detector.** But DO test Chronos-2 as a candidate-stage background model — it may outperform the Kalman harmonic model with zero pre-training.

- **Do not redesign the architecture.** The two-path system (custom Himawari + DEA/FIRMS fallback) with shared event store is sound. Calibrate what we have.

- **Do not spend time on GPU training unless RF clearly needs it.** sklearn RF trains on CPU in minutes. Only consider PyTorch/TensorFlow if we need a CNN for patch classification (the lightweight CNN stretch goal in the system plan), and only after all higher-priority work is done.

- **Do not optimize for latency below ~7 minutes.** Our floor is Himawari S3 data availability at ~13 minutes. No amount of processing optimization can beat the data latency. Focus engineering time on accuracy and reliability instead.

- **Do not build a complex frontend.** The portal is Leaflet.js with auto-refresh. Judges need a map with colored dots. The portal does not need a React framework, state management, or a build pipeline. Static HTML served by FastAPI is sufficient.

---

## Resource Allocation Summary

| Phase | Duration | Primary Focus | Key Deliverable |
|-------|----------|---------------|-----------------|
| Phase 1 | Days 1-5 | Validation + Calibration | Detection rate and FAR numbers; calibrated thresholds |
| Phase 2 | Days 5-10 | ML Enhancement | Trained RF classifier; A/B comparison with thresholds |
| Phase 3 | Days 10-15 | Multi-Sensor + Infra | SLSTR polling; overpass schedule; CUSUM convergence |
| Phase 4 | Days 15-20 | Competition Readiness | CONOPS; 48-hr dry run; AWS deployment; travel |

**The most important single deliverable is the validation results from Phase 1.** Every subsequent decision (threshold adjustment, RF training data quality, CONOPS claims, confidence in our competitive position) depends on knowing how the system actually performs on real data. Phase 1 cannot be skipped or rushed.
