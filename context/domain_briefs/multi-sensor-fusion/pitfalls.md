# Pitfalls in Multi-Sensor Fire Detection Fusion

## 1. Registration Errors Between Sensors

### The Problem

When matching a geostationary detection (2 km pixel) to a polar-orbiting detection (375 m pixel), geolocation errors can cause real detections to appear spatially disjoint. If the match radius is too tight, you miss valid cross-sensor confirmations. If too loose, you get false associations.

### Error Magnitudes

| Sensor | Geolocation Error (1-sigma) | Worst Case (3-sigma) |
|--------|---------------------------|---------------------|
| Himawari AHI | 0.5-1.5 km | ~4.5 km |
| VIIRS at nadir | ~375 m | ~1.1 km |
| VIIRS at scan edge | ~500-750 m | ~2.25 km |
| MODIS at nadir | ~500 m | ~1.5 km |
| MODIS at scan edge | 1-2 km | ~6 km |
| Landsat OLI | ~50 m | ~150 m |

**Terrain effects multiply errors**: Fire pixels over mountains or steep terrain show larger geolocation errors because terrain correction algorithms introduce their own uncertainty. At NSW latitudes with the Great Dividing Range, expect up to 2x normal geolocation error in mountainous areas.

### Mitigation

- Use sensor-specific match radii, not a single fixed radius
- Account for scan angle: a VIIRS detection at scan edge has ~2x the uncertainty of one at nadir. The `scan` and `track` fields in FIRMS data encode the actual pixel dimensions
- For critical decisions, use the 3-sigma uncertainty radius, not 1-sigma
- Never point-match across sensors -- always buffer by the coarser sensor's uncertainty

```python
# WRONG: point-to-point matching
distance = haversine(ahi_lat, ahi_lon, viirs_lat, viirs_lon)
if distance < 1.0:  # km -- too tight for AHI uncertainty
    match = True

# RIGHT: buffer-to-buffer matching
ahi_uncertainty_km = np.sqrt((ahi_pixel_size_km / 2)**2 + ahi_geoloc_error_km**2)
viirs_uncertainty_km = np.sqrt((viirs_scan_m / 2000)**2 + (viirs_geoloc_error_km)**2)
max_match_distance = ahi_uncertainty_km + viirs_uncertainty_km
if distance < max_match_distance:
    match = True
```

## 2. Timing Mismatches

### Satellite Overpass Time is NOT Fire Start Time

A critical conceptual error: the `acq_time` in satellite data is when the satellite observed the pixel, not when the fire started. A fire that started 2 hours before a VIIRS overpass will appear in the data with the overpass timestamp. This means:

- **You cannot determine fire start time from a single satellite detection**
- **Cross-sensor temporal matching must use generous windows** because the same fire observed by AHI (10-min cadence) and VIIRS (12-hour revisit) will have very different timestamps
- **FIRMS NRT data has additional processing latency** (~3 hours), so a FIRMS detection with `acq_time` of 02:30 UTC may not appear in the API until ~05:30 UTC

### Geostationary Scan Timing

AHI full-disk scans take ~10 minutes and proceed from north to south. The `timestamp` of a full-disk image is the scan start time, but pixels at different latitudes are actually observed at different times within the 10-minute window. For NSW at ~33 S, the observation time is approximately 7-8 minutes after the nominal scan start time.

This matters for:
- **Frame-to-frame persistence**: Two consecutive "10-minute" frames for a NSW pixel are actually ~10 minutes apart (roughly correct), but comparing a pixel at 10 S to one at 40 S within the same "frame" means comparing observations ~5 minutes apart.
- **Solar geometry calculations**: Use the actual pixel observation time, not the frame timestamp, for glint angle and solar zenith calculations.

### Clock Alignment Across Sensors

| Source | Time Reference | Typical Clock Accuracy |
|--------|---------------|----------------------|
| AHI | JMA spacecraft clock | < 1 second |
| VIIRS | GPS-synchronized | < 1 millisecond |
| MODIS | GPS-synchronized | < 1 millisecond |
| FIRMS NRT | Derived from sensor time | Exact (just delayed) |

Clock accuracy is not the issue -- the issue is that sensors observe the same location at different times, and fires are dynamic. A fire that is 100 m^2 at the AHI observation time may be 500 m^2 by the VIIRS overpass 2 hours later. Treat cross-sensor matching as "same fire event", not "same fire state".

## 3. Confidence Calibration

### The Calibration Problem

Your Bayesian confidence score must be calibrated so that "80% confidence" actually means "80% of detections at this confidence level are real fires." Uncalibrated scores lead to:

- **Overconfident alerts**: If you say 90% confidence but only 60% are real, users lose trust fast
- **Underconfident suppression**: If you say 30% confidence for fires that are 70% real, you miss genuine fires

### Calibration Pitfalls

1. **LLR values are subjective initially**: The log-likelihood ratios in the Bayesian framework are educated guesses until validated against ground truth. Start conservative (lower LLR values) and adjust upward as you accumulate verification data.

2. **Conditional independence assumption is wrong**: The Bayesian log-odds framework assumes each evidence source is independent. In reality:
   - AHI and VIIRS look at the same fire, so their evidence is correlated
   - Temporal persistence is correlated with detection strength (strong fires persist)
   - Land cover and fire weather are correlated

   The practical effect is that combined confidence is overestimated. Mitigate by using smaller LLR values than theory suggests, or by applying a calibration correction after combining.

3. **Prior varies wildly by context**: The base rate of fire differs by orders of magnitude between:
   - Australian bush during fire season: ~0.01% of pixels per day
   - Urban area: ~0.0001% of pixels per day
   - Known fire-prone area during fire weather warning: ~0.1% of pixels per day

   Using a single prior for all pixels produces miscalibrated confidence. Use spatially and temporally varying priors.

4. **Verification data is biased**: You will only verify fires that you detected (or that were reported through other channels). Fires you missed (false negatives) are invisible. This means your calibration data underestimates your false negative rate.

### Recommended Calibration Approach

```
Phase 1 (pre-deployment): Set LLR values based on literature.
  Use FIRMS historical data as pseudo-ground-truth.
  Target: < 5% false positive rate at nominal confidence threshold.

Phase 2 (early deployment): Log all detections with confidence scores.
  Request verification for a random sample, not just high-confidence ones.
  Compute reliability diagram. Adjust LLR values.

Phase 3 (steady state): Continuous calibration with isotonic regression.
  Map raw confidence -> calibrated confidence using accumulated verification data.
```

## 4. The "Crying Wolf" Problem

### The Problem

Frequent false alerts cause users to ignore real alerts. This is the most critical operational risk for a fire detection system. Research shows:

- After repeated false alarms, humans assume future alerts are also false
- Desensitization occurs rapidly -- even 2-3 false alerts in succession can reduce response rates
- Recovery of trust after false alerts is slow and difficult

### For the XPRIZE Competition Specifically

The competition targets < 5% false positive rate. But 5% of thousands of pixels is still potentially dozens of false alerts per day. A false alert every few hours will rapidly erode scorer confidence.

### Mitigation Strategies

1. **Do not alert at "low" confidence**: Reserve alerts for nominal (50%+) and high (85%+) confidence. Low-confidence detections go to a monitoring queue, not to users.

2. **Use the persistence requirement as a hard gate**: Never alert on a single geostationary frame, regardless of anomaly strength. The 20-30 minute delay for 2-of-3 persistence is acceptable given the alternative of false alerts.

3. **Different channels for different confidence levels**:
   - High confidence (85%+): Immediate alert, all channels
   - Nominal confidence (50-85%): Alert after 30-min persistence OR cross-sensor confirmation
   - Low confidence (20-50%): Internal monitoring only, auto-escalate if upgraded

4. **Include confidence metadata in alerts**: Let the user decide their own threshold. Provide the probability, the evidence list, and the sensor sources. Transparency builds trust.

5. **Track your false positive rate in real time**: If FPR over the last 24 hours exceeds 5%, tighten thresholds dynamically.

## 5. Pixel Size vs Fire Size Mismatch

### The Sub-Pixel Problem

At 2 km AHI resolution, a fire needs to be ~4,000 m^2 (roughly 60 m x 60 m) to be detectable at all. The XPRIZE targets fires as small as 10 m^2. This means:

- **AHI will never detect a 10 m^2 fire directly**: The fire must grow substantially before geostationary detection is possible
- **VIIRS can detect fires down to ~100-500 m^2**: Better but still much larger than 10 m^2
- **Only Landsat (30 m) and Sentinel-2 (20 m) can approach the 10 m^2 target**: But their revisit times are 8-16 days

**Implication**: The multi-sensor pipeline is inherently limited for very small fire detection. For the competition, supplement satellite detection with ground-based sensors, camera networks, or other non-satellite inputs if the scoring penalizes missed small fires.

### FRP Below Sensor Noise Floor

Small fires produce low FRP (< 1 MW). At this level, the fire-induced radiance increase may be within the sensor's noise level:

| Sensor | Noise-Equivalent Temperature Difference (NEDT) | Min FRP (approximate) |
|--------|----------------------------------------------|----------------------|
| AHI Band 7 | ~0.2-0.5 K at 300 K | ~5 MW |
| VIIRS I4 | ~0.3-0.7 K at 300 K | ~0.5 MW |
| MODIS B21/22 | ~0.07-0.2 K at 300 K | ~1 MW |

A 10 m^2 fire at 800 K produces roughly 0.02 MW -- well below any sensor's noise floor for a sub-pixel detection.

## 6. Cloud Interference

### Clouds Block All Thermal Detection

Optically thick clouds completely block MIR and TIR radiation from the surface. No amount of algorithmic sophistication can detect a fire through a cloud. In NSW during April:

- Average cloud fraction: ~40-60%
- Convective clouds (afternoon): Can develop quickly, blocking previously clear pixels
- Morning fog/stratus: Common along the coast, clearing by mid-morning

### Cloud Edge False Positives

The boundary between cloud and clear sky is a major false positive source:
- **Warm cloud edges**: Thin cloud can transmit warm surface radiation, creating a BT anomaly that mimics fire
- **Cloud shadow recovery**: When a cloud moves off a pixel, the sudden jump from cold (cloud) to warm (surface) can trigger anomaly detection
- **Navigation-induced cloud leakage**: Imperfect geolocation can cause a cloud pixel to be incorrectly mapped to a clear pixel's location

**Mitigation**: Dilate the cloud mask by 1-2 pixels. This sacrifices some detection area but eliminates the most common cloud-edge false positives.

```python
from scipy.ndimage import binary_dilation

def conservative_cloud_mask(cloud_mask, dilation_pixels=2):
    """Dilate cloud mask to avoid edge artifacts."""
    struct = np.ones((2 * dilation_pixels + 1, 2 * dilation_pixels + 1))
    return binary_dilation(cloud_mask, structure=struct)
```

## 7. Data Latency and Availability Gaps

### Latency Chain

The total time from fire ignition to alert is the sum of:

```
Fire ignition
  + time until next AHI scan covers the area (0-10 min)
  + AHI scan time for NSW latitude (~7-8 min into scan)
  + Data transmission to ground station (~2-5 min)
  + Data processing and ingestion (~5-15 min)
  + Persistence check (10-20 min for 2-of-3)
  + Cross-sensor check (0-6 hours for VIIRS/MODIS)
  = Total: 25-45 min for geostationary-only alert
           2-7 hours for cross-sensor confirmed alert
```

### Data Gaps

- **AHI maintenance windows**: JMA schedules occasional downtime for calibration
- **VIIRS data gaps**: Individual granules may be missing due to downlink failures
- **FIRMS outages**: The API has occasional service interruptions (check `/api/missing_data/`)
- **AWS data lag**: Himawari data on AWS can be delayed beyond the usual 20-40 min window

**Build resilience**: The pipeline should continue operating with whatever sensors are available. If AHI is down, rely solely on VIIRS/MODIS polling. If FIRMS is down, use direct VIIRS L1b data if accessible.

## 8. Diurnal and Seasonal Effects

### Diurnal False Positive Patterns

| Time of Day | Primary False Positive Source | Severity |
|------------|-----------------------------|---------|
| Early morning | Cold cloud clearing, fog burn-off | Moderate |
| Late morning | Sun glint onset, hot bare ground heating | High |
| Solar noon | Peak sun glint risk, maximum surface temperature | Very High |
| Early afternoon | Hot ground persists, convective cloud development | High |
| Late afternoon | Sun glint shifts, long shadows | Moderate |
| Night | Minimal false positives (no solar effects) | Low |

### Seasonal Context for NSW (April)

- **Late autumn**: Declining fire risk but not zero. Major fires can still occur during drought.
- **Lower sun angle**: Reduces but does not eliminate sun glint risk
- **Shorter days**: More nighttime observations (better for fire detection, fewer FP sources)
- **Agricultural burning**: Possible post-harvest burning, which is real fire but may not be the target

### Diurnal Baseline Drift

The Kalman filter baseline will drift during weather changes. A cold front passage can drop surface temperatures by 5-10 K within an hour, causing the baseline to be too warm and masking fire anomalies. Conversely, a warm-to-hot shift can cause the baseline to be too cool, creating false anomalies.

**Mitigation**: Use a process noise parameter (Q) in the Kalman filter that is large enough to allow rapid baseline adaptation, or reset the baseline after detected weather changes using ancillary meteorological data.

## 9. Event Association Errors

### Over-Merging

If the spatial search radius for event association is too large, separate fires within a few kilometers will be merged into a single event. This is particularly problematic in areas with multiple ignitions (e.g., lightning storms producing many small fires).

**Recommended**: Start with a smaller association radius (2-3 km) and increase it only when fire growth is detected. The FEDS algorithm uses ecosystem-specific parameters for merge decisions.

### Under-Merging (Fragmentation)

Conversely, a fire that moves (e.g., a head fire advancing rapidly) may not be associated with the original event if the new detections fall outside the search radius of the original centroid. The centroid-based search can fail for elongated or rapidly advancing fires.

**Mitigation**: Search from the fire event's full geometry (alpha hull), not just its centroid. Any detection within or adjacent to the geometry should be associated.

### Gap-Spanning Association

The 5-day inactivity timeout (from FEDS) means a fire that goes undetected for 6 days will spawn a new event ID, even though it is the same fire. This is a deliberate tradeoff -- the alternative (very long timeouts) risks associating unrelated fires.

For the XPRIZE competition, use a shorter timeout (e.g., 2-3 days) since the evaluation period is limited and long gaps are less likely to be operationally relevant.

## 10. Implementation Complexity Traps

### Trap 1: Over-Engineering the Kalman Filter

The per-pixel Kalman filter sounds elegant but is computationally expensive for a full geostationary disk (~5500 x 5500 pixels for AHI full disk, though most are ocean/cloud). The original research (Roberts & Wooster, 2014) noted it is "computationally costly and requires the full day diurnal variation to be measured prior to fire detection."

**Recommendation**: Use simple contextual tests for the initial implementation. Add temporal filtering only for the NSW land area (~500,000 pixels), not the full disk. Even better, apply temporal filtering only to pixels that pass a coarse pre-filter (e.g., BT_3.9 > 290 K in daytime).

### Trap 2: Treating All VIIRS Detections Equally

VIIRS "low confidence" detections are qualitatively different from "nominal" or "high":
- Low confidence daytime detections are associated with sun glint and weak anomalies
- Low confidence nighttime detections in the South Atlantic Magnetic Anomaly region are filtered from NRT distribution entirely
- Commission error for nominal confidence is < 1.2%; for low confidence it is significantly higher

**Recommendation**: Map VIIRS confidence categories to distinct LLR values: low -> +1.0, nominal -> +3.0, high -> +4.0.

### Trap 3: Ignoring the MODIS `type` Field

MODIS fire data includes a `type` field:
- 0 = presumed vegetation fire
- 1 = active volcano
- 2 = other static land source (industrial)
- 3 = offshore

The VIIRS data does not have this field but FIRMS now provides the STA overlay. Always check the type field for MODIS and the STA mask for all sensors.

### Trap 4: Hard-Coding Thresholds for Australian Conditions

The standard MOD14/VNP14IMG thresholds were developed and validated globally. Australian conditions differ:
- Eucalyptus-dominated forests produce high-intensity fires with high FRP
- Fire behavior in Australian scrub differs from boreal or tropical forests
- The spectral properties of Australian soil and vegetation differ from training regions

The thresholds in the algorithms should be treated as starting points, to be validated and adjusted using Australian fire data from FIRMS historical records.
