# Sub-Pixel Fire Detection Physics

Reference document for the radiative physics underlying satellite-based fire detection.
Covers Planck radiation, mixed-pixel models, minimum detectable fire area, emissivity,
reflected solar contamination, signal-to-noise analysis, and fire radiative power.

---

## 1. Planck Function and Blackbody Radiation

### 1.1 The Planck Function

The spectral radiance of a blackbody at temperature T and wavelength lambda is:

```
B(lambda, T) = C1 / (lambda^5 * (exp(C2 / (lambda * T)) - 1))
```

where:
- `C1 = 2hc^2 = 1.191042 x 10^8  W m^-2 sr^-1 um^-4`  (first radiation constant for spectral radiance, with lambda in um)
- `C2 = hc/k  = 1.4387770 x 10^4  um K`                 (second radiation constant, with lambda in um)
- `h  = 6.62607 x 10^-34 J s`       (Planck constant)
- `c  = 2.99792 x 10^8  m s^-1`     (speed of light)
- `k  = 1.38065 x 10^-23 J K^-1`    (Boltzmann constant)

Output units: **W m^-2 sr^-1 um^-1** (spectral radiance per micrometre of wavelength).

Note on constants: The form above uses C1 = 2hc^2 (not 2*pi*hc^2) because this is the
*spectral radiance* form (per steradian), not the spectral emittance (hemispherical) form.
When you see c1L = 1.191 x 10^8 in remote sensing literature, it already accounts for the
2hc^2 factor with lambda in micrometres.

For computation in Python/code, it is often more practical to use:
```
C1 = 1.19104e8    # W m^-2 sr^-1 um^-4
C2 = 1.43878e4    # um K

B = C1 / (lam**5 * (exp(C2 / (lam * T)) - 1))
```
where `lam` is in micrometres and `T` in kelvin.

### 1.2 Wien's Displacement Law

The wavelength of peak spectral radiance for a blackbody at temperature T:

```
lambda_max = 2897.8 / T    [um]
```

| Temperature (K) | Peak wavelength (um) | Regime            |
|-----------------|----------------------|-------------------|
| 300             | 9.66                 | Earth surface     |
| 500             | 5.80                 | Smoldering fire   |
| 800             | 3.62                 | Flaming front     |
| 1000            | 2.90                 | Intense flame     |
| 1200            | 2.41                 | Hot flame core    |
| 1500            | 1.93                 | Very hot flame    |
| 5778            | 0.50                 | Sun (visible)     |

**Key insight**: Fires (800-1200 K) have their peak emission near 2.4-3.6 um, which is
much closer to the 3.9 um MIR band than to the 11 um TIR band. The Earth's ambient
surface (~300 K) peaks near 9.7 um, close to the 11 um band.

### 1.3 Why 3.9 um Is Far More Sensitive to Fire Than 11 um

The exponential term `exp(C2 / (lambda * T))` dominates the behaviour. At short wavelengths
relative to the temperature, a small temperature increase produces a dramatic radiance
increase because the exponent `C2/(lambda*T)` is large and the function is on the steep
Wien-law side of the Planck curve.

**Worked example: Radiance at 3.9 um**

```
At 3.9 um, C2/(lambda) = 14388 / 3.9 = 3689.7 K

For T = 300 K:  exponent = 3689.7 / 300  = 12.299
                exp(12.299) = 2.195 x 10^5
                B(3.9, 300) = 1.191e8 / (3.9^5 * (2.195e5 - 1))
                            = 1.191e8 / (9.0224e2 * 2.195e5)
                            = 1.191e8 / 1.981e8
                            = 0.60 W m^-2 sr^-1 um^-1

For T = 1000 K: exponent = 3689.7 / 1000 = 3.6897
                exp(3.6897) = 39.87
                B(3.9, 1000) = 1.191e8 / (9.0224e2 * (39.87 - 1))
                             = 1.191e8 / (9.0224e2 * 38.87)
                             = 1.191e8 / 3.507e4
                             = 3384 W m^-2 sr^-1 um^-1
```

**Radiance ratio at 3.9 um (1000 K fire vs 300 K background):**
```
B(3.9, 1000) / B(3.9, 300) = 3384 / 0.60 = 5616
```

**Worked example: Radiance at 11 um**

```
At 11 um, C2/(lambda) = 14388 / 11.0 = 1308.0 K

For T = 300 K:  exponent = 1308.0 / 300  = 4.360
                exp(4.360) = 78.26
                B(11, 300) = 1.191e8 / (11.0^5 * (78.26 - 1))
                           = 1.191e8 / (1.6105e5 * 77.26)
                           = 1.191e8 / 1.244e7
                           = 9.57 W m^-2 sr^-1 um^-1

For T = 1000 K: exponent = 1308.0 / 1000 = 1.308
                exp(1.308) = 3.699
                B(11, 1000) = 1.191e8 / (1.6105e5 * (3.699 - 1))
                            = 1.191e8 / (1.6105e5 * 2.699)
                            = 1.191e8 / 4.348e5
                            = 273.9 W m^-2 sr^-1 um^-1
```

**Radiance ratio at 11 um (1000 K fire vs 300 K background):**
```
B(11, 1000) / B(11, 300) = 273.9 / 9.57 = 28.6
```

### 1.4 Summary: Sensitivity Contrast

| Wavelength | B(300 K)          | B(1000 K)           | Ratio (1000/300) |
|------------|-------------------|---------------------|------------------|
| 3.9 um     | ~0.60 W/m^2/sr/um | ~3384 W/m^2/sr/um   | **~5616x**       |
| 11.0 um    | ~9.6 W/m^2/sr/um  | ~274 W/m^2/sr/um    | **~29x**         |

A 1000 K fire is ~5600 times brighter than 300 K background at 3.9 um, but only ~29 times
brighter at 11 um. This is why the MIR band at 3.9 um is the primary fire detection channel:
even a tiny sub-pixel fire produces a measurable signal at 3.9 um while being nearly
invisible at 11 um.

---

## 2. Mixed-Pixel Radiance Model (Dozier Equations)

### 2.1 The Two-Component Model

A satellite pixel of area A_pixel contains a fire of area A_fire at temperature Tf,
surrounded by background at temperature Tb. The fire fraction is:

```
p = A_fire / A_pixel
```

The observed spectral radiance at wavelength lambda is the area-weighted sum:

```
L(lambda) = p * B(lambda, Tf) + (1 - p) * B(lambda, Tb)
```

This model, introduced by Matson and Dozier (1981), assumes:
- The pixel contains exactly two thermal components (fire and background)
- Both components emit as blackbodies (or greybodies with known emissivity)
- The fire is uniform at temperature Tf
- The background is uniform at temperature Tb
- Atmospheric effects have been corrected

### 2.2 The Bi-Spectral Inversion (Dozier 1981)

With measurements at two wavelengths (lambda_MIR ~ 3.9 um and lambda_TIR ~ 11 um),
we get two equations with two unknowns (p and Tf), assuming Tb is known from
the surrounding non-fire pixels:

```
L_MIR = p * B(3.9, Tf) + (1 - p) * B(3.9, Tb)     ... (1)
L_TIR = p * B(11, Tf)  + (1 - p) * B(11, Tb)       ... (2)
```

Rearranging equation (1) for p:

```
p = (L_MIR - B(3.9, Tb)) / (B(3.9, Tf) - B(3.9, Tb))
```

Similarly from equation (2):

```
p = (L_TIR - B(11, Tb)) / (B(11, Tf) - B(11, Tb))
```

Setting these equal gives one equation in one unknown (Tf):

```
(L_MIR - B(3.9, Tb))     (L_TIR - B(11, Tb))
--------------------- = ---------------------
(B(3.9, Tf) - B(3.9, Tb))   (B(11, Tf) - B(11, Tb))
```

This is a transcendental equation that must be solved numerically (e.g., Newton-Raphson
or lookup table). Once Tf is found, p follows from either equation above.

### 2.3 Practical Solution Method

1. Determine Tb from surrounding non-fire pixels (spatial context).
2. Measure L_MIR and L_TIR (observed pixel radiances after atmospheric correction).
3. Define f(Tf) = p_MIR(Tf) - p_TIR(Tf) and find Tf where f(Tf) = 0.
4. Compute p from either band's equation.
5. Compute fire area: A_fire = p * A_pixel.

### 2.4 Well-Conditioned vs Ill-Conditioned Solutions

The Dozier retrieval works best when:
- **Fire temperature is 700-1200 K** (the MIR and TIR radiance curves are sufficiently
  different functions of Tf to provide independent constraints)
- **Fire fraction p > ~0.0005** (the fire signal must be detectable above noise)
- **Background temperature is well-characterized** (errors in Tb propagate strongly
  into Tf and p estimates)

The retrieval becomes **ill-conditioned** when:
- **Tf < ~600 K**: Both bands respond more similarly to temperature changes, so the
  two equations become nearly linearly dependent. Small measurement errors produce
  large errors in Tf and p.
- **Tf > ~1500 K**: At very high temperatures, the MIR channel may saturate, and the
  radiance curve flattens (relative to the exponential).
- **Very small p (< 0.0001)**: The fire signal is buried in noise at both wavelengths.
- **Tb uncertainty > ~1-2 K**: Because p is typically very small (10^-4 to 10^-2),
  the background radiance term (1-p)*B(lambda, Tb) dominates the pixel radiance.
  Even small errors in Tb can exceed the fire contribution, making the retrieval
  unstable.

**Sensitivity analysis** (Giglio & Kendall 2001): The Dozier method retrieves fire
temperature most reliably in the 750-950 K range, where the RMSE range is smallest.
Outside this range, retrieved Tf and p become increasingly uncertain.

### 2.5 Extension to Emissivity

In practice, surfaces are not perfect blackbodies. The model becomes:

```
L(lambda) = p * epsilon_f(lambda) * B(lambda, Tf)
          + (1 - p) * epsilon_b(lambda) * B(lambda, Tb)
```

where epsilon_f and epsilon_b are the fire and background emissivities at wavelength
lambda. In most fire detection algorithms, epsilon_f is assumed ~ 1.0 for the flame/hot
surface, and epsilon_b is estimated from land surface databases.

---

## 3. Minimum Detectable Fire Area

### 3.1 Detection Criterion

A fire is detectable when the brightness temperature increase at 3.9 um exceeds the
sensor noise level by a sufficient margin:

```
Delta_BT >= n * NEdT
```

where `n` is typically 3-5 for robust detection (3-sigma or 5-sigma threshold) in
contextual algorithms, though operational algorithms also use adaptive thresholds
based on the spatial context of surrounding pixels.

### 3.2 Deriving the Brightness Temperature Increase

The observed pixel radiance at 3.9 um with fire:

```
L_obs = p * B(3.9, Tf) + (1 - p) * B(3.9, Tb)
```

Without fire, the pixel radiance would be B(3.9, Tb). The radiance increase is:

```
Delta_L = L_obs - B(3.9, Tb) = p * [B(3.9, Tf) - B(3.9, Tb)]
```

The brightness temperature increase Delta_BT is related to Delta_L by:

```
Delta_BT approx= Delta_L / (dB/dT)|_{Tb}
```

where dB/dT is the derivative of the Planck function evaluated at the background temperature:

```
dB/dT = B(lambda, T) * (C2 / (lambda * T^2)) * exp(C2/(lambda*T)) / (exp(C2/(lambda*T)) - 1)
```

At 3.9 um and Tb = 300 K:
```
dB/dT|_{3.9, 300} approx= 0.0247 W m^-2 sr^-1 um^-1 K^-1
```

So the minimum detectable fire fraction is:

```
p_min = (n * NEdT * dB/dT) / (B(3.9, Tf) - B(3.9, Tb))
```

And the minimum detectable fire area is:

```
A_fire_min = p_min * A_pixel
```

### 3.3 Sensor Specifications

| Sensor          | Band       | Wavelength | NEdT (K)   | Pixel nadir | Pixel NSW*  | Saturation (K) |
|-----------------|------------|------------|------------|-------------|-------------|-----------------|
| VIIRS I4        | I4         | 3.74 um    | 0.4-0.7    | 375 m       | ~500 m      | 367             |
| Himawari AHI    | Band 7     | 3.9 um     | <=0.16     | 2 km        | ~3-4 km     | ~400            |
| GOES-16/17 ABI  | Ch 7       | 3.9 um     | <=0.1      | 2 km        | N/A (Americas) | ~400         |
| Landsat TIRS    | Band 10    | 10.9 um    | ~0.05      | 100 m       | 100 m       | ~360            |
| MODIS           | Ch 21/22   | 3.96 um    | 0.07       | 1 km        | ~1.3 km     | 500 (Ch21)/331  |

*NSW pixel size accounts for viewing geometry from satellite to NSW Australia
(~33 S latitude). For geostationary satellites like Himawari (140.7 E), pixels
over NSW are typically 1.3-1.5x larger than nadir due to Earth curvature.

**VIIRS I4 note**: The I4 band saturates at 367 K, which means hot fires saturate
the sensor. The M13 band (4.05 um, 750 m) has a dual-gain design with high-gain
saturation at 343 K and low-gain saturation at 634 K, and is used as a complement
for characterizing saturated fire pixels. The NEdT specification for I4 is 2.5 K
at 210 K scene temperature; at typical fire-detection background temperatures
(~300 K), the effective NEdT is lower, around 0.14-0.18 K based on on-orbit
performance characterization.

**Landsat TIRS note**: Landsat TIRS does not have a MIR (3.9 um) band. It operates
only at 10.9 um (Band 10) and 12.0 um (Band 11). While it achieves remarkable
NEdT of ~0.05 K, it can only detect fires through the relatively insensitive TIR
window. Its 100 m native resolution (resampled to 30 m in products) partially
compensates. Landsat fire detection requires extremely hot or large fires.

### 3.4 Minimum Detectable Fire Area: Worked Examples

For each sensor, we compute the minimum fire area detectable at 3-sigma above noise,
assuming a fire at 800 K and background at 300 K.

**Common values:**
```
B(3.9, 800)  = ~1325 W/m^2/sr/um   (from Planck function)
B(3.9, 300)  = ~0.60 W/m^2/sr/um
B(3.9, 800) - B(3.9, 300) = ~1324 W/m^2/sr/um

dB/dT at (3.9, 300) = ~0.0245 W/m^2/sr/um/K
```

**VIIRS I4 (375 m pixel):**
```
NEdT = 0.4 K (specification; ~0.15 K on-orbit)
A_pixel = 375^2 = 140,625 m^2
Threshold = 3 * 0.4 = 1.2 K

p_min = 1.2 * 0.0247 / 1324 = 2.24 x 10^-5
A_fire_min = 2.24e-5 * 140625 = ~3.1 m^2

Using on-orbit NEdT of 0.15 K:
Threshold = 3 * 0.15 = 0.45 K
p_min = 0.45 * 0.0247 / 1324 = 8.39 x 10^-6
A_fire_min = 8.39e-6 * 140625 = ~1.2 m^2
```

**Himawari AHI Band 7 (2 km pixel at nadir, ~3.5 km over NSW):**
```
NEdT = 0.16 K
A_pixel (at NSW) = 3500^2 = 12,250,000 m^2
Threshold = 3 * 0.16 = 0.48 K

p_min = 0.48 * 0.0247 / 1324 = 8.95 x 10^-6
A_fire_min = 8.95e-6 * 12,250,000 = ~110 m^2

At nadir (2 km pixel):
A_pixel = 4,000,000 m^2
A_fire_min = 8.95e-6 * 4,000,000 = ~36 m^2
```

**GOES ABI Ch 7 (2 km pixel):**
```
NEdT = 0.1 K (specification; ~0.05 K measured on-orbit)
A_pixel = 2000^2 = 4,000,000 m^2
Threshold = 3 * 0.1 = 0.3 K

p_min = 0.3 * 0.0247 / 1324 = 5.59 x 10^-6
A_fire_min = 5.59e-6 * 4,000,000 = ~22 m^2
```

**Landsat TIRS Band 10 (100 m pixel, 10.9 um band):**

Landsat lacks a MIR band, so we must use the 10.9 um channel where fire sensitivity
is much lower (see Section 1 radiance ratios):

```
B(10.9, 800) - B(10.9, 300) approx= 174 W/m^2/sr/um  (much smaller ratio than MIR)
dB/dT at (10.9, 300) approx= 0.143 W/m^2/sr/um/K

NEdT = 0.05 K
A_pixel = 100^2 = 10,000 m^2
Threshold = 3 * 0.05 = 0.15 K

p_min = 0.15 * 0.143 / 174 = 1.23 x 10^-4
A_fire_min = 1.23e-4 * 10,000 = ~1.2 m^2
```

Despite the lower sensitivity at 10.9 um, Landsat's small pixel size (100 m)
yields a competitive minimum detectable fire area. However, the TIR-only approach
is much more susceptible to false alarms from warm (non-fire) surfaces.

### 3.5 Effect of Fire Temperature on Minimum Detectable Area

The MIR radiance of the fire increases extremely steeply with temperature.
Minimum detectable area for a 3-sigma detection in a 2 km Himawari pixel (3.5 km over NSW):

| Fire Temp (K) | B(3.9,Tf) W/m^2/sr/um | Delta_B from 300K | p_min      | A_fire_min (m^2) |
|---------------|------------------------|-------------------|------------|------------------|
| 500           | 82.5                   | 81.9              | 1.45e-4    | 1,773            |
| 600           | 283                    | 282               | 4.20e-5    | 515              |
| 700           | 682                    | 682               | 1.74e-5    | 213              |
| 800           | 1325                   | 1324              | 8.95e-6    | 110              |
| 900           | 2227                   | 2226              | 5.33e-6    | 65               |
| 1000          | 3384                   | 3383              | 3.50e-6    | 43               |
| 1200          | 6397                   | 6397              | 1.85e-6    | 23               |

At low fire temperatures (~500 K, smoldering), thousands of square metres are needed.
At high temperatures (~1000 K, intense flaming), tens of square metres suffice.

---

## 4. Surface Emissivity

### 4.1 Emissivity Values by Surface Type and Wavelength

Real surfaces emit less radiation than a perfect blackbody. The actual radiance is:

```
L(lambda, T) = epsilon(lambda) * B(lambda, T)
```

| Surface Type              | epsilon (3.9 um) | epsilon (11 um) | Notes                          |
|---------------------------|------------------|-----------------|--------------------------------|
| Water (ocean/lake)        | 0.97-0.98        | 0.98-0.99       | High, spectrally flat          |
| Green vegetation canopy   | 0.94-0.97        | 0.97-0.99       | High in TIR; slightly lower MIR|
| Eucalyptus forest         | 0.95-0.97        | 0.97-0.98       | Similar to general vegetation  |
| Dry grass/senescent veg   | 0.90-0.95        | 0.93-0.97       | Reduced by cellulose features  |
| Bare soil (sandy)         | 0.85-0.92        | 0.90-0.96       | Quartz reststrahlen at 8-10 um |
| Bare soil (clay)          | 0.92-0.96        | 0.95-0.98       | Higher than sandy soils        |
| Bare rock (silicate)      | 0.80-0.90        | 0.85-0.95       | Strong mineral features        |

**Key points:**
- At 3.9 um, emissivities are generally 0.02-0.05 lower than at 11 um
- This means 1/epsilon is higher at 3.9 um, so reflectivity rho = 1 - epsilon is higher
  at 3.9 um, leading to more reflected solar radiation during daytime (see Section 5)
- Emissivity variations of 0.01-0.02 translate to brightness temperature errors of
  0.5-2 K, which is significant for fire detection thresholds
- Eucalyptus forests in NSW have emissivities in the 0.95-0.98 range across both bands

### 4.2 Emissivity Impact on Brightness Temperature

Brightness temperature (BT) is defined as the temperature a blackbody would need to
produce the observed radiance. For a surface with emissivity epsilon at temperature T:

```
L_observed = epsilon * B(lambda, T)

BT = B^(-1)(lambda, L_observed)
```

Because epsilon < 1, BT < T (the surface appears cooler than it actually is). The
brightness temperature depression is approximately:

```
Delta_T_emissivity approx= -T * (1 - epsilon) * lambda * T / C2
```

For typical values (T=300 K, epsilon=0.96, lambda=11 um):
```
Delta_T approx= -300 * 0.04 * 11 * 300 / 14388 = -2.75 K
```

This 2-3 K bias must be accounted for in fire detection algorithms, especially
when computing the background temperature from contextual pixels.

### 4.3 Emissivity Difference Between Bands

The emissivity difference between 3.9 um and 11 um affects the Dozier retrieval.
If we assume the same emissivity at both wavelengths but it is actually different,
the retrieved Tf and p will be biased. For Australian eucalypt forest:

```
epsilon(3.9) approx= 0.96
epsilon(11)  approx= 0.98
```

This 0.02 difference is significant enough to warrant correction in operational
algorithms.

---

## 5. Reflected Solar Radiation at 3.9 um

### 5.1 The Daytime Problem

During daytime, the 3.9 um channel receives both:
1. **Thermal emission** from the surface: epsilon * B(3.9, T_surface)
2. **Reflected solar radiation**: rho * E_sun(3.9) * cos(theta_z) / pi

where:
- rho = 1 - epsilon (surface reflectivity, by Kirchhoff's law)
- E_sun(3.9) = solar spectral irradiance at 3.9 um (approximately 8-12 W m^-2 um^-1
  at the top of the atmosphere, depending on reference spectrum)
- theta_z = solar zenith angle
- Division by pi converts irradiance to the Lambertian-reflected radiance

The total observed radiance at 3.9 um during daytime:

```
L_3.9 = epsilon * B(3.9, T_sfc) + rho * (E_sun * cos(theta_z) * tau_atm) / pi
```

where tau_atm is the atmospheric transmittance in the 3.9 um band.

### 5.2 Magnitude of the Solar Component

For a surface with epsilon = 0.96 (rho = 0.04), at solar zenith angle 30 deg:

```
Thermal emission:   0.96 * B(3.9, 300) = 0.96 * 0.60 = 0.58 W/m^2/sr/um
Solar reflected:    0.04 * 10.0 * cos(30) / pi = 0.04 * 10.0 * 0.866 / 3.14
                    = 0.11 W/m^2/sr/um
```

The reflected solar component is roughly 15-20% of the total 3.9 um signal for
typical vegetated surfaces. For brighter surfaces (bare soil, rho ~ 0.10-0.15):

```
Solar reflected:    0.12 * 10.0 * 0.866 / 3.14 = 0.33 W/m^2/sr/um
```

This can be 30-50% of the total signal, creating substantial complications.

### 5.3 Separating Thermal and Reflected Components

**Nighttime**: No reflected solar component -- the 3.9 um signal is purely thermal.
This is why nighttime fire detection is simpler and more reliable.

**Daytime**: The standard approach to separate thermal and reflected components:

1. **Use the 11 um channel to estimate surface temperature**: Since the 11 um channel
   has negligible solar reflection (rho * E_sun contribution at 11 um is tiny), the
   11 um brightness temperature provides a good estimate of T_surface.

2. **Compute the expected thermal radiance at 3.9 um**: Using the 11 um-derived
   temperature and known 3.9 um emissivity:
   ```
   L_thermal_3.9 = epsilon(3.9) * B(3.9, T_from_11um)
   ```

3. **The residual is the reflected solar component (or fire signal)**:
   ```
   L_reflected = L_observed_3.9 - L_thermal_3.9
   ```

This is the basis of the GOES "Shortwave Albedo" product: subtract the thermal
component from the total 3.9 um signal.

### 5.4 Solar Contamination and False Alarms

Reflected solar radiation at 3.9 um can mimic a fire signal because both produce
elevated 3.9 um brightness temperatures. Common daytime false alarm sources:

- **Sun glint** from water or smooth surfaces (specular reflection spikes)
- **Bare rock/soil** with high reflectivity at 3.9 um
- **Cloud edges** with specific illumination geometry
- **Solar panels** and metal roofs (urban environments)

Operational fire algorithms handle this by:
- Requiring the 3.9 um anomaly to exceed a higher threshold during daytime than
  nighttime (typically 10-15 K daytime vs 6-10 K nighttime)
- Checking the absolute 3.9 um brightness temperature (fires > 310-315 K)
- Using the BT difference (BT_3.9 - BT_11) which enhances fire signal and reduces
  solar contamination (because solar reflection affects both bands similarly)
- Using visible-band tests to identify clouds and sun glint

### 5.5 Solar Zenith Angle Dependence

The reflected solar component scales with cos(theta_z):

| Solar zenith angle | cos(theta_z) | Relative solar contribution |
|--------------------|--------------|----------------------------|
| 0 deg (overhead)   | 1.000        | Maximum                    |
| 30 deg             | 0.866        | 87%                        |
| 45 deg             | 0.707        | 71%                        |
| 60 deg             | 0.500        | 50%                        |
| 75 deg             | 0.259        | 26%                        |
| 85 deg             | 0.087        | 9%                         |

Fire detection is most reliable when the solar zenith angle is high (early morning,
late afternoon) or after sunset, because the solar contamination is reduced.

---

## 6. Signal-to-Noise Analysis for Fire Detection

### 6.1 Framework

Given a fire of area A_fire (m^2) at temperature Tf in a pixel of area A_pixel at
background temperature Tb, the observed brightness temperature at 3.9 um is:

```
p = A_fire / A_pixel

L_obs = p * B(3.9, Tf) + (1 - p) * B(3.9, Tb)

BT_obs = B^-1(3.9, L_obs)

Delta_BT = BT_obs - Tb
```

The signal-to-noise ratio is:

```
SNR = Delta_BT / NEdT
```

Detection requires SNR >= 3 (typical threshold), though operational algorithms
use adaptive context-dependent thresholds.

### 6.2 Simplified Delta_BT Formula

For small fire fractions (p << 1), the brightness temperature increase is
approximately:

```
Delta_BT approx= p * [B(3.9, Tf) - B(3.9, Tb)] / (dB/dT)|_{3.9, Tb}
```

This linear approximation is valid for p < ~0.01 (which covers most sub-pixel fires).

### 6.3 Worked Example 1: 10 m^2 fire at 800 K in a 2 km Himawari pixel

```
Sensor: Himawari AHI Band 7
Pixel area at NSW: 3500 m x 3500 m = 12,250,000 m^2  (accounting for off-nadir viewing)
NEdT = 0.16 K

Fire area: 10 m^2
Fire temperature: 800 K
Background: 300 K

p = 10 / 12,250,000 = 8.16 x 10^-7

Delta_L = p * (B(3.9, 800) - B(3.9, 300))
        = 8.16e-7 * (1325 - 0.60)
        = 8.16e-7 * 1324
        = 1.08 x 10^-3 W/m^2/sr/um

Delta_BT = Delta_L / (dB/dT at 300K)
         = 1.08e-3 / 0.0247
         = 0.044 K

SNR = 0.044 / 0.16 = 0.27

RESULT: NOT detectable (SNR < 3). A 10 m^2 fire at 800 K is invisible to Himawari.
Need ~110 m^2 for 3-sigma detection (see Section 3).
```

### 6.4 Worked Example 2: 100 m^2 fire at 600 K in a 375 m VIIRS pixel

```
Sensor: VIIRS I4
Pixel area: 375 m x 375 m = 140,625 m^2
NEdT = 0.4 K (spec); ~0.15 K (on-orbit)

Fire area: 100 m^2
Fire temperature: 600 K
Background: 310 K

p = 100 / 140,625 = 7.11 x 10^-4

B(3.9, 600) approx= 283 W/m^2/sr/um
B(3.9, 310) approx= 0.90 W/m^2/sr/um
dB/dT at (3.9, 310) approx= 0.034 W/m^2/sr/um/K

Delta_L = 7.11e-4 * (283 - 0.90) = 7.11e-4 * 282 = 0.200 W/m^2/sr/um

Delta_BT = 0.200 / 0.034 = 5.8 K

SNR (spec) = 5.8 / 0.4 = 14.6
SNR (on-orbit) = 5.8 / 0.15 = 38.8

RESULT: Clearly detectable at both noise levels.
A 100 m^2 fire at 600 K in a 375 m pixel produces a ~5.8 K signal.
```

### 6.5 Worked Example 3: 1 m^2 fire at 1000 K in a 100 m Landsat pixel

```
Sensor: Landsat TIRS Band 10 (10.9 um -- note: no MIR band!)
Pixel area: 100 m x 100 m = 10,000 m^2
NEdT = 0.05 K

Fire area: 1 m^2
Fire temperature: 1000 K
Background: 295 K

p = 1 / 10,000 = 1.0 x 10^-4

At 10.9 um (Landsat's band):
B(10.9, 1000) approx= 282 W/m^2/sr/um
B(10.9, 295)  approx= 8.9 W/m^2/sr/um
dB/dT at (10.9, 295) approx= 0.137 W/m^2/sr/um/K

Delta_L = 1.0e-4 * (282 - 8.9) = 1.0e-4 * 273 = 0.0273 W/m^2/sr/um

Delta_BT = 0.0273 / 0.137 = 0.200 K

SNR = 0.200 / 0.05 = 4.0

RESULT: Marginally detectable (SNR ~ 4). A 1 m^2 fire at 1000 K in a 100 m
Landsat pixel produces a ~0.19 K signal at 10.9 um, just above the 3-sigma
threshold. However, in practice, background temperature uncertainty and
emissivity variation make this extremely challenging without a MIR band.
```

For comparison, if Landsat had a 3.9 um band with the same NEdT:
```
At 3.9 um:
Delta_L = 1.0e-4 * (3384 - 0.50) = 0.338 W/m^2/sr/um
Delta_BT = 0.338 / 0.023 = 14.7 K

SNR = 14.7 / 0.05 = 294

This would be trivially detectable -- illustrating why MIR capability matters.
```

### 6.6 Summary Table: Detection Scenarios

| Scenario                    | Sensor   | A_fire | Tf    | Tb   | Delta_BT | NEdT  | SNR  | Detectable? |
|-----------------------------|----------|--------|-------|------|----------|-------|------|-------------|
| Small fire, Himawari        | AHI B7   | 10 m^2 | 800 K | 300 K | 0.04 K  | 0.16  | 0.3  | No          |
| Small fire, Himawari        | AHI B7   | 100 m^2| 800 K | 300 K | 0.44 K  | 0.16  | 2.7  | Marginal    |
| Medium fire, Himawari       | AHI B7   | 500 m^2| 800 K | 300 K | 2.19 K  | 0.16  | 14   | Yes         |
| Smolder, Himawari           | AHI B7   | 500 m^2| 500 K | 300 K | 0.14 K  | 0.16  | 0.9  | No          |
| Small fire, VIIRS           | I4       | 100 m^2| 600 K | 310 K | 5.8 K   | 0.15* | 39   | Yes         |
| Tiny fire, VIIRS            | I4       | 5 m^2  | 1000 K| 300 K | 0.49 K  | 0.15* | 3.3  | Marginal    |
| Bonfire, VIIRS              | I4       | 5 m^2  | 1000 K| 300 K | ~10 K** | 0.15* | 67   | Yes         |
| 1 m^2 fire, Landsat TIR     | TIRS B10 | 1 m^2  | 1000 K| 295 K | 0.20 K  | 0.05  | 4.0  | Marginal    |

*On-orbit NEdT (specification is 0.4 K)
**Observed in the 2013 Schroeder et al. bonfire test (1.25 m radius circular bonfire,
scan angle 32.7 deg, resulting in a 10 K brightness temperature increase)

---

## 7. Fire Radiative Power (FRP) Physics

### 7.1 Stefan-Boltzmann Law

The total radiative power emitted per unit area by a surface at temperature T:

```
M = epsilon * sigma * T^4
```

where:
- sigma = 5.670 x 10^-8 W m^-2 K^-4 (Stefan-Boltzmann constant)
- epsilon = broadband emissivity (close to 1 for flames)

### 7.2 Fire Radiative Power

For a fire of area A_fire at effective temperature Tf, surrounded by background
at Tb, the fire radiative power is:

```
FRP = sigma * A_fire * (Tf^4 - Tb^4)    [W]
```

Note: The Tb^4 term is subtracted because we want the *excess* radiative power
from the fire above the background level.

**Example**: A 100 m^2 fire at 800 K (background 300 K):
```
FRP = 5.67e-8 * 100 * (800^4 - 300^4)
    = 5.67e-8 * 100 * (4.096e11 - 8.1e9)
    = 5.67e-8 * 100 * 4.015e11
    = 2.28 MW
```

### 7.3 The Wooster MIR Radiance Method

Wooster et al. (2003, 2005) showed that for typical fire temperatures (650-1350 K),
the Planck function at MIR wavelengths (~3.9 um) can be approximated by a fourth-order
power law:

```
B(lambda_MIR, T) approx= a * T^4
```

This is the same power-law dependence as Stefan-Boltzmann's law (sigma * T^4), which
means FRP can be estimated directly from the MIR radiance without needing to retrieve
Tf and p separately.

The MIR radiance method equation:

```
FRP = (A_pixel / a_MIR) * (L_MIR_fire - L_MIR_bg)    [W]
```

where:
- A_pixel = pixel area (m^2)
- L_MIR_fire = observed MIR spectral radiance of the fire pixel (W m^-2 sr^-1 um^-1)
- L_MIR_bg = MIR spectral radiance of the non-fire background (W m^-2 sr^-1 um^-1)
- a_MIR = sensor-specific coefficient relating MIR spectral radiance to total radiant
  emittance, derived from fitting the fourth-order power law to the Planck function
  at the sensor's MIR wavelength

**Sensor-specific coefficients:**

| Sensor   | MIR band (um) | a_MIR coefficient                        |
|----------|---------------|------------------------------------------|
| MODIS    | 3.96          | ~3.0 x 10^-9 W m^-2 sr um K^-4           |
| SEVIRI   | 3.9           | Similar (~2.8 x 10^-9)                    |
| VIIRS    | 3.74          | Similar (adjusted for band wavelength)    |
| AHI      | 3.9           | Similar to SEVIRI                         |

The physical basis: since both B(lambda_MIR, T) ~ a*T^4 and M_total = sigma*T^4,
the ratio sigma/a gives a constant that converts MIR spectral radiance to total
radiant emittance. This is why FRP is a simple linear function of the MIR radiance
excess.

### 7.4 Accuracy and Limitations of the MIR Method

- Accuracy: +/-12% within the temperature range 665-1365 K
- Below 665 K: The 4th-order power law underestimates B(lambda, T)
- Above 1365 K: The approximation overestimates B(lambda, T)
- The method avoids the need for TIR band measurements, which is advantageous because
  the fire signal in the TIR is small relative to background variability
- FRP is insensitive to the specific decomposition of fire temperature and area --
  the same FRP can come from a small hot fire or a large cool fire

### 7.5 Typical FRP Values

| Fire Type                   | Typical FRP per pixel | FRP per unit fire area |
|-----------------------------|----------------------|------------------------|
| Small grass fire            | 1-10 MW              | 10-50 kW/m^2           |
| Savanna fire                | 5-30 MW              | 20-80 kW/m^2           |
| Eucalyptus forest surface   | 10-100 MW            | 50-200 kW/m^2          |
| Eucalyptus crown fire       | 50-500+ MW           | 100-500+ kW/m^2        |
| Boreal crown fire           | 100-2000+ MW         | 200-1000+ kW/m^2       |
| Agricultural stubble burn   | 1-20 MW              | 10-40 kW/m^2           |

**Notes on FRP per pixel:**
- These are per-pixel FRP values as detected by moderate-resolution sensors (1-2 km)
- Multiple fire pixels in a fire produce aggregate FRP that can reach tens of GW
  for large wildfires
- MODIS has a minimum per-pixel FRP detection limit of ~5-8 MW
- Himawari AHI has a higher minimum FRP threshold (~20-40 MW) due to larger pixels

### 7.6 FRP-to-Biomass Consumption Relationship

Wooster et al. (2005) established:

```
Biomass consumption rate (kg/s) = 0.368 * FRP (MW)
```

So 1 MW of FRP corresponds to burning approximately 0.37 kg/s of biomass.
This allows estimation of emissions from satellite-observed FRP.

### 7.7 FRP from Stefan-Boltzmann (Using Dozier-Retrieved Tf and p)

If fire temperature and fraction are retrieved from the Dozier method:

```
FRP = sigma * A_pixel * p * (Tf^4 - Tb^4)
```

This is equivalent to the MIR radiance method but requires the explicit
retrieval of Tf and p, which introduces additional uncertainty. The MIR
radiance method's advantage is that it bypasses this step entirely.

---

## 8. Reference Values for NSW Australia Fire Detection

### 8.1 Typical NSW Background Temperatures (3.9 um brightness temperature)

| Season   | Time   | BT Range (K) | Notes                                    |
|----------|--------|---------------|------------------------------------------|
| Summer   | Day    | 310-340       | Hot surfaces, high solar reflected comp   |
| Summer   | Night  | 285-300       | Cooling, good detection conditions        |
| Winter   | Day    | 285-310       | Moderate, lower solar contamination       |
| Winter   | Night  | 270-285       | Cold, excellent detection conditions      |
| Spring   | Day    | 295-325       | Warming, increasing fire risk             |
| Autumn   | Day    | 295-320       | Still warm, fire season winding down      |

### 8.2 Detection Summary for NSW XPRIZE Context

For the XPRIZE competition (NSW, April 2026 -- southern hemisphere autumn):
- Background temperatures ~290-310 K daytime, ~280-295 K nighttime
- Himawari AHI provides 10-minute revisit but ~3.5 km pixels
- VIIRS provides 375 m resolution but only ~2 overpasses per day
- Landsat provides 100 m resolution but only 16-day revisit and TIR-only detection

**Minimum fire areas for reliable detection (3-sigma, 800 K fire):**

| Sensor          | Pixel size (NSW) | Min fire area | Revisit          |
|-----------------|------------------|---------------|------------------|
| Himawari AHI    | ~3.5 km          | ~110 m^2      | 10 minutes       |
| VIIRS I4        | ~500 m           | ~1-3 m^2      | ~2x daily        |
| Landsat TIRS    | 100 m (TIR only) | ~1.2 m^2      | 16 days           |
| MODIS           | ~1.3 km          | ~10-20 m^2    | ~4x daily (2 sat)|

The tradeoff is clear: geostationary sensors (Himawari) offer continuous monitoring
but need larger fires; polar-orbiting sensors (VIIRS) detect smaller fires but with
gaps in coverage.

---

## Appendix A: Physical Constants Reference

| Constant                | Symbol | Value                    | Units          |
|-------------------------|--------|--------------------------|----------------|
| Planck constant         | h      | 6.62607 x 10^-34         | J s            |
| Speed of light          | c      | 2.99792 x 10^8           | m s^-1         |
| Boltzmann constant      | k      | 1.38065 x 10^-23         | J K^-1         |
| Stefan-Boltzmann const  | sigma  | 5.67037 x 10^-8          | W m^-2 K^-4    |
| Wien displacement const | b      | 2897.8                   | um K           |
| 1st radiation const     | C1     | 1.19104 x 10^8           | W m^-2 sr^-1 um^4 |
| 2nd radiation const     | C2     | 1.43878 x 10^4           | um K           |

## Appendix B: Quick-Reference Planck Radiance Table (W m^-2 sr^-1 um^-1)

| T (K) | B(3.9 um) | B(4.0 um) | B(10.9 um) | B(11.0 um) |
|-------|-----------|-----------|------------|------------|
| 280   | 0.25      | 0.31      | 7.0        | 7.0        |
| 290   | 0.39      | 0.48      | 8.3        | 8.2        |
| 300   | 0.60      | 0.72      | 9.6        | 9.6        |
| 310   | 0.90      | 1.06      | 11.1       | 11.0       |
| 320   | 1.30      | 1.53      | 12.7       | 12.6       |
| 400   | 13.0      | 14.5      | 29.6       | 29.2       |
| 500   | 82.5      | 87.4      | 59.5       | 58.3       |
| 600   | 283       | 291       | 96.5       | 94.3       |
| 700   | 682       | 686       | 138        | 135        |
| 800   | 1325      | 1312      | 184        | 179        |
| 900   | 2227      | 2178      | 232        | 226        |
| 1000  | 3384      | 3278      | 282        | 274        |
| 1200  | 6397      | 6111      | 386        | 375        |

Note: Values computed from the Planck function B = C1/(lam^5 * (exp(C2/(lam*T))-1))
with C1 = 1.19104e8 W/m^2/sr/um^4 and C2 = 1.43878e4 um*K.

## Appendix C: Key References

1. Dozier, J. (1981). "A method for satellite identification of surface temperature
   fields of subpixel resolution." Remote Sensing of Environment, 11, 221-229.

2. Wooster, M.J., Zhukov, B., & Oertel, D. (2003). "Fire radiative energy for
   quantitative study of biomass burning." Remote Sensing of Environment, 86, 83-107.

3. Wooster, M.J., Roberts, G., Perry, G.L.W., & Kaufman, Y.J. (2005). "Retrieval of
   biomass combustion rates and totals from fire radiative power observations." Journal
   of Geophysical Research, 110, D24311.

4. Giglio, L. & Kendall, J.D. (2001). "Application of the Dozier retrieval to wildfire
   characterization: a sensitivity analysis." Remote Sensing of Environment, 77, 34-49.

5. Schroeder, W., Oliva, P., Giglio, L., & Csiszar, I. (2014). "The New VIIRS 375 m
   active fire detection data product." Remote Sensing of Environment, 143, 85-96.

6. Kaufman, Y.J., Justice, C.O., Flynn, L.P., et al. (1998). "Potential global fire
   monitoring from EOS-MODIS." Journal of Geophysical Research, 103, 32215-32238.
