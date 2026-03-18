# Satellite Remote Sensing for Wildfire Detection

## Scope and Relevance to XPRIZE (NSW, Australia -- April 2026)

This domain brief covers the satellite sensors, physics, and data access pathways relevant to building a wildfire detection system using public satellite data. The competition finals are in **New South Wales, Australia** in **April 2026**, which dictates:

- **Himawari-9 AHI is the primary geostationary sensor** (GOES covers the Americas only and has no view of Australia)
- **April is late autumn** in Australia -- fire season in NSW typically peaks in summer (Dec--Feb) but can extend through April in drought years. Cloud cover is moderate; lower humidity and declining rainfall since mid-1990s increase fire risk
- **Latitude ~28--37 S** affects LEO overpass frequency, Himawari view geometry, and Sentinel-2/Landsat revisit patterns

## Key Concepts

### Electromagnetic Spectrum and Atmospheric Windows

Fire detection exploits two atmospheric windows:

| Window | Wavelength | Primary Use | Key Physics |
|--------|-----------|-------------|-------------|
| **MWIR** (Mid-Wave IR) | 3.5--4.1 um | Active fire detection | Peak emission for fire temperatures (600--1200 K) per Wien's law. Radiance increases ~8th power of temperature at 3.9 um, giving extreme sensitivity to hot sub-pixel targets |
| **TIR** (Thermal IR) | 10.0--12.5 um | Background temperature, cloud masking | Peak emission for Earth surface temperatures (~300 K). Radiance increases ~5th power of temperature at 11 um |
| **SWIR** (Short-Wave IR) | 1.6--2.2 um | Fire detection (daytime), burn scars | Sensitive to very high-temperature fires (>700 K) but mixed with reflected solar radiance during day |

The MWIR-TIR brightness temperature difference (BT_3.9 - BT_11) is the fundamental fire detection signal. A sub-pixel fire raises BT_3.9 far more than BT_11 because of the nonlinear Planck function.

### Pixel Size vs Fire Size

The competition targets fires as small as ~10 m^2. Sensor pixel sizes range from 0.5 km to 4+ km:

| Sensor | Nadir Pixel (fire bands) | Pixel Area | Ratio to 10 m^2 target |
|--------|-------------------------|-----------|------------------------|
| Himawari AHI B7 | 2 km | 4,000,000 m^2 | 400,000x |
| VIIRS I4 | 375 m | 140,625 m^2 | 14,063x |
| MODIS B21/22 | 1 km | 1,000,000 m^2 | 100,000x |
| Landsat OLI B7 | 30 m | 900 m^2 | 90x |
| Sentinel-2 B12 | 20 m | 400 m^2 | 40x |

Sub-pixel detection is possible when fire radiance contribution exceeds the sensor's noise floor and background variability. A 10 m^2 fire at 800 K occupying 0.0000025 of a 2 km AHI pixel is generally **not detectable** by geostationary sensors. The same fire in a 375 m VIIRS pixel (fraction ~0.00007) is marginal. In a 30 m Landsat pixel (fraction ~0.011) it is **readily detectable**.

### Minimum Detectable Fire Size (Order of Magnitude)

| Sensor | Best-Case Minimum Detectable Fire | Conditions |
|--------|----------------------------------|-----------|
| Himawari AHI (2 km) | ~4,000 m^2 (0.004 km^2) | Nadir, nighttime, uniform background |
| GOES ABI (2 km) | ~4,000 m^2 | Nadir, nighttime |
| Meteosat SEVIRI (3 km) | ~900 m^2 | Nadir |
| MODIS (1 km) | ~1,000 m^2 | Typical conditions |
| VIIRS I-band (375 m) | ~100--500 m^2 | Low FRP fires detectable |
| Landsat OLI (30 m) | ~4 m^2 | Daytime, reflective-band algorithm |

## Sensor Inventory

### Geostationary Sensors

#### Himawari-9 AHI (PRIMARY for NSW)

- **Operator:** Japan Meteorological Agency (JMA)
- **Position:** Geostationary at **140.7 E longitude**, equatorial
- **Coverage:** Full disk covering East Asia, Australia, and West/Central Pacific
- **Scan cadence:**
  - Full disk: **10 minutes** (144/day)
  - Japan Area: **2.5 minutes** (576/day)
  - Target Area (1000x1000 km, repositionable): **2.5 minutes** (576/day)
  - Landmark regions 4 & 5: **0.5 minutes** (2880/day each)

**AHI 16-Band Specifications:**

| Band | Central Wavelength | Bandwidth | Resolution | Primary Purpose |
|------|-------------------|-----------|-----------|-----------------|
| 1 | 0.47 um | 0.05 um | 1.0 km | Aerosol over land, coastal water |
| 2 | 0.51 um | 0.02 um | 1.0 km | Green (color composite) |
| 3 | 0.64 um | 0.03 um | **0.5 km** | Vegetation, burn scar, aerosol |
| 4 | 0.86 um | 0.02 um | 1.0 km | Cirrus cloud |
| 5 | 1.61 um | 0.02 um | 2.0 km | Cloud-top phase, snow |
| 6 | 2.26 um | 0.02 um | 2.0 km | Cloud/land properties, vegetation |
| **7** | **3.90 um** | **0.22 um** | **2.0 km** | **Surface, fog, FIRE, winds** |
| 8 | 6.19 um | 0.37 um | 2.0 km | Upper-level water vapor |
| 9 | 6.95 um | 0.12 um | 2.0 km | Mid-level water vapor |
| 10 | 7.40 um | 0.17 um | 2.0 km | Lower-level water vapor, SO2 |
| 11 | 8.50 um | 0.32 um | 2.0 km | Cloud phase, dust, SO2 |
| 12 | 9.61 um | 0.18 um | 2.0 km | Total ozone |
| 13 | 10.35 um | 0.30 um | 2.0 km | Surface and cloud |
| **14** | **11.20 um** | **0.20 um** | **2.0 km** | **SST, clouds, rainfall** |
| **15** | **12.30 um** | **0.30 um** | **2.0 km** | **Total water, ash, SST** |
| 16 | 13.30 um | 0.20 um | 2.0 km | Air temperature, cloud heights |

**Fire-relevant bands:** B7 (3.9 um MWIR) is the primary fire channel. B14 (11.2 um) and B15 (12.3 um) provide background temperature and split-window cloud/ash discrimination.

**Comparison to GOES ABI:** AHI and ABI are near-identical instruments (both built by Harris/L3Harris). Same 16 bands, same spatial resolutions, same scan cadence. Key difference: ABI has CONUS/PACUS rapid scan (5 min) and mesoscale sectors (30--60 sec for 1000x1000 km boxes) that AHI does not offer for Australia. AHI's Japan Area rapid scan (2.5 min) covers only Japan. The Target Area can be repositioned but is primarily used for typhoons/volcanoes, not routine fire monitoring.

#### Other Geostationary (not primary but potentially supplementary)

- **GK2A (GEO-KOMPSAT-2A):** Korean satellite at 128.2 E, AMI instrument, covers Australia. 10-min full disk. Could provide supplementary views.
- **GOES-West (GOES-18/19):** 137.2 W -- **does not cover Australia**. Irrelevant for NSW.
- **Meteosat (MSG/SEVIRI, MTG/FCI):** IODC position at 57.5 E could have marginal view of western Australia but very poor geometry for NSW.

### Polar-Orbiting Sensors (LEO)

#### VIIRS (S-NPP, NOAA-20, NOAA-21)

- **Orbit:** Sun-synchronous, ~834 km altitude
- **Equator crossing:** ~13:30 local solar time (ascending, daytime), ~01:30 (descending, nighttime)
- **NOAA-20 offset:** ~50 minutes ahead of S-NPP
- **Swath width:** 3,040 km (no gaps between consecutive orbits at equator)
- **Global coverage:** Full globe every ~12 hours per satellite
- **Overpasses at ~33 S (Sydney):** ~3--4 per satellite per day = **~9--12 total overpasses/day** with 3 satellites (S-NPP, NOAA-20, NOAA-21), including both day and night passes

**I-Band Fire Detection Channels:**

| Band | Wavelength | Resolution | Saturation BT | Role |
|------|-----------|-----------|--------------|------|
| I4 | 3.55--3.93 um (center 3.74 um) | 375 m | **367 K** | Primary fire detection driver |
| I5 | 10.50--12.40 um (center 11.45 um) | 375 m | 340 K | Background temperature |

**M-Band for Fire Characterization:**

| Band | Wavelength | Resolution | Saturation BT | Role |
|------|-----------|-----------|--------------|------|
| M13 | 3.97--4.13 um (center 4.05 um) | 750 m | **343 K (high gain) / 634--659 K (low gain)** | FRP retrieval, dual-gain for hot targets |

M13 is a **dual-gain** band: dynamically switches between high gain (sensitive, saturates at 343 K) and low gain (less sensitive, saturates at ~634--659 K) depending on pixel radiance. This allows fire radiative power (FRP) retrieval for fires that would saturate I4.

**Detection algorithm:** Contextual thermal anomaly using I4 and I5 brightness temperatures. Pixel flagged as fire if BT_I4 and (BT_I4 - BT_I5) exceed background statistics by sensor-specific thresholds. Confidence levels:
- **Low:** Daytime pixels with sun glint or BT anomaly < 15 K
- **Nominal:** BT anomaly > 15 K, no sun glint
- **High:** Saturated pixels (day or night)

#### MODIS (Terra, Aqua)

- **Orbit:** Sun-synchronous, ~705 km altitude (drifting for Terra)
- **Terra equator crossing:** Nominally 10:30 AM descending, but **drifting to ~9:00 AM by Dec 2025** and ~8:30 AM by late 2026 due to stopped inclination maneuvers. Altitude dropping from 715 km to ~702 km.
- **Aqua equator crossing:** ~13:30 PM ascending (stable)
- **Swath width:** 2,330 km
- **Status (April 2026):** Terra MODIS expected to be in final operational phase; data quality degrading due to orbit drift. Aqua MODIS more stable. **MODIS is transitioning to VIIRS** -- treat as supplementary, not primary.

**Fire detection bands:**

| Band | Wavelength | Resolution | Saturation BT | Role |
|------|-----------|-----------|--------------|------|
| 21 | 3.929--3.989 um | 1 km | **500 K** | Fire detection (primary) |
| 22 | 3.929--3.989 um | 1 km | ~331 K | Fire detection (low-gain complement) |
| 31 | 10.780--11.280 um | 1 km | ~400 K | Background temperature |

Band 21 and 22 cover the same spectral range but with different gains. Band 22 saturates at lower temperatures and is used for non-fire pixels; Band 21 has higher saturation for fire characterization.

#### Landsat 8 / Landsat 9

- **Orbit:** Sun-synchronous, 705 km altitude, ~10:00 AM descending node
- **Swath width:** 185 km
- **Revisit:** 16-day repeat per satellite; **8-day combined** with both satellites
- **WRS-2 coverage of NSW:** Multiple paths; any given point in NSW gets an overpass every 8 days

**Fire-relevant instruments:**

| Instrument | Band | Wavelength | Resolution | Use |
|-----------|------|-----------|-----------|-----|
| OLI | B6 (SWIR1) | 1.57--1.65 um | 30 m | Fire/burn detection |
| OLI | **B7 (SWIR2)** | **2.11--2.29 um** | **30 m** | **Primary fire detection** |
| TIRS | B10 | 10.6--11.2 um | 100 m (resampled to 30 m) | Thermal reference |
| TIRS | B11 | 11.5--12.5 um | 100 m | Split-window correction |

**Active fire algorithm:** Uses OLI reflective SWIR bands (B6, B7), not TIRS thermal bands. Exploits the strong increase in 2.2 um reflectance from fire emissions relative to the 0.66 um band. Can detect fires as small as **~4 m^2** during daytime. This is the only public satellite source capable of meter-scale fire detection.

**Limitation:** 8-day revisit means Landsat is opportunistic -- cannot provide continuous monitoring.

#### Sentinel-2 MSI (A/B/C)

- **Orbit:** Sun-synchronous, 786 km altitude, ~10:30 AM descending node
- **Swath width:** 290 km
- **Revisit at NSW (~33 S):** **2--3 days** with two satellites (Sentinel-2B + 2C). Sentinel-2A extension campaign in 2025 may add further coverage.
- **Current constellation (2025+):** Sentinel-2C replaced Sentinel-2A as the primary on 2025-01-21. Sentinel-2A is in an extension campaign.

**Fire-relevant bands:**

| Band | Wavelength | Resolution | Use |
|------|-----------|-----------|-----|
| B4 | 0.665 um | 10 m | Red -- fire ratio denominator |
| B8A | 0.865 um | 20 m | NIR vegetation reference |
| **B11** | **1.610 um** | **20 m** | **SWIR1 -- fire/burn detection** |
| **B12** | **2.190 um** | **20 m** | **SWIR2 -- fire/burn detection** |

**Critical limitation:** Sentinel-2 has **no thermal infrared band**. Fire detection relies on SWIR bands, where emitted fire radiance is mixed with reflected solar radiation during daytime. This makes detection less reliable than thermal-based sensors and limits it to:
- Large or high-temperature fires that produce sufficient SWIR emission
- Burn scar mapping (NBR = (B8 - B12) / (B8 + B12))
- Smoke plume identification (RGB + SWIR composites)

**Use case for XPRIZE:** Confirmation and perimeter refinement when an overpass coincides with a detected event. Not a standalone early-warning sensor.

## Sensor Comparison Summary

| Property | Himawari AHI | VIIRS | MODIS | Landsat 8/9 | Sentinel-2 |
|----------|-------------|-------|-------|-------------|-----------|
| Orbit | GEO (140.7 E) | LEO sun-sync | LEO sun-sync | LEO sun-sync | LEO sun-sync |
| Fire band resolution | 2 km | 375 m | 1 km | 30 m | 20 m |
| Temporal cadence | 10 min FD | ~4--6 passes/day (combined 3 sats) | ~4 passes/day (2 sats) | 8 days | 2--3 days |
| Min detectable fire | ~4000 m^2 | ~100--500 m^2 | ~1000 m^2 | ~4 m^2 | Limited (no thermal) |
| Thermal band? | Yes (3.9, 11.2 um) | Yes (3.74, 11.45 um) | Yes (3.96, 11.03 um) | Yes (10.9 um, 100 m) | **No** |
| Role in system | Continuous monitor | Primary LEO fire detection | Supplementary | Small-fire opportunistic | Confirmation/burn scar |
| Data latency | ~16--17 min (HimawariCast) | ~30 min RT, ~3 h NRT | ~3 h NRT | 4--6 h L1 RT | 100 min -- 24 h |
