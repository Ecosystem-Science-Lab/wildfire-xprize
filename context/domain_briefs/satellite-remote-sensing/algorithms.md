# Fire Detection Algorithms and Physics

## Sub-Pixel Fire Detection Theory

### The Planck Function

The spectral radiance of a blackbody at temperature T and wavelength lambda is given by Planck's law:

```
B(lambda, T) = (2 * h * c^2) / (lambda^5 * (exp(h*c / (lambda * k_B * T)) - 1))
```

Where:
- `h` = 6.626e-34 J*s (Planck constant)
- `c` = 2.998e8 m/s (speed of light)
- `k_B` = 1.381e-23 J/K (Boltzmann constant)
- `lambda` = wavelength in meters
- `T` = temperature in Kelvin
- `B` = spectral radiance in W/(m^2 sr um)

For practical satellite radiometry, constants are often combined:

```
c1 = 2 * h * c^2 = 1.191e-16 W*m^2/sr
c2 = h * c / k_B = 1.439e-2 m*K
```

So:
```
B(lambda, T) = c1 / (lambda^5 * (exp(c2 / (lambda * T)) - 1))
```

### Wien's Displacement Law

The wavelength of peak emission:

```
lambda_max = 2898 / T   (um, when T in K)
```

Implications for fire detection:
- Earth surface at 300 K: peak at ~10 um (TIR window)
- Brush fire at 600 K: peak at ~4.8 um
- Hot flaming fire at 800 K: peak at ~3.6 um (right in the MWIR window!)
- Intense fire at 1200 K: peak at ~2.4 um (SWIR)

This is why the 3.9 um channel is the primary fire detection band -- it sits near the emission peak of active fires.

### Temperature Responsivity

The key insight for sub-pixel fire detection: radiance sensitivity to temperature changes is **much greater** at shorter wavelengths. At 3.9 um, radiance approximately follows:

```
B(3.9um, T) ~ T^n   where n ~ 8 for temperatures 300-1000 K
```

At 11 um:
```
B(11um, T) ~ T^n   where n ~ 5 for temperatures 300-1000 K
```

This means a small hot fire raises the 3.9 um pixel-integrated radiance **far more** than the 11 um radiance, creating the detectable BT_3.9 - BT_11 signal.

### Brightness Temperature Inversion

Given a measured spectral radiance L at wavelength lambda, the brightness temperature is obtained by inverting the Planck function:

```
T_B = c2 / (lambda * ln(1 + c1 / (lambda^5 * L)))
```

Where:
- `c1 = 1.191e-8` W/(m^2 sr cm^-4) (when using wavenumber conventions)
- `c2 = 1.439` cm*K

In practice, satellite instruments provide calibrated radiance, and the brightness temperature is computed per-pixel per-band.

**Important:** Brightness temperature equals kinetic temperature only for a perfect blackbody filling the entire pixel. For sub-pixel fires, BT is a complex function of fire fraction, fire temperature, and background temperature.

## The Bi-Spectral Method (Dozier, 1981)

This is the foundational approach for retrieving sub-pixel fire properties using two spectral channels.

### Linear Radiance Mixing Model

Assume a pixel contains a fire at temperature T_f occupying fractional area p, and a background at temperature T_b occupying fraction (1-p):

```
L_MIR = p * B(lambda_MIR, T_f) + (1-p) * B(lambda_MIR, T_b)
L_TIR = p * B(lambda_TIR, T_f) + (1-p) * B(lambda_TIR, T_b)
```

Where:
- `L_MIR` = observed radiance at ~3.9 um (MWIR)
- `L_TIR` = observed radiance at ~11 um (TIR)
- `lambda_MIR` = 3.9 um (AHI B7, VIIRS I4, MODIS B21/22)
- `lambda_TIR` = 11 um (AHI B14, VIIRS I5, MODIS B31)

**Two equations, two unknowns** (T_f and p) if T_b is known from surrounding non-fire pixels. This can be solved numerically.

### Practical Limitations

1. **Assumes single-temperature fire** -- real fires have a distribution of temperatures
2. **Assumes uniform background** -- vegetation heterogeneity introduces errors
3. **Atmospheric effects** -- requires atmospheric correction or assumption of transparent atmosphere
4. **Sensor noise** -- at very small fire fractions, the fire signal is below the noise equivalent delta-temperature (NEdT)
5. **MWIR reflected solar component** -- during daytime, reflected sunlight adds to 3.9 um radiance, must be subtracted

### Minimum Detectable Fire Size

The minimum detectable fire fraction is determined by the sensor's noise floor. A fire is detectable when:

```
Delta_L_MIR = p * [B(lambda_MIR, T_f) - B(lambda_MIR, T_b)] > k * NEdL
```

Where `k` is a detection confidence multiplier (typically 3--5 for low false alarm rate) and `NEdL` is the noise-equivalent spectral radiance.

Rearranging for minimum detectable fire fraction:

```
p_min = (k * NEdL) / [B(lambda_MIR, T_f) - B(lambda_MIR, T_b)]
```

And minimum detectable fire area:

```
A_fire_min = p_min * A_pixel
```

**Worked examples at 3.9 um (nighttime, T_b = 290 K):**

| Fire Temperature | B(3.9, T_f) - B(3.9, T_b) [W/m^2/sr/um] | p_min (AHI, NEdT~0.1K) | Min Fire Area (2 km pixel) | p_min (VIIRS I4) | Min Fire Area (375 m pixel) |
|-----------------|------------------------------------------|------------------------|---------------------------|------------------|-----------------------------|
| 500 K | ~8.5 | ~0.0005 | ~2000 m^2 | ~0.0003 | ~40 m^2 |
| 700 K | ~120 | ~0.00004 | ~160 m^2 | ~0.00002 | ~3 m^2 |
| 900 K | ~700 | ~0.000006 | ~24 m^2 | ~0.000004 | ~0.5 m^2 |
| 1100 K | ~2500 | ~0.000002 | ~8 m^2 | ~0.000001 | ~0.15 m^2 |

**Key insight:** These are theoretical physics limits. Practical detection thresholds are 10--100x higher due to:
- Background heterogeneity (non-uniform T_b)
- Atmospheric absorption and emission
- Daytime reflected solar contamination at 3.9 um
- View geometry effects (pixel enlargement off-nadir)
- Algorithm false-alarm thresholds set conservatively

**Realistic minimum detectable fire sizes:**
- AHI at nadir, nighttime, uniform background: ~4,000 m^2
- VIIRS at nadir, nighttime: ~100--500 m^2
- MODIS at nadir: ~1,000 m^2

## View Geometry Effects

### Geostationary Pixel Size vs View Zenith Angle

For a geostationary satellite at altitude H = 35,786 km above the equator, the view zenith angle (VZA) to a ground point depends on the point's latitude (phi) and longitude difference from the subsatellite point (delta_lambda):

```
cos(VZA) = cos(phi) * cos(delta_lambda)     [simplified, spherical Earth]
```

More precisely, accounting for Earth radius R_E = 6,371 km:

```
gamma = arccos(cos(phi) * cos(delta_lambda))     [central angle]
VZA = arctan(sin(gamma) / (H/R_E - cos(gamma) + 1))   [approximate]
```

### Pixel Enlargement

The pixel size at the ground grows with VZA due to two effects:

1. **Foreshortening (N-S direction):** pixel stretches by factor ~1/cos(VZA)
2. **Path length increase:** pixel stretches further due to longer slant path

The effective pixel area relative to nadir:

```
A_pixel(VZA) / A_pixel(nadir) ~ 1 / cos^3(VZA)    [approximate]
```

### Himawari View Geometry for Australia

Himawari-9 subsatellite point: 0 N, 140.7 E

| Location | Latitude | Longitude | VZA | Pixel Size Factor | Effective B7 Pixel |
|----------|---------|-----------|-----|-------------------|-------------------|
| Darwin | 12.5 S | 130.8 E | ~15 deg | ~1.1x | ~2.2 km |
| Brisbane | 27.5 S | 153.0 E | ~31 deg | ~1.5x | ~3.0 km |
| **Sydney** | **33.9 S** | **151.2 E** | **~37 deg** | **~1.8x** | **~3.6 km** |
| Canberra | 35.3 S | 149.1 E | ~38 deg | ~1.9x | ~3.8 km |
| Melbourne | 37.8 S | 145.0 E | ~40 deg | ~2.0x | ~4.0 km |
| Hobart | 42.9 S | 147.3 E | ~45 deg | ~2.4x | ~4.8 km |

**Impact on fire detection:**
- At Sydney (VZA ~37 deg), the effective pixel area is ~1.8x the nadir value, meaning ~13 km^2 per pixel instead of 4 km^2
- Minimum detectable fire size scales proportionally: ~7,200 m^2 instead of 4,000 m^2
- Geolocation accuracy also degrades: parallax errors from smoke plumes and elevated terrain become significant
- The atmosphere path length is longer by factor 1/cos(VZA) ~ 1.25x, increasing absorption

### View Geometry for LEO Sensors

VIIRS and MODIS have wide swaths (3,040 km and 2,330 km respectively). At swath edges:

- **VIIRS I-band:** 375 m at nadir grows to ~800 m at swath edge (but aggregation scheme limits growth to ~2x)
- **MODIS:** 1 km at nadir grows to ~2 km x 4.8 km (bow-tie effect) at swath edge

For any given location in NSW, the effective spatial resolution depends on where in the swath that location falls during a particular overpass. Near-nadir overpasses provide best detection sensitivity.

## Contextual Fire Detection Algorithm (VIIRS-style)

The standard VIIRS 375 m fire detection algorithm (Schroeder et al., 2014) uses these steps:

### 1. Cloud Masking

Use I5 (11 um) brightness temperature and I1-I3 reflectances to identify and reject cloud-contaminated pixels.

### 2. Water Body Masking

Use land/water mask and I-band reflectance tests to reject water pixels (which can cause sun glint false alarms).

### 3. Candidate Fire Pixel Identification

A pixel is a fire candidate if:

```
BT_I4 > T4_threshold
```

Where `T4_threshold` is typically 310 K (day) or 295 K (night).

### 4. Contextual Tests

For each candidate pixel, compute background statistics from a window of valid (non-fire, non-cloud, non-water) pixels:

```
BT_I4_mean = mean of background I4 BT values
BT_I4_mad = mean absolute deviation of background I4 BT
DeltaBT_mean = mean of (BT_I4 - BT_I5) for background
DeltaBT_mad = MAD of (BT_I4 - BT_I5) for background
```

Fire is confirmed if:

```
BT_I4 > BT_I4_mean + max(3 * BT_I4_mad, delta_T4)
AND
(BT_I4 - BT_I5) > DeltaBT_mean + max(3 * DeltaBT_mad, delta_DT)
AND
BT_I4 > T4_absolute_threshold
```

Where `delta_T4` and `delta_DT` are minimum threshold floors that prevent detection in highly uniform backgrounds where MAD is near zero.

### 5. Daytime Sun Glint Rejection

Check if the pixel is within the sun glint geometry (specular reflection angle < threshold). If so, apply stricter thresholds or reject.

### 6. Confidence Assignment

- **High confidence:** I4 saturated (BT_I4 >= 367 K)
- **Nominal confidence:** passes contextual tests with margin > 15 K
- **Low confidence:** marginal detection or within sun glint zone

## Landsat Active Fire Algorithm

Unlike VIIRS/MODIS, the Landsat fire algorithm uses **reflective SWIR bands** rather than thermal bands:

### Detection Logic

```
Fire = (B7_reflectance / B4_reflectance) > threshold_ratio
  AND B7_reflectance > threshold_B7
  AND B6_reflectance > threshold_B6
```

Where B7 = 2.2 um SWIR and B4 = 0.66 um Red.

The physics: at fire temperatures (600--1200 K), thermal emission at 2.2 um is significant and dominates reflected solar for hot targets. The ratio B7/B4 increases dramatically for fire pixels because B4 (red) has negligible fire emission.

**Advantages:**
- 30 m resolution enables ~4 m^2 fire detection
- Works in daytime (the primary observation mode)
- No saturation issues at fire temperatures in reflective bands

**Disadvantages:**
- Nighttime detection not possible (no solar illumination for reflective bands)
- TIRS thermal bands (100 m, resampled to 30 m) can supplement but have coarser native resolution

## Sentinel-2 Fire Detection Approach

Since Sentinel-2 has no thermal band, fire detection uses SWIR:

### High-Temperature Anomaly (HTA) Detection

```
HTA_index = (B12 - B11) / (B12 + B11)    [SWIR ratio]
```

Or simpler thresholds:
```
Fire candidate if:
  B12_TOA_reflectance > 0.15
  AND B12/B4 > threshold
  AND spatial context anomaly
```

### Normalized Burn Ratio (NBR)

For burn scar mapping (post-fire):
```
NBR = (B8 - B12) / (B8 + B12)
dNBR = NBR_pre - NBR_post
```

### Limitations for Active Fire

- Daytime only (solar reflectance needed)
- SWIR fire emission mixed with reflected solar -- hard to separate for small fires
- No thermal channel means no BT-based detection or sub-pixel temperature retrieval
- Better for confirming already-known fires and mapping burn extent than for initial detection

## Fire Radiative Power (FRP)

FRP is estimated from the excess MWIR radiance above background:

```
FRP = A_pixel * sigma_SB / (B(lambda_MIR, T_b)) * [L_MIR_observed - L_MIR_background]
```

A simplified empirical form (Wooster et al., 2003):

```
FRP (MW) = 4.34e-19 * (T_4^8 - T_4bg^8) * A_pixel
```

Where T_4 and T_4bg are 4 um brightness temperatures of the fire and background pixels in Kelvin, and A_pixel is pixel area in m^2.

FRP is proportional to the rate of biomass combustion and is a key metric for fire intensity classification.
