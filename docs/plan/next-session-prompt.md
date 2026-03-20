# Next Session Prompt

Paste this to start the next session:

---

We're building a wildfire detection system for the XPRIZE Track A finals (April 9-21, 2026, NSW Australia). Start by reading `docs/development-context.md` for full context on what's been built, and `docs/plan/forward-plan.md` for the action plan.

## Where We Left Off

We ran the first validation of our detection pipeline against 86 FIRMS fire events using ~2700 archived Himawari observations (March 1-19). Results in `docs/plan/validation-results-v1.md`:

- **Contextual detector caught only 3 of 86 fires** — thresholds are too strict
- **CUSUM produced 10.2M false alarms** — Kalman models hadn't converged (only 23% of pixels initialized after ~19 days of data). CUSUM needs to be disabled until properly pre-initialized.
- 98.8% "detection rate" is misleading — CUSUM noise coincidentally near real fires

## Priority Tasks (in order)

### 1. Analyze contextual misses (HIGHEST PRIORITY)
For each of the 83 FIRMS fires that contextual detection missed:
- Extract the AHI pixel values (BT7, BT14, BTD) at the FIRMS lat/lon and time
- Compute what the contextual algorithm saw: background mean/std, candidate test results, which specific threshold test failed
- Categorize: was it (a) below candidate threshold, (b) failed sigma test, (c) failed BTD floor, (d) cloud-masked, (e) too small for AHI resolution?
- This tells us EXACTLY which thresholds to relax

The validation output is in `data/validation/` (results.csv, detections_raw.csv, false_alarms.csv). The FIRMS events are in `data/calibration/fire_targets.json`. The Himawari archive is cached in `data/himawari_cache/` (~2700 observations, ~38GB).

### 2. Tune contextual thresholds
Based on the miss analysis, adjust thresholds in `src/himawari/config.py`:
- Candidate selection: `candidate_day_btd_k` (currently 22K — probably too high)
- Sigma: `sigma_day` (3.5) and `sigma_night` (3.0) — may need loosening
- BTD floors: `btd_floor_day_k` (10K), `btd_floor_night_k` (8K)
- Re-run validation (with CUSUM disabled) to measure improvement

### 3. Build RF training dataset
For each FIRMS fire event + matched Himawari observation:
- Extract contextual features (BT7, BT14, BTD, background stats, SZA)
- Add weather features from `data/weather/silo/silo_all_fires_v2.csv` (7823 records, 1266 locations)
- Construct negative samples (fire-free candidates, industrial sites, cloud edges)
- Train Maeda-style Random Forest (sklearn, CPU, minutes)
- Compare to tuned thresholds

### 4. Chronos-2 experiment
Test Amazon's Chronos-2 (120M-param time series foundation model) as a candidate-stage background predictor:
- `pip install chronos-forecasting`
- Feed fire pixel BTD time series from Wollemi data (`data/calibration/wollemi_fire_onset.csv`, `data/calibration/wollemi_neighborhood.csv`)
- Compare Chronos-2 predicted BTD residuals vs our Kalman model residuals
- If residuals are tighter, it's a better background model for temporal detection
- Run on candidates only (1000-3000 pixels, 3-10 sec on GPU)

### 5. Disable CUSUM, start pre-initialization
- Set `cusum_enabled: bool = False` in `src/config.py` for live operation
- Run `scripts/preinit_cusum.py --daily` via cron to accumulate Kalman state
- By April 9, pixels will have 4+ weeks of training — then re-evaluate CUSUM

### 6. CONOPS finalization (due March 31)
- Update `docs/conops/CONOPS-v1.md` with real validation numbers
- Be honest about capabilities: contextual detection of 200+ m² fires from Himawari, LEO sensors (VIIRS/MODIS) for smaller fires via DEA/FIRMS
- Include detection probability curve if synthetic fire injection is done

## Key Files

| File | Purpose |
|------|---------|
| `src/himawari/detection.py` | Contextual fire detection algorithm |
| `src/himawari/config.py` | All tunable thresholds |
| `src/himawari/cusum.py` | CUSUM temporal detector (disable for now) |
| `src/himawari/pipeline.py` | Pipeline orchestration |
| `scripts/validate_pipeline.py` | Validation against FIRMS |
| `scripts/bulk_download.py` | Himawari S3 bulk downloader |
| `scripts/download_weather.py` | SILO weather data |
| `scripts/calibration_extract.py` | Pixel time series extraction |
| `docs/plan/forward-plan.md` | Full 20-day action plan |
| `docs/plan/validation-results-v1.md` | First validation results |
| `docs/development-context.md` | Full development history |
| `docs/refs/maeda_2022_rf.md` | Maeda RF paper (our ML reference) |
| `docs/refs/zhang_2025_msstf.md` | Zhang MSSTF paper (reference, not implementing) |

## Data Assets

| Data | Location | Size |
|------|----------|------|
| Himawari archive (Mar 1-19) | `data/himawari_cache/` | ~38GB, 2705 obs |
| FIRMS fire events | `data/calibration/fire_targets.json` | 1384 events |
| Weather (all fires) | `data/weather/silo/silo_all_fires_v2.csv` | 7823 records |
| Validation output | `data/validation/` | results.csv, detections, false alarms |
| Wollemi fire time series | `data/calibration/wollemi_*.csv` | Single pixel + 5×5 neighborhood |
| GSHHS water mask | `data/gshhs_land_water_mask_3km_i.tif` | 497KB |

## Key Decisions Already Made
- Skip MSSTF deep learning (wrong domain, 20% FAR)
- Maeda-style RF is the right ML intervention
- LEO sensors detect small fires, Himawari detects medium fires fast + characterizes
- CUSUM is stretch goal, not load-bearing
- Test Chronos-2 as candidate-stage temporal model
- Per-overpass scoring means we need every sensor we can get
