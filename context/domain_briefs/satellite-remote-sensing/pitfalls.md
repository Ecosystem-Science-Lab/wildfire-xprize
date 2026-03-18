# Pitfalls and Gotchas for Satellite Fire Detection in NSW Australia

## 1. Himawari View Geometry for Australia

### The Problem

Himawari-9 sits at 140.7 E on the equator. NSW (28--37 S, 148--154 E) is substantially south and slightly east of the subsatellite point. This means:

| Location | View Zenith Angle | Effective Pixel Size (B7) | Pixel Area Multiplier |
|----------|------------------|--------------------------|----------------------|
| Sydney (33.9 S, 151.2 E) | ~37 deg | ~3.6 km | ~1.8x nadir |
| Canberra (35.3 S, 149.1 E) | ~38 deg | ~3.8 km | ~1.9x nadir |
| Melbourne (37.8 S, 145.0 E) | ~40 deg | ~4.0 km | ~2.0x nadir |
| Hobart (42.9 S, 147.3 E) | ~45 deg | ~4.8 km | ~2.4x nadir |

### Consequences

- **Minimum detectable fire size increases proportionally** with pixel area. At Sydney, the theoretical minimum detectable fire is ~7,000 m^2 instead of ~4,000 m^2 at nadir
- **Geolocation error increases** with VZA. Parallax from smoke plumes and elevated terrain displaces the apparent fire position. For a 2 km smoke plume above ground at VZA = 37 deg, the parallax displacement is ~1.5 km
- **Atmospheric path length increases** by factor 1/cos(VZA) ~ 1.25x at Sydney, increasing absorption and reducing signal-to-noise
- **Pixel is not square** -- stretched more in the N-S direction than E-W due to foreshortening

### Mitigation

- Accept degraded geostationary sensitivity for NSW; design the system to rely more heavily on VIIRS for fire confirmation
- Use the sensor zenith angle grid (available from NCI Himawari products) to scale detection thresholds by VZA
- Apply parallax correction using terrain elevation data (e.g., SRTM DEM)
- Do NOT use nadir-calibrated detection thresholds at Australian latitudes without VZA adjustment

## 2. Sun Glint Contamination (3.9 um)

### The Problem

The 3.9 um MWIR band receives **both thermal emission and reflected solar radiation** during daytime. Specular reflection of sunlight from water surfaces, wet soil, or shiny rooftops produces a "sun glint" signal that mimics fire:

- Water has an anomalously high refractive index at 3.9 um, causing **much stronger** sun glint at 3.9 um than at visible wavelengths
- The glint area in 3.9 um imagery is much larger than in visible images
- At low solar angles (morning/evening), the sensor can saturate on glint alone

### When It Happens

- Daytime only (no sun glint at night)
- Geometry-dependent: glint occurs when the specular reflection angle is near zero (sun angle mirrors sensor angle)
- For Himawari viewing NSW at VZA ~37 deg, sun glint is most problematic over water bodies and coastal areas when the solar geometry aligns
- **April in NSW:** Solar elevation is moderate (autumn). Sun glint is possible but less severe than summer. Watch for morning scans when solar and sensor angles may align over coastal waters

### False Alarm Signature

- High BT_3.9 but BT_11.2 is near-normal background temperature
- BT_3.9 - BT_11.2 can be 10--30 K over sun glint -- overlapping with fire detection thresholds
- Typically over water or wet surfaces, not vegetation

### Mitigation

- **Compute sun glint angle** for every pixel using solar and sensor geometry. Flag pixels where specular angle < 20--25 deg
- **Use land/water mask**: reject fire candidates over water bodies (rivers, lakes, coastal pixels)
- **Check TIR consistency**: genuine fires raise both BT_3.9 and BT_11.2 (though BT_3.9 rises much more). Pure sun glint raises BT_3.9 only, leaving BT_11.2 at ambient background
- **Night-only processing** for highest reliability: eliminates sun glint entirely but misses daytime fires
- VIIRS fire algorithm assigns **low confidence** to fire pixels in sun glint zones. Follow this approach

## 3. Diurnal Cycle Effects on Thermal Detection

### The Problem

Daytime thermal detection is fundamentally harder than nighttime:

1. **Reflected solar at 3.9 um** adds a non-fire signal that varies with surface albedo, solar angle, and atmospheric state. Must be estimated and subtracted.
2. **Background temperature is higher** during day (surface heated by sun). A 310 K background reduces the fire-vs-background contrast compared to 280 K nighttime background.
3. **Background spatial variability is greater** during day: different land cover types heat differently, creating heterogeneous backgrounds that increase the noise floor for contextual detection.

### Quantitative Impact

- Night: BT_3.9 background ~280--290 K. A 500 K fire covering 0.05% of a 2 km pixel raises BT_3.9 by ~3 K. Detectable.
- Day: BT_3.9 background ~310--320 K (including solar reflection). The same fire raises BT_3.9 by only ~1.5 K against a noisier background. Marginally detectable.

### April in NSW

- Day length ~11 hours (approx 06:00 to 17:00 local)
- **Nighttime detection window: ~17:00 to 06:00 (13 hours)** -- longer than daytime, which is favorable
- Autumn conditions: lower daytime surface temperatures than summer, slightly improving daytime detection contrast
- VIIRS nighttime passes (~01:30 local) are the highest-sensitivity LEO observations

### Mitigation

- Use **separate day/night detection thresholds** (higher for day)
- For AHI, estimate the reflected solar component using visible band data (B3 at 0.64 um or B6 at 2.26 um) and subtract from B7
- The **pyspectral** library can compute estimated solar reflection contribution to 3.9 um
- Prioritize nighttime detections for initial alerts; use daytime data for monitoring growth of known fires
- For VIIRS, the algorithm already applies different thresholds for day and night

## 4. Cloud Contamination

### The Problem

Clouds block the view of the surface in all thermal and SWIR bands. Undetected thin clouds or cloud edges can:
- Obscure real fires (missed detections)
- Create brightness temperature gradients that mimic fires (false detections, especially at cloud edges where cold cloud meets warm surface)
- Bias background temperature statistics used in contextual detection

### NSW April Cloud Conditions

- April is **early autumn** in NSW. Generally:
  - **Eastern seaboard (Sydney, coastal):** moderate cloud cover from onshore easterly winds, occasional East Coast Lows
  - **Western NSW (inland):** generally clearer, lower cloud fraction
  - **Alpine areas (Snowy Mountains):** variable cloud cover
- Overall cloud fraction in NSW April: typically 40--60%, lower than winter (June--August) but variable
- Persistent low stratus is less common than in winter
- Afternoon convective clouds (cumulus) are possible on warm days, particularly over elevated terrain

### Specific Cloud-Fire Confusion Issues

1. **Cloud edge contamination:** When a fire pixel is at the boundary of a cloud, the contextual background may include cold cloud pixels, artificially inflating the anomaly. Conversely, a cloud edge can have a warm bright limb in 3.9 um that triggers false detection.
2. **Thin cirrus:** Allows some surface thermal signal through but attenuates it, potentially causing a fire to be missed. Also can scatter solar radiation into the 3.9 um band.
3. **Smoke vs cloud:** Dense smoke plumes can be misclassified as cloud, causing the fire beneath to be masked out. Smoke is semi-transparent in TIR but absorbing in visible bands.
4. **Newly cleared cloud:** When a pixel transitions from cloud-covered to clear, the first clear observation may have biased background statistics (no recent clear history), potentially increasing false alarm rate.

### Mitigation

- Use a robust cloud mask (AHI B14/B15 split window; VIIRS cloud mask in the active fire product)
- Reject fire candidates within N pixels of a cloud edge
- Maintain temporal history of clear-sky background temperatures per pixel to handle cloud transitions
- For VIIRS, the cloud mask is integrated into the fire algorithm; for AHI custom processing, you need to implement cloud screening yourself

## 5. Sensor Degradation and Cross-Calibration

### Terra MODIS Orbit Drift

**This is the most acute sensor degradation issue for the April 2026 timeframe:**

- Terra stopped inclination-adjust maneuvers in 2020. Its orbit is drifting.
- By late 2026, Terra's equator crossing will have drifted from the nominal 10:30 AM to approximately **8:30 AM**
- Altitude dropping from 715 km to ~702 km, changing the swath width and pixel geometry
- **Impact:** Terra MODIS fire products in April 2026 will observe at lower solar elevation angles, with different illumination geometry. This degrades daytime fire detection and changes the background temperature statistics compared to historical baselines.
- **Recommendation:** Treat Terra MODIS as **unreliable** for operational fire detection by April 2026. Aqua MODIS (13:30 PM, stable orbit) remains usable but is secondary to VIIRS.
- NASA is actively transitioning from MODIS to VIIRS. By April 2026, Terra may have ceased operations entirely.

### VIIRS Cross-Satellite Calibration

- S-NPP, NOAA-20, and NOAA-21 carry nominally identical VIIRS instruments, but:
  - Small calibration offsets exist between instruments (typically < 0.5 K for thermal bands)
  - Different instruments may be at different stages of detector degradation
  - S-NPP is oldest (launched 2011) and may show more noise/drift
- **Impact:** Fire detection thresholds tuned on one satellite's data may produce slightly different false alarm rates on another
- **Mitigation:** Use per-satellite bias corrections; monitor false alarm rates separately per satellite

### Himawari-8 to Himawari-9 Transition

- Himawari-9 took over operations at 140.7 E on December 13, 2022, replacing Himawari-8
- The instruments are nearly identical, but small calibration differences exist
- Band 7 (3.9 um) stray light characterization differs between H8 and H9 -- a known issue documented by NOAA
- **Impact:** If using historical Himawari-8 data for training/baseline building, verify that calibration offsets are accounted for when applying to Himawari-9 operational data

### Sentinel-2A to 2C Transition

- Sentinel-2C replaced Sentinel-2A as the primary operational satellite on 2025-01-21
- Spectral response functions differ slightly between MSI instruments
- **Impact:** SWIR band ratios for fire detection may need recalibration. Use Harmonized Landsat Sentinel (HLS) products where possible for consistency.

## 6. False Alarm Sources Specific to NSW

### Hot Industrial Sites

- Steel works, power plants, cement kilns, and gas flares produce persistent thermal anomalies
- Port Kembla steelworks (near Wollongong), industrial areas in Hunter Valley
- **Mitigation:** Maintain a static "hot spot" mask of known industrial thermal sources; reject fire candidates at these locations unless the anomaly significantly exceeds the persistent baseline

### Bare Soil and Rock Heating

- Western NSW (semi-arid) has exposed rock and bare soil that heats rapidly in daytime
- BT_3.9 can reach 310--320 K over dark bare surfaces in summer/autumn
- **Mitigation:** Land cover mask; require persistence (2+ consecutive frames for AHI) before alerting

### Agricultural Burning

- Crop residue burning is common in rural NSW (particularly Hunter Valley, Riverina)
- These are real fires but may not be the target for wildfire detection
- **Mitigation:** Cross-reference with agricultural burning permits (if available); flag but do not suppress -- the competition may count these

### Urban Heat Island

- Sydney metro area has elevated surface temperatures
- Not a fire but can create moderate BT anomalies
- **Mitigation:** Urban mask; raise BT thresholds over urban areas

## 7. Data Latency Pitfalls

### FIRMS NRT is Not Real-Time for Australia

The FIRMS "near real-time" label is misleading for latency-critical applications:
- Global NRT data has latency of **up to 3 hours** (best effort)
- URT (< 5 min) and RT (< 30 min) are **only available for US/Canada**, not Australia
- Do NOT design the system assuming sub-hour fire point data from FIRMS for NSW

### Himawari AWS NODD Latency is Not the Same as GOES NODD

- GOES NODD end-to-end transfer latency is documented at ~24 seconds once product is generated
- Himawari NODD latency is less well documented but appears similar in magnitude
- HimawariCast (broadcast) latency is ~16--17 min from observation start
- The AWS mirror should be faster than HimawariCast but slower than GOES NODD due to longer processing chain (JMA --> NOAA --> AWS vs NOAA --> AWS for GOES)

### Sentinel-2 "Real-Time" Does Not Mean Minutes

- Sentinel-2 "Real-Time" timeliness class is defined as <= 100 minutes from observation
- "NRT" is 100 min to 3 hours
- "Nominal" is 3--24 hours
- These are data availability times, not fire detection times. You still need to download, process, and analyze the data.

## 8. Coordinate System and Projection Pitfalls

### Himawari Sweep Axis

- Himawari AHI uses **sweep="y"** (Y-axis) in the geostationary projection
- GOES ABI uses **sweep="x"** (X-axis)
- Using the wrong sweep axis in pyproj/pyresample will produce **systematically wrong geolocation** by up to several kilometers
- This is one of the most common bugs when adapting GOES-based code for Himawari

### VIIRS Bow-Tie Deletion

- VIIRS implements on-board bow-tie deletion to limit pixel overlap at swath edges
- Some rows near swath edges have deleted pixels (fill values)
- Fire detection algorithms must handle these fill values; do not treat them as cold (non-fire) pixels

### Sentinel-2 Tile Boundaries

- Sentinel-2 data is delivered in 100x100 km MGRS tiles (UTM projection)
- Fire events near tile boundaries appear in multiple tiles
- Must implement tile-edge deduplication
- Different tiles may have different UTM zones (NSW spans UTM zones 55 and 56)

## 9. Atmospheric Effects

### Water Vapor Absorption at 3.9 um

- The 3.9 um window is not perfectly transparent. Water vapor absorbs weakly in this region.
- High humidity conditions (common in coastal NSW) increase absorption, reducing fire signal-to-noise
- **Mitigation:** Use atmospheric water vapor products (AHI bands 8--10) or NWP model fields to estimate and correct for absorption

### Aerosol Scattering

- Smoke aerosols from the fire itself (or from nearby fires) scatter and absorb radiation
- In the 3.9 um band, aerosol effects are generally small
- In SWIR bands (1.6, 2.2 um), smoke scattering is significant and can obscure Sentinel-2/Landsat fire signals
- Dense smoke plumes can completely obscure the fire in visible and SWIR imagery while remaining partially transparent in TIR

## 10. Competition-Specific Pitfalls

### Time Zone Awareness

- NSW is in AEDT (UTC+11) during daylight saving or AEST (UTC+10) in standard time
- April 2026: Daylight saving ends first Sunday in April (April 5, 2026), transitioning from AEDT to AEST
- All satellite data uses UTC timestamps
- Ensure the detection system correctly handles the UTC-to-local conversion, especially for day/night threshold selection and for reporting detection times in competition format

### Competition Area Uncertainty

- The exact test area within NSW may not be known until close to the event
- Different regions of NSW have very different characteristics:
  - Coastal eucalyptus forest: dense canopy, high moisture, moderate cloud risk
  - Western grassland/savanna: open, dry, low cloud risk but hot bare soil false alarms
  - Alpine areas: variable terrain, weather-dependent cloud
- Build the system to be adaptable to any NSW sub-region; avoid hard-coding thresholds for a specific landscape

### Satellite Outages and Maintenance

- Himawari-9 undergoes planned maintenance (eclipse season around equinoxes, ~March/September; stationkeeping maneuvers)
- April is shortly after the March equinox -- verify Himawari-9 eclipse season schedule and plan for brief outages
- VIIRS satellites also have occasional anomalies or safe-mode events
- The system must handle graceful degradation when any single sensor is temporarily unavailable
