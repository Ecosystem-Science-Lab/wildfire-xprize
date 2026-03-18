# Implementation Details of the VIIRS 375 m Active Fire Algorithm (VNP14IMG) and GOES ABI Fire/Hot Spot Product

## Executive Overview

The VIIRS 375 m active fire product (VNP14IMG) implements a MODIS-heritage multi-spectral contextual algorithm tuned for the peculiarities of the VIIRS I-band (375 m) channels, especially the relatively low saturation temperature and noise characteristics of the I4 mid-infrared band. Detection is driven primarily by I4 (3.55–3.93 µm) and I5 (10.5–12.4 µm) brightness temperatures, with extensive cloud and water masking, dynamic background characterization, absolute and contextual threshold tests, and a three-level confidence scheme. Sub-pixel fire radiative power (FRP) is retrieved using co-located 750 m M13 radiances following the Wooster et al. mid-IR FRP method, with FRP apportioned back to the 375 m detections.[^1][^2][^3]

The GOES-R / GOES-16+ ABI Fire/Hot Spot Characterization (FDC/FDCA) algorithm shares the same physical basis (3.9 µm vs 11.2 µm contrast) but is optimized for 2 km geostationary imagery, higher temporal resolution, and full sub-pixel characterization (fire fraction, temperature, FRP) via modified Dozier equations combined with a rich set of spectral, contextual, and temporal tests. The sections below detail the VIIRS implementation first, then summarize how GOES ABI differs and which parameters are most natural candidates for regional tuning (e.g., Australian bushfire regimes).[^2][^4]

## VIIRS VNP14IMG inputs and pre-processing

The VNP14IMG algorithm uses all five 375 m VIIRS I-bands (I1–I5) plus the 750 m dual-gain M13 channel and corresponding L1B quality flags, terrain-corrected geolocation, and a quarterly land–water mask. I4 provides the primary fire signal, I5 supports separation of hot targets from the background and contributes to cloud tests, I1–I3 drive cloud and water classification, while M13 supports FRP retrieval and additional filtering over water and in the South Atlantic Magnetic Anomaly (SAMA) region.[^1]

I-band data are pre-aggregated onboard in three scan-angle-dependent regimes (3:1, 2:1, and 1:1 native samples) to yield nominal 375 m pixels; M13 data are similarly aggregated on the ground and used in both aggregated and un-aggregated forms. Special handling is required for I4 because of its low effective saturation temperature (~358–367 K, depending on context), including explicit tests for saturated, folded, and mixed saturated/unsaturated pixels.[^1]

## Cloud and water masking in VNP14IMG

### Cloud classification tests

Cloud masking is deliberately liberal to avoid excessive omissions of fires under thin or partial cloud, focusing on optically thick clouds that would fully obscure the fire signal. The tests use I1–I2 reflectances (ρ1, ρ2) and I4/I5 brightness temperatures (BT4, BT5):[^1]

- **Daytime cloud tests** (any true → cloud):
  - BT5 < 265 K, or
  - (ρ1 + ρ2 > 0.9 and BT5 < 295 K), or
  - (ρ1 + ρ2 > 0.7 and BT5 < 285 K).
- **Nighttime cloud test** (both must hold):
  - BT5 < 265 K and BT4 < 295 K.

Pixels classified as cloud are excluded from all subsequent fire processing and from background statistic windows.[^1]

### Water masking

Water pixels are first identified using a simple spectral ordering test on visible/NIR reflectances:[^1]

- ρ1 > ρ2 > ρ3 (daytime),

which masks most open water but can miss sediment-laden nearshore water and misclassify some burn scars, though these edge cases have limited impact on fire detection performance. This internal mask is combined with a high-resolution land–water mask derived from MODIS 250 m water classification to provide a more robust land/water discrimination.[^1]

Water pixels are not excluded from fire detection; they are processed separately to allow detection of gas flares and other thermal anomalies over water, but they are treated as a distinct background class for contextual tests.[^1]

## Fixed (absolute) fire and anomaly threshold tests in VNP14IMG

Absolute or fixed-threshold tests identify unambiguous fires and special cases (e.g., saturation and folding) without requiring full contextual characterization. These tests define high-confidence fire pixels or identify potential background fires that must be excluded from background statistics.[^1]

### High-confidence unsaturated nighttime fires

For nighttime, unsaturated I4 data with nominal quality (QF4 = 0), a strong mid-IR signal alone is sufficient to declare a high-confidence fire:[^1]

- BT4 > 320 K and QF4 = 0 (nighttime only).

Pixels passing this test are immediately classified as “high confidence” fires (fire mask class 9).

### Saturated I4 fires

Saturated I4 pixels (BT4 at the saturation value) require corroborating evidence to avoid misclassification of spurious saturation. For both day and night:[^1]

- BT4 = 367 K and QF4 = 9 (saturated) and QF5 = 0 (I5 nominal), and
- (for daytime only) BT5 > 290 K and (ρ1 + ρ2) < 0.7.

Pixels meeting these criteria are also flagged as high-confidence fires.[^1]

### I4 folding (DN wrap-around) detection

Extreme saturation can cause digital number folding in I4, leading to spuriously low BT4 while I5 remains hot. These cases are detected via:[^1]

- Daytime:
  - ΔBT45 = BT4 − BT5 < 0 and BT5 > 325 K and QF5 = 0.
- Nighttime:
  - ΔBT45 < 0 and BT5 > 310 K and QF5 = 0, or
  - BT4 = 208 K and BT5 > 335 K.

Such pixels are treated as unequivocal strong fires and assigned high confidence.[^1]

### Potential background fires

To avoid contamination of background statistics by strongly anomalous hot pixels that are not the central candidate, VNP14IMG identifies and masks “potential background fire pixels” using:[^1]

- Daytime: BT4 > 335 K and ΔBT45 > 30 K.
- Nighttime: BT4 > 300 K and ΔBT45 > 10 K.

Additionally, pixels detected as I4 folding are also treated as background fires for the purpose of contextual window selection.[^1]

## Avoiding bright reflective targets and sun glint

### Bright reflective targets

Strong solar reflection from bright surfaces can produce high apparent BT4 in daytime I4 data, especially over sands, soils, and bright urban targets. VNP14IMG screens out such pixels before candidate fire selection when:[^1]

- ρ3 > 0.3 and ρ3 > ρ2 and ρ2 > 0.25 and BT4 ≤ 335 K.

Pixels satisfying this condition are flagged as “bright pixel rejection” and excluded from further fire tests.[^1]

### Sun glint

Sun-glint geometries (e.g., over small water bodies or metal roofs) can also mimic the radiometric signature of fires. The algorithm computes the glint angle θg via:[^1]

\( \cos \theta_g = \cos \theta_v \cos \theta_s - \sin \theta_v \sin \theta_s \cos \phi \),

where θv is view zenith, θs is solar zenith, and φ is relative azimuth; pixels are classified as “sun glint” (mask class 2) if:[^1]

- θg < 15° and (ρ1 + ρ2) > 0.35, or
- θg < 25° and (ρ1 + ρ2) > 0.4.

These glint pixels are masked from candidate fire selection but can still influence secondary confidence downgrades (see below).[^1]

## Candidate fire pixel selection and large-scale background (BT4S)

To avoid hard-wiring a global BT4 threshold that would under-detect cold-background high-latitude fires and over-trigger in hot low-latitude scenes, VNP14IMG uses a very large contextual window to compute a scene-dependent mid-IR threshold BT4S.[^1]

### Large-area background window

For each pixel, a 501×501 sampling window centered on the pixel is constructed, excluding:[^1]

- Cloud pixels,
- Water pixels,
- Potential background fire pixels,
- Any pixel with non-zero quality flag (including bow-tie deletion samples).

If the window contains fewer than 10 valid observations, BT4S is forced to 330 K; otherwise the median BT4 (M) over the window is used to define:[^1]

- BT4M = MAX(325, M + 25) K,
- BT4S = MIN(330, BT4M) K.

This allows candidate BT4 thresholds to vary adaptively between 325 and 330 K during daytime, depending on the background; at night, a fixed BT4 threshold is used (see below).[^1]

### Candidate fire tests

Using BT4S, candidate fire pixels are defined via liberal tests intended to capture all possible thermal anomalies for later contextual evaluation:[^1]

- **Daytime**: BT4 > BT4S and ΔBT45 > 25 K.
- **Nighttime**: BT4 > 295 K and ΔBT45 > 10 K.

Pixels not meeting these tests are treated as ordinary background and do not enter the detailed contextual fire detection stage.[^1]

## Contextual background characterization window and statistics

For each candidate fire pixel, a smaller dynamic sampling window is used to characterize the local background around that candidate. The window is centered on the candidate and grows from 11×11 up to a maximum of 31×31 elements until one of the following is true:[^1]

- At least 25% of window elements are valid background pixels, or
- At least 10 valid background pixels are found.

Valid background pixels are those that:[^1]

- Are not clouds,
- Are not potential background fires,
- Have nominal quality flags,
- Belong to the same medium type (land or water) as the candidate.

If sufficient background pixels cannot be found, the candidate is assigned the “unclassified” class (mask value 6).[^1]

Within the final window, the algorithm computes for the set of valid background pixels:[^1]

- BT4B: mean BT4,
- BT5B: mean BT5,
- ΔBT45B: mean BT4 – BT5,
- δ4B, δ5B, δ45B: mean absolute deviations of BT4, BT5, and ΔBT45, respectively.

For daytime scenes where a significant number of background fires are present (≥4 background fire pixels, or background fires >10% of valid background pixels), secondary statistics BT′4B and δ′4B are computed over just the background-fire subset for a pre-filter (see below).[^1]

## Contextual fire detection tests and confidence assignment

### Background-fire pre-filter (daytime)

If the candidate’s local neighborhood includes significant background-fire contamination, a pre-filter attempts to reject small fluctuations within a broader fire region that might not represent distinct active fire pixels:[^1]

- Condition: ρ2 > 0.15 and BT′4B < 345 K and δ′4B < 3 K and BT4 < BT′4B + 6×δ′4B.

Candidates meeting all of these are reclassified as fire-free land (or water) and not processed further.[^1]

### Main contextual tests

Remaining candidate pixels are subjected to contextual tests that compare their BT4, BT5, and ΔBT45 to the local background means and deviations. Pixels that pass all relevant tests are classified as nominal-confidence fires (mask 8).[^1]

- **Daytime contextual tests** (all conditions must hold):
  - ΔBT45 > ΔBT45B + 2×δ45B,
  - ΔBT45 > ΔBT45B + 10 K,
  - BT4 > BT4B + 3.5×δ4B,
  - BT5 > BT5B + δ5B − 4 K, or δ′4B > 5 K (alternative condition when background-fire variability is high).

- **Nighttime contextual tests** (all conditions must hold):
  - ΔBT45 > ΔBT45B + 3×δ45B,
  - ΔBT45 > ΔBT45B + 9 K,
  - BT4 > BT4B + 3×δ4B.

These tests encapsulate the classic MODIS-style requirement that fire pixels be significantly warmer in I4 relative to both the absolute background and the I4–I5 contrast, scaled by the local variability.[^2][^1]

### Secondary tests and low-confidence fires

Two secondary mechanisms either add fires that failed earlier tests or downgrade nominal-confidence detections that are likely false alarms.[^1]

1. **Residual saturation/folding-related fires**:
   - Pixels satisfying any of:
     - BT5 ≥ 325 K, or
     - BT4 = 355 K, or
     - ΔBT45 < 0,
   - and having at least one adjacent (8-neighbor) nominal or high-confidence fire pixel are promoted to **low-confidence** fires (mask 7).[^1]

2. **Sun-glint-related downgrades**:
   - For nominal-confidence fire pixels, if:
     - ΔBT45 ≤ 30 K, or
     - θg < 15°,
   - then the pixel is downgraded to **low confidence** (mask 7) if **either**:
     - At least two adjacent “sun glint” pixels exist, or
     - There are no adjacent high-confidence fires and BT4 is less than 15 K above any adjacent pixel.[^1]

### Confidence classes and mask codes

The two-dimensional fire mask SDS assigns integer classes:[^1]

- 0: not processed,
- 1: bow-tie deletion,
- 2: sun glint,
- 3: water,
- 4: clouds,
- 5: land,
- 6: unclassified (insufficient background),
- 7: low confidence fire,
- 8: nominal confidence fire,
- 9: high confidence fire.

In addition, the sparse-array field `FP_confidence` stores fire-only confidence codes 7 (low), 8 (nominal), and 9 (high).[^1]

## Nighttime SAMA filter and persistence tests

Noise in nighttime I4 data over the South Atlantic Magnetic Anomaly region (roughly 110° W–11° E, 7° N–55° S) can mimic hot pixels and lead to spurious detections. VNP14IMG uses co-located un-aggregated M13 radiances and a modified aggregation to enforce additional checks:[^1]

- M13 is re-aggregated with **maximum** rather than mean value within each 750 m pixel to preserve fire signals.[^1]
- For each suspicious 375 m fire in the SAMA domain, the co-located aggregated M13 must be at least 2 K warmer than all adjacent M13 pixels; otherwise the detection is downgraded to fire-free with a specific QA flag.[^1]

For fires over water, a **persistence test** adds an additional safeguard against random noise or rare SAMA manifestations in daytime I4:[^1]

- First, require M13 fire pixel > adjacent M13 pixels by at least 2.5 K; if not,
- Require at least three co-located detections within the previous 30 days; otherwise downgrade to fire-free and flag bits 19–21 in the QA SDS.[^1]

## FRP retrieval and sub-pixel characterization in VNP14IMG

### Rationale for using M13 rather than I4

Because I4 saturates at relatively low brightness temperatures and experiences folding and noise issues, sub-pixel fire characterization using I4 radiances is unreliable. Instead, VNP14IMG uses the higher-saturation, dual-gain 750 m M13 mid-IR channel, which rarely saturates, to compute FRP while relying on 375 m I4/I5 data purely for detection and background selection.[^1]

### FRP computation

VIIRS FRP retrieval follows the Wooster et al. 4 µm method, applied to M13 radiances under the simplifying assumptions of unit atmospheric transmittance and emissivity. For each 750 m pixel that contains at least one 375 m fire pixel, FRP is computed as:[^3][^1]

\[ \text{FRP} = A \, \sigma \, \left( \frac{L_{13} - L_{13B}}{a} \right)^{1/4} \] [^1]

where:

- A is the 750 m pixel area (scan-angle dependent),
- σ is the Stefan–Boltzmann constant (5.67×10⁻⁸ W m⁻² K⁻⁴),
- a is a band-specific constant for M13 (2.88×10⁻⁹ W m⁻² sr⁻¹ µm⁻¹ K⁻⁴),
- L13 is the M13 radiance for the fire pixel,
- L13B is the mean background M13 radiance for the contextual window.[^1]

If M13 itself is saturated or background statistics cannot be derived (rare cases), FRP is set to zero or null even if a fire is detected at 375 m.[^3][^1]

### Mapping FRP back to 375 m detections

Because FRP is computed at 750 m resolution, but detections are at 375 m, VNP14IMG apportions each M13 FRP value equally among all coincident 375 m fire pixels:[^5][^1]

- If one 375 m fire lies within a given M13 pixel, that fire receives the full FRP.
- If N 375 m fires lie within the same M13 pixel, each receives FRP/N.

Thus, FRP in `FP_power` is defined per 375 m active-fire pixel, even though it is fundamentally derived from coarser mid-IR radiance differences.[^5][^1]

### Sub-pixel area and temperature

The VNP14IMG product does not explicitly retrieve sub-pixel fire area or temperature; only FRP is provided. Users seeking area and temperature must infer them indirectly from FRP using assumptions about typical fire temperatures or combine VNP14IMG with independent higher-resolution data.[^3][^1]

Conceptually, however, the FRP approach is consistent with Dozier-style sub-pixel modeling: mid-IR radiance in a mixed pixel can be approximated as a linear mixture of a hot component (fire) and a cooler background, with FRP proportional to the fourth power of fire temperature times emitting area.[^6][^3]

## Confidence scoring methodology in VNP14IMG

Confidence is encoded via the fire mask and the `FP_confidence` field, based on which tests led to classification and on subsequent spatial/ancillary checks.[^1]

- **High confidence (9)**:
  - Fires passing explicit fixed-threshold tests (unsaturated BT4 > 320 K at night, saturated I4 with supportive BT5 and reflectance, or clear folding signatures) without relying on contextual thresholds.[^1]

- **Nominal confidence (8)**:
  - Fires passing the full set of contextual tests (daytime or nighttime) with valid background statistics, not downgraded by glint or SAMA filters.[^1]

- **Low confidence (7)**:
  - Residual saturated/folding-related signals adjacent to higher-confidence fires,
  - Contextual fires in strong glint geometries with ambiguous ΔBT45 behavior,
  - Detections over water that pass some but not all persistence or M13 corroboration criteria.[^1]

This discrete confidence scheme is intended to approximate relative detection reliability as observed in validation studies (e.g., against Landsat/ASTER), and users are often advised to select nominal+high for most applications, reserving low-confidence pixels for more permissive use cases or targeted event review.[^7][^2]

## GOES ABI Fire/Hot Spot Characterization (FDC) algorithm

### Overall design and inputs

The GOES-R/GOES-16 ABI Fire Detection and Characterization Algorithm (FDCA, or FDC/FHS product) is also a dynamic, multi-spectral thresholding contextual algorithm but is tuned for continuous geostationary coverage at ~2 km resolution, with a strong emphasis on temporal filtering and sub-pixel characterization.[^4][^2]

Key inputs:[^2]

- ABI channels:
  - Channel 7 (3.9 µm) and Channel 14 (11.2 µm) required for detection and characterization,
  - Channel 2 (0.64 µm) for daytime cloud/surface reflectance,
  - Channel 13 (10.3 µm) used when focal-plane temperature anomalies affect Channel 14,
  - Channel 15 (12.3 µm) to help identify opaque clouds.
- Ancillary masks and fields: land–sea mask, desert mask, coast mask, NWP fields (e.g., TPW), surface emissivity database, vegetation/land-cover type, and viewing geometry.[^2]

Processing is limited to view zenith angles ≤80° (best performance ≤65°), with explicit block-out zones for some surface types and glint regions.[^2]

### Two-part processing: Part I and Part II

FDCA is organized into two main loops:[^2]

- **Part I (loop over all pixels)**:
  - Global pre-screening (view-angle, solar geometry, cold/warm thresholds),
  - Multi-stage cloud and glint tests,
  - Background window construction and statistics,
  - Contextual fire detection and preliminary sub-pixel characterization (Dozier solution and FRP),
  - Assignment of initial fire mask and characterization flags.

- **Part II (loop over candidate fires)**:
  - Additional thresholding and post-correction tests,
  - Temporal filtering using previous detections to reduce false alarms and code persistence,
  - Final classification into fire categories and quality flags.[^2]

### Key threshold tests (examples)

While the FDCA includes numerous tests, the ATBD highlights several representative thresholds in the initial and contextual stages.[^2]

**Initial screening examples:**

- Satellite zenith angle >80° → mask as “block-out.”
- Strongly cold or non-fire pixels via T3.9, T11.2, and T3.9–T11.2 differences; for example, pixels with T3.9–T11.2 ≤2 K when either band exceeds 273 K are considered unlikely to be fires.[^2]
- T3.9 minimum thresholds T3.9min (scene dependent) around 285 K at night and higher in daytime, with additional dependence on cos(SZA).[^2]

**Cloud tests examples:**

- Opaque-cold clouds: T11.2 < 270 K or combinations of T3.9–T11.2 < −4 K.[^2]
- Highly reflective daytime clouds: Channel-2 albedo ≥0.38, sometimes combined with temperature thresholds and T11.2–T12.3 differences.[^2]

**Background window and contextual tests:**

- Dynamic background window up to about 111×111 pixels, requiring at least ~20% valid cloud-free land pixels; used to compute mean and standard deviation (or similar metrics) of T3.9, T11.2, T3.9–T11.2, and a reflectivity proxy (3.9 µm – 11.2 µm radiance difference).[^2]
- Contextual fire tests requiring the pixel’s T3.9–T11.2 and T3.9 anomalies to exceed several times the background standard deviation plus scene-dependent offsets, conceptually similar to the MODIS/VIIRS approach.[^2]

Because FDCA is used operationally in multiple versions (legacy WFABBA, updated ABI-specific variants), exact numeric thresholds and tuning can vary between software releases, but the ATBD clearly documents the above families of tests tied to background variability, viewing geometry, and surface type.[^4][^2]

### Cloud and water masking in FDCA

Cloud and water detection leverage multiple spectral and ancillary tests rather than a single cloud-mask product. Representative logic includes:[^2]

- Multi-band cold and split-window tests (e.g., T11.2, T11.2–T12.3) for opaque clouds.
- High visible albedo and spectral ratios for daytime clouds.
- Land–sea and coast masks, with separate handling of ocean, inland water, and coastal fringe pixels; many water and near-coastal pixels are excluded from fire processing or receive special classification codes.[^2]

These tests feed into a rich set of fire mask categories (e.g., different non-fire reasons such as water, various cloud types, sun-glint block-out, invalid ecosystems).[^2]

### Sub-pixel area, temperature, and FRP (Dozier + FRPDEF)

Unlike VNP14IMG, ABI FDCA explicitly solves for sub-pixel fire area and temperature using a modified Dozier method based on radiances in the 3.9 µm and 11.2 µm channels:[^2]

- System of equations (conceptually):
  - L3.9 = p·L3.9(Tfire) + (1 − p)·L3.9(Tbg),
  - L11.2 = p·L11.2(Tfire) + (1 − p)·L11.2(Tbg),
- Where p is the fractional fire area, Tfire the fire temperature, and Tbg the background temperature estimated from contextual statistics.[^2]

The system is solved numerically (typically via bisection followed by Newton–Raphson) to yield p and Tfire, from which fire size (p times pixel area) and temperature are obtained.[^2]

FRP is then derived using a middle-IR FRP definition (FRPDEF/FRPMIR) expressed as a function of pixel area, fire fraction, and fire temperature, following Wooster-type relationships adapted to ABI spectral response:[^2]

- FRP ≈ Apixel · p · σ · (Tfire⁴ − Tbg⁴), adjusted by calibration constants to map from band-limited FRP to broadband radiative power.[^4][^2]

Only pixels meeting sufficient SNR, dynamic-range, and contextual criteria receive valid Dozier and FRP solutions; others are flagged accordingly (e.g., saturated, cloudy, low-probability) with undefined or sentinel-valued characterization fields.[^2]

### Fire categories and confidence in FDCA

The ABI fire mask categories encode both confidence and reasons for non-detection. Core fire-related categories (exact numeric codes vary) include:[^2]

- Saturated fires (sub-pixel characterization typically not attempted or limited).
- Processed fires (Dozier and FRP successfully computed; “high possibility”).
- Cloudy fires (fire signal detected but heavily cloud affected).
- High-, medium-, and low-possibility fires (based on which tests passed and temporal consistency).

Temporal filtering is a key differentiator: fires confirmed in subsequent time steps receive upgraded codes (e.g., +20 to mask value), while isolated, one-off detections that fail temporal consistency checks can be downgraded or treated as low possibility.[^4][^2]

## Key differences between VIIRS VNP14IMG and GOES ABI fire algorithms

The following table summarizes major implementation differences most relevant to scientific use and potential tuning:

| Aspect | VIIRS VNP14IMG | GOES ABI FDCA |
|--------|----------------|----------------|
| Platform/orbit | Polar-orbiting S-NPP/JPSS, ~12 h global coverage | Geostationary GOES-R series, 5–15 min refresh |
| Native fire channel | I4 (3.55–3.93 µm, 375 m) with low saturation (~358–367 K) | Ch7 (3.9 µm, 2 km) with higher saturation (~400 K) |
| Companion LWIR | I5 (10.5–12.4 µm, 375 m) | Ch14 (11.2 µm, 2 km), plus Ch13/Ch15 when needed |
| Primary detection tests | Fixed BT4/ΔBT45 tests + contextual BT4/BT5/ΔBT45 vs local mean/mean-abs-dev | Multi-stage fixed/contextual tests on T3.9, T11.2, T3.9–T11.2, reflectivity, with larger background windows |
| Background window | 501×501 (scene BT4 median) for BT4S; 11×11–31×31 for contextual stats | Up to ~111×111 for contextual stats, with ≥20% valid background requirement |
| Cloud/water handling | Internal cloud tests on BT5 and ρ1+ρ2; simple spectral water mask plus MODIS-based land–water mask | Multi-channel cloud tests (T11.2, T11.2–T12.3, T3.9–T11.2, visible albedo) plus land/sea, desert, and coast masks |
| Confidence | 3-level (low/nominal/high) based on test history and glint/SAMA/persistence checks | Multiple fire categories (saturated, processed, cloudy, high/medium/low possibility) with temporal filtering-based upgrades/downgrades |
| Sub-pixel characterization | FRP only (no explicit area/temperature), computed with M13 radiances and apportioned to 375 m fires | Full Dozier-based area and temperature + FRP for many fires |
| Temporal filtering | Limited to persistence tests over water (gas flares) | Extensive temporal filtering over full disk (12 h window typical) to refine confidence |

[^4][^2][^1]

## Tunable parameters and thresholds for Australian bushfire conditions

The operational VNP14IMG and ABI FDCA algorithms are globally tuned, but from an algorithm-design perspective several parameters are natural candidates for regional tuning, such as for Australian bushfires which often feature high-intensity flaming, large contiguous fire lines, and hot summer backgrounds.

### VIIRS VNP14IMG tunable elements

Potentially tunable thresholds or parameters (if one were to develop an Australia-specific variant) include:

1. **Candidate fire BT4/ΔBT45 thresholds**
   - Daytime: BT4 > BT4S and ΔBT45 > 25 K.
   - Nighttime: BT4 > 295 K and ΔBT45 > 10 K.[^1]
   - For hot, semi-arid Australian backgrounds, BT4S may regularly be near the 330 K cap; raising the ΔBT45 daytime threshold slightly (e.g., to 27–30 K) could reduce false alarms from very hot bare soils while maintaining sensitivity to intense flaming lines, but would risk increased omission of low-intensity grass fires.

2. **Scene-dependent BT4S definition**
   - BT4S ranges from 325 to 330 K via BT4M = MAX(325, M + 25), BT4S = MIN(330, BT4M).[^1]
   - In climatologically hot regions, one could consider a larger offset than +25 K above median or a higher BT4S cap (e.g., 332–335 K) to avoid over-triggering; conversely, high-latitude Australian forests might benefit from slightly lower caps to better capture modest anomalies.

3. **Contextual test multipliers**
   - Daytime: factors 2 (for ΔBT45 vs δ45B) and 3.5 (for BT4 vs δ4B); nighttime: factors 3 and 3, respectively.[^1]
   - Validation studies could assess whether reduced multipliers (e.g., 3.0 instead of 3.5) improve detection of narrow, intense fire fronts common in eucalypt fuels without excessive false alarms from heterogeneous terrain.

4. **Background-fire handling**
   - The background-fire pre-filter (using BT′4B, δ′4B, and BT4 < BT′4B + 6×δ′4B) is designed to suppress small fluctuations inside large fire complexes.[^1]
   - For Australian mega-fires, relaxing these conditions could retain more within-perimeter gradients, potentially improving mapping of active front positions at the cost of more clutter within large burned areas.

5. **Glint and bright-surface thresholds**
   - Bright-surface rejection (ρ3 > 0.3, ρ3 > ρ2, ρ2 > 0.25, BT4 ≤ 335 K) and glint thresholds (θg, ρ1+ρ2) are generic.[^1]
   - Over bright Australian inland water bodies and salt lakes, these thresholds might be overly aggressive or insufficient, and could be regionally tuned based on ground validation (e.g., adjusting reflectance cutoffs or glint-angle limits).

6. **SAMA and persistence filters**
   - These primarily affect South Atlantic sectors and global oceans; they are less directly relevant to Australia but highlight the utility of spectral corroboration (M13) and long-term temporal persistence filters for gas flares and industrial sources.[^1]

Any such tuning should be informed by high-resolution reference data (e.g., Landsat-8/9, Sentinel-2, aerial IR) in Australian landscapes, ensuring that changes improve detection probability for target fires while controlling commission errors.[^7][^2]

### GOES ABI FDCA tunable elements

Although GOES-R does not cover Australia, analogous geostationary systems (e.g., Himawari AHI) use similar contextual/Dozier approaches, and the FDCA ATBD illustrates tunable dimensions:[^2]

1. **Background window and σ-multipliers**
   - Maximum background window size (~111×111) and the number of valid pixels required are tunable, as are the σ-multipliers for T3.9, T11.2, and T3.9–T11.2 anomalies.[^2]
   - Hot, heterogeneous Australian surfaces might benefit from slightly smaller windows or vegetation-type–dependent σ thresholds to reflect more localized variability.

2. **Minimum T3.9 thresholds (T3.9min, T3.9ReflThreshold)**
   - The ATBD describes T3.9min around 285 K at night and higher during the day (plus cos(SZA) scaling) as a gatekeeper for potential fires.[^2]
   - Regionally lowering or raising these thresholds could better match typical background temperature distributions in Australian summers vs winters.

3. **Cloud and glint block-out definitions**
   - Thresholds combining visible albedo, LWIR temperatures, and split-window differences for cloud, as well as sun-glint angular limits, can be tuned against regional cloud climatology and surface reflectance patterns.[^2]

4. **Temporal filtering parameters**
   - The length of the temporal window and spatial co-location criteria for upgrading/downgrading fire categories can be adjusted to match typical fire lifetimes and movement speeds in specific regions.[^2]

Translating these concepts to AHI or other geostationary fire products over Australia would involve similar regional validation using ground-based and higher-resolution satellite fire records.

## Concluding remarks

The VNP14IMG and GOES ABI FDCA algorithms share a common physical basis and contextual design but differ in resolution, orbit, temporal sampling, and the extent of sub-pixel characterization. For Australian bushfire applications with access to VIIRS, the most directly relevant tunable elements are the candidate and contextual BT4/ΔBT45 thresholds, BT4S definition, and glint/bright-surface handling, all of which can be regionally calibrated against independent fire references. Any such tuning must carefully balance improved sensitivity to characteristic Australian fire behavior against increased commission errors from hot, bright, or heterogeneous backgrounds.[^7][^2][^1]

---

## References

1. [[PDF] Visible Infrared Imaging Radiometer Suite (VIIRS) 375 m Active Fire ...](https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_375m_ATBD.pdf) - Visible Infrared Imaging Radiometer Suite (VIIRS). 375 m Active Fire Detection and Characterization....

2. [[PDF] The New VIIRS 375m active fire detection data product](https://www.earthdata.nasa.gov/sites/default/files/imported/Schroeder_et_al_2014b_RSE.pdf) - In this paper we introduced the use of the new 375 m VIIRS sensor data in support of active fire det...

3. [[PDF] VIIRS Active Fire Product User's Guide - LP DAAC](https://lpdaac.usgs.gov/documents/427/VNP14_User_Guide_V1.pdf)

4. [[PDF] GOES-R Advanced Baseline Imager (ABI) Algorithm Theoretical ...](https://www.star.nesdis.noaa.gov/atmospheric-composition-training/documents/ABI_FDC_ATBD.pdf) - Document (ATBD) provides a high level description of diurnal fire detection ... The cloud screening ...

5. [[PDF] Visible Infrared Imaging Radiometer Suite (VIIRS) 375 m & 750 m ...](https://lpdaac.usgs.gov/documents/132/VNP14_User_Guide_v1.3.pdf) - This document describes the Suomi National Polar-orbiting Partnership Visible. Infrared Imaging Radi...

6. [The New VIIRS 375 m active fire detection data product](https://www.sciencedirect.com/science/article/abs/pii/S0034425713004483) - In this study, we introduce a new VIIRS active fire detection algorithm, which is driven primarily b...

7. [Assessment of VIIRS 375 m active fire using tropical peatland ...](https://www.tandfonline.com/doi/full/10.1080/17538947.2020.1791268) - The VNP14IMG data is available cost-free on a daily basis. The theoretical 50% probability of detect...

