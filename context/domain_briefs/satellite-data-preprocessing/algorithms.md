# Algorithms: Calibration, Atmospheric Correction, and Cloud Detection

## 1. Radiometric Calibration

### 1.1 General Principle: Planck Function

The inverse Planck function converts spectral radiance to brightness temperature:

```
T_B = (h*c) / (k_B * lambda) * 1/ln(1 + 2*h*c^2 / (L * lambda^5))
```

Where:
- `h` = Planck's constant (6.626e-34 J*s)
- `c` = speed of light (2.998e8 m/s)
- `k_B` = Boltzmann constant (1.381e-23 J/K)
- `lambda` = central wavelength (m)
- `L` = spectral radiance (W/m^2/sr/m)

In practice, sensors use band-integrated "effective" Planck functions with correction coefficients.

### 1.2 VIIRS Thermal Emissive Bands (I4, I5)

VIIRS SDR products have calibration already applied. The L1b/SDR pipeline internally uses:

**DN to radiance:**
```
L_EV = F * (c0 + c1*dn_EV + c2*dn_EV^2) / RVS_EV
```
Where:
- `F` = scan-by-scan F-factor from onboard blackbody (F = L_BB / L_retrieved)
- `c0, c1, c2` = pre-launch calibration coefficients (temperature-dependent)
- `dn_EV` = background-subtracted detector response (DN - space_view)
- `RVS_EV` = response vs. scan angle at Earth view half-angle mirror position

**When using SDR/L1b products, this is already done.** What you receive is calibrated radiance. You then convert to brightness temperature using the Planck function.

**VIIRS band-specific Planck parameters** (approximate effective values):

| Band | Center wavelength (um) | Use |
|------|----------------------|-----|
| I4 | 3.740 | Primary fire detection (MIR) |
| I5 | 11.450 | Background characterization (TIR) |
| M13 | 4.050 | Fire detection, dual gain |

I4 saturates at ~367K (important: fires above this can't be measured with I4 alone). M13 has dual-gain mode that extends to ~634K for fire characterization.

### 1.3 Himawari AHI

**DN to radiance (linear):**
```
Radiance = DN * gain + offset
```
Where `gain` and `offset` come from the HSD file header (Block 5 for nominal, Block 6 for updated VIS coefficients).

**Radiance to brightness temperature:**
```python
# From satpy's ahi_hsd.py implementation
cwl = central_wave_length * 1e-6  # convert um to m
a = (h * c) / (k * cwl)
b = ((2 * h * c**2) / (radiance * 1e6 * cwl**5)) + 1
Te = a / log(b)

# Apply band-specific correction coefficients
BT = c0 + c1 * Te + c2 * Te**2
```
The `c0, c1, c2` correction coefficients account for the finite spectral bandwidth of each band (stored in the calibration header block).

**Reflectance (visible bands):**
```
Reflectance = Radiance * coeff_rad2albedo * 100  # result in percent
```

### 1.4 GOES ABI

L1b products provide calibrated radiance in netCDF. The conversion to brightness temperature uses:

**Radiance to BT:**
```
T = (fk2 / ln(fk1/R + 1) - bc1) / bc2
```

**BT to radiance (inverse):**
```
R = fk1 / (exp(fk2 / (bc1 + bc2*T)) - 1)
```

Where `fk1, fk2, bc1, bc2` are band-specific Planck function constants stored IN the L1b netCDF file as variables:
- `planck_fk1` -- units same as radiance (mW/m^2/sr/cm^-1)
- `planck_fk2` -- units: K
- `bc1` -- units: K
- `bc2` -- dimensionless

Key ABI IR bands for fire detection:
| Band | Wavelength | Typical use |
|------|-----------|-------------|
| B07 | 3.9 um | Shortwave IR, fire detection primary |
| B13 | 10.3 um | Clean longwave IR window |
| B14 | 11.2 um | Longwave IR, BT differencing |
| B15 | 12.3 um | Dirty longwave IR window |

### 1.5 Landsat OLI/TIRS

**DN to TOA radiance:**
```
L_lambda = M_L * Q_cal + A_L
```
Where `M_L` = `RADIANCE_MULT_BAND_x`, `A_L` = `RADIANCE_ADD_BAND_x` from MTL.txt metadata.

**TOA radiance to brightness temperature:**
```
T = K2 / ln(K1/L_lambda + 1)
```
Where `K1, K2` are thermal conversion constants from MTL metadata (`K1_CONSTANT_BAND_x`, `K2_CONSTANT_BAND_x`).

Typical Landsat 8/9 thermal constants:
| Band | K1 (W/m^2/sr/um) | K2 (K) |
|------|-------------------|--------|
| B10 (10.9um) | 774.89 | 1321.08 |
| B11 (12.0um) | 480.89 | 1201.14 |

**DN to TOA reflectance (reflective bands):**
```
rho = (M_rho * Q_cal + A_rho) / sin(sun_elevation)
```

### 1.6 Sentinel-2

L1C products provide TOA reflectance. Values are stored as integers with a quantification value (typically 10000):
```
reflectance = DN / 10000.0
```

No thermal bands exist on Sentinel-2. Fire detection uses SWIR anomalies:
- B12 (2.19 um) -- primary fire signal (SWIR2)
- B11 (1.61 um) -- secondary fire signal (SWIR1)
- B8A (0.865 um) -- NIR for NBR calculation

---

## 2. Atmospheric Correction

### 2.1 When to Skip It (Fire Detection)

**For thermal-band fire detection: skip full atmospheric correction.**

Rationale:
- Fire algorithms (MOD14, VNP14, WF-ABBA) operate on brightness temperature, not land surface temperature.
- Contextual algorithms compare a candidate pixel against its neighbors. All pixels share approximately the same atmospheric path, so atmospheric effects cancel in the difference.
- The brightness temperature difference (e.g., T_4um - T_11um) is itself a partial atmospheric correction: the split-window technique exploits differential atmospheric absorption between bands.
- Full atmospheric correction (e.g., via MODTRAN/6S) is computationally expensive and requires ancillary atmospheric profile data with latency.

**Exception:** If you need land surface temperature (LST) for fire severity assessment or fuel moisture estimation, you do need atmospheric correction.

### 2.2 When to Apply It

- Sentinel-2 SWIR-based fire detection: atmospheric correction helps with consistent reflectance values across scenes, but L1C TOA reflectance works for fire detection. In fact, L2A processing can struggle with smoke plumes (confuses smoke with cloud, introduces artifacts near active fires). **For fire detection with Sentinel-2, prefer L1C.**
- Landsat: same logic. TOA reflectance (with sun angle correction) is usually adequate for fire detection.
- Multi-temporal change detection: atmospheric correction improves consistency across dates, but again not critical for fire detection.

### 2.3 Methods (When Needed)

**6S / Py6S** -- Second Simulation of the Satellite Signal in the Solar Spectrum:
- Full radiative transfer model for solar bands (not thermal)
- Too slow for per-pixel correction (~2 seconds per pixel per band)
- Useful for generating lookup tables (LUTs): pre-compute corrections for discrete atmospheric states, interpolate at runtime

**6S Emulator** (github.com/samsammurphy/6S_emulator):
- Machine learning emulator trained on 6S outputs
- Orders of magnitude faster than running 6S directly
- Generates correction coefficients for Landsat/Sentinel-2

**MODTRAN:**
- More comprehensive than 6S (covers thermal wavelengths)
- Commercial license required
- Used for generating atmospheric correction coefficients for LST retrieval

**Split-window technique** (practical for thermal):
```
LST = T_11 + c1*(T_11 - T_12) + c2*(T_11 - T_12)^2 + c0 + (c3 + c4*W)*(1-emissivity) + (c5 + c6*W)*delta_emissivity
```
Where `W` = atmospheric water vapor, `emissivity` = surface emissivity. This provides approximate atmospheric correction using two thermal bands without running a radiative transfer model.

---

## 3. Cloud Detection Algorithms

### 3.1 Why Cloud Masking is Critical for Fire Detection

- Clouds directly obscure fires (missed detections)
- Cloud edges produce steep brightness temperature gradients that mimic fire signatures (false positives)
- Sun-illuminated cloud edges can produce high MIR radiance
- Optically thin cirrus reduces apparent fire brightness temperature
- The penalty for false positives (false alarms erode trust) often exceeds the penalty for missed detections

### 3.2 VIIRS Cloud Mask (VCM)

The VCM is "clear-sky conservative" -- if any single cloud test flags a pixel as cloudy with high confidence, the pixel is classified as cloudy. This is good for fire detection (better to miss a fire pixel than false-alarm on a cloud).

VCM uses tests across VIIRS bands:
- Visible reflectance tests (daytime)
- 11um brightness temperature tests
- 3.9-11um brightness temperature difference (discriminates low cloud)
- 1.38um cirrus test
- Spatial uniformity tests
- I-band edge tests for sub-pixel cloud edges

VCM output categories:
- Confidently clear
- Probably clear
- Probably cloudy
- Confidently cloudy

**For fire detection: treat "probably cloudy" and "confidently cloudy" as cloud.**

Night-time VCM accuracy: ~86.4% correct, 4.4% false alarm, 7.3% missed cloud.

### 3.3 Himawari AHI Cloud Products

CLAVR-x (Clouds from AVHRR Extended) system processes AHI data:
- Uses infrared, visible, and NIR channels
- Night-time mode uses IR-only tests
- Available as standard product

For faster custom cloud screening (useful for a real-time pipeline):

**Simple thermal threshold approach:**
```python
# Fast cloud screening for AHI
cloud_mask = np.zeros_like(bt_11um, dtype=bool)

# Test 1: Cold clouds (11um BT below threshold)
cloud_mask |= bt_11um < 265.0  # K, tune for region/season

# Test 2: Cirrus (8.6um - 11um difference)
cloud_mask |= (bt_86um - bt_11um) > 2.5  # thin cirrus signature

# Test 3: Low cloud (3.9um - 11um difference, daytime)
if is_daytime:
    cloud_mask |= (bt_39um - bt_11um) > 15.0  # reflected solar component

# Test 4: Spatial uniformity (high variance = cloud edges)
from scipy.ndimage import uniform_filter
bt_std = np.sqrt(uniform_filter(bt_11um**2, 5) - uniform_filter(bt_11um, 5)**2)
cloud_mask |= bt_std > 3.0  # K
```

### 3.4 Sentinel-2 Cloud Detection (s2cloudless)

ML-based cloud detection using 10 spectral bands:

**Input bands:** B01, B02, B04, B05, B08, B8A, B09, B10, B11, B12

**Output:** Per-pixel cloud probability (0-1) and binary cloud mask.

Algorithm: gradient-boosted decision trees trained on manually labeled cloud/clear data.

**Key parameters:**
- `threshold` -- cloud probability threshold (default 0.4)
- `average_over` -- pixel neighborhood for averaging probabilities
- `dilation_size` -- morphological dilation radius for cloud buffer

The Sentinel-2 L2A product also includes a Scene Classification Layer (SCL) with cloud classes, but s2cloudless is generally more accurate, particularly at cloud edges.

### 3.5 Fast Cloud Screening for Real-Time Fire Detection

For a pipeline that must run within a 10-minute window (Himawari cadence), a tiered approach works:

**Tier 1: Quick reject (sub-second)**
- Static cloud climatology: reject pixels where cloud probability exceeds some threshold based on historical cloud frequency
- Night: single 11um BT threshold

**Tier 2: Spectral tests (seconds)**
- Brightness temperature difference tests (3.9-11um, 8.6-11um, 11-12um)
- Clear-sky BT composite comparison (pixel BT vs recent clear-sky value)

**Tier 3: Spatial/temporal consistency (seconds)**
- If a "fire" pixel appears in a region that was cloud-covered 10 minutes ago, it is probably a cloud edge artifact
- Track cloud motion to predict where cloud edges will be

---

## 4. Fire Detection Algorithm Reference

### 4.1 VIIRS 375m Active Fire (VNP14IMG / Schroeder et al. 2014)

This is the reference algorithm for VIIRS-based fire detection.

**Inputs:** I4 (3.74um) and I5 (11.45um) brightness temperatures from SDR.

**Processing flow:**
1. Apply cloud mask (internal, using VCM or simplified cloud tests)
2. Apply land/water mask (quarterly product)
3. Identify candidate fire pixels using absolute BT thresholds
4. Apply contextual tests comparing candidates to background
5. Reject false alarms (sun glint, bright surfaces)
6. Calculate Fire Radiative Power (FRP)

**Absolute thresholds:**
- Daytime: T_I4 > 325-330K (adaptive based on background variability)
- Nighttime: T_I4 > 310K (fixed; nighttime background is more stable)
- Day/night boundary: solar zenith angle > 85 degrees = nighttime

**Contextual tests (simplified):**
```
Fire confirmed if ALL of:
  T_I4 > T_I4_bg_mean + 3 * T_I4_bg_stdev
  delta_T > delta_T_bg_mean + 3 * delta_T_bg_stdev
  T_I4 > T_I4_bg_mean + 6K

Where:
  delta_T = T_I4 - T_I5
  Background computed from surrounding window (excluding cloud, water, other fire candidates)
  Minimum 10 valid background pixels required
```

**I4 saturation:** I4 saturates at ~367K. For saturated pixels, I5 > I4 indicates saturation (normally fire pixels show I4 >> I5). M13 band (dual gain, saturates at ~634K) can be used for FRP retrieval of intense fires.

### 4.2 MODIS MOD14 Algorithm

Similar to VIIRS but at 1km resolution using bands 21/22 (3.96um) and 31 (11.03um). Operates on L1b brightness temperatures directly (no atmospheric correction). The algorithm is the foundation that VIIRS and geostationary fire products adapted.

### 4.3 Geostationary Fire Detection (Himawari/GOES)

Adapted from MOD14 for geostationary sensors (2km resolution). Key difference: temporal context is available (can compare current BT to previous observation 10 minutes ago), which helps reject cloud-edge false positives and detect rapidly emerging fires.
