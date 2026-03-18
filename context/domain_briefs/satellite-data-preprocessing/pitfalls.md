# Pitfalls: Calibration Drift, Cloud/Fire Confusion, Bowtie Artifacts, and Processing Order

## 1. Calibration Pitfalls

### 1.1 VIIRS Calibration Drift

**Solar Diffuser (SD) degradation:** The VIIRS Solar Diffuser degrades from UV exposure over the mission lifetime. The H-factor (degradation rate) is monitored by the Solar Diffuser Stability Monitor (SDSM), but imprecise characterization of this degradation leads to drifts in calibrated radiances.

**SD vs. lunar F-factor divergence:** For S-NPP and NOAA-20 VIIRS, systematic differences exist between the SD-based calibration and independent lunar calibration results. The lunar F-factor can deviate from the solar F-factor by ~1% in short-wavelength bands. This matters less for thermal bands (I4, I5) used in fire detection than for reflective solar bands.

**For fire detection:** Thermal emissive band calibration is more stable than reflective bands because it uses the onboard blackbody (BB) reference at a known temperature (~292.5K). The F-factor for thermal bands is generally stable to within 0.1-0.3%. This is well below the noise floor of fire detection thresholds.

**Practical implication:** If you're using L1b/SDR products, calibration drift is already handled by the operational pipeline. If you're processing raw data from a direct-broadcast station, make sure you're using current calibration coefficients (updated quarterly for VIIRS).

### 1.2 Saturation of MIR Bands

**I4 saturation at ~367K:** Any fire pixel with brightness temperature above ~367K will saturate the VIIRS I4 detector. The pixel value will be clipped, and the true fire temperature cannot be retrieved from I4 alone.

**How to detect saturation:** When I4 saturates, the T_I5 value will appear higher than T_I4 (normally, fire pixels have T_I4 >> T_I5). If T_I5 > T_I4, the pixel is likely I4-saturated.

**M13 dual gain as backup:** The VIIRS M13 band (4.05um, 750m) has a high-gain mode for typical scenes and a low-gain mode that saturates at ~634K. Use M13 for Fire Radiative Power (FRP) retrieval of intense fires where I4 saturates.

**AHI/ABI saturation:** Geostationary sensor MIR bands have similar saturation issues at lower temperatures (~400K for AHI B07) due to their coarser radiometric quantization.

### 1.3 Inconsistent Calibration Between Sensors

If comparing fire detections across sensors (e.g., VIIRS and AHI), be aware that:
- Different spectral response functions mean "3.9um brightness temperature" is slightly different for each sensor
- Cross-calibration using GSICS (Global Space-based Inter-Calibration System) coefficients can reduce inter-sensor biases
- Satpy supports GSICS coefficients for AHI: `reader_kwargs={'calib_mode': 'gsics'}`

### 1.4 Landsat Stray Light

Landsat 8 TIRS Band 11 (12um) has a known stray light issue causing scene-dependent radiometric errors of up to 10K. **Use Band 10 only for quantitative brightness temperature analysis.** Band 11 is not recommended for single-band thermal retrievals.

---

## 2. Cloud/Fire Confusion

### 2.1 Cloud Edges as False Fire Sources

This is the single largest source of false alarms in satellite fire detection.

**Mechanism:** Cloud edges create steep spatial gradients in MIR brightness temperature. The contextual fire detection algorithm compares a pixel to its neighbors. If a pixel is at a cloud edge where one side is clear (warm) and the other is cloudy (cold), the background statistics are distorted:
- The background mean is pulled down by cloud-contaminated pixels
- The candidate pixel (partially clear, warm) appears anomalously hot relative to the distorted background
- Result: false fire detection

**Mitigation strategies:**
1. **Buffer cloud mask:** Dilate the cloud mask by 1-2 pixels to exclude cloud-edge pixels from fire detection entirely.
2. **Require minimum background count:** The VIIRS algorithm requires at least 10 valid (non-cloud, non-water) background pixels. If the cloud fraction is too high, skip fire detection for that pixel.
3. **Temporal consistency:** A real fire persists across consecutive observations. A cloud-edge false alarm typically shifts location as the cloud moves. Require detection in 2+ consecutive scans (for geostationary sensors with 10-min cadence).

### 2.2 Fire Beneath/Near Clouds

- Optically thick clouds completely block the fire signal. Nothing can be done except wait for cloud clearance.
- Optically thin cirrus reduces the apparent MIR brightness temperature of the fire pixel, potentially pushing it below detection thresholds. The 1.38um cirrus test can flag these pixels, but the fire may still be missed.
- Smoke from fires can be misclassified as cloud by automated cloud masks, causing the fire pixel itself to be masked out. This is especially problematic for large fires producing thick smoke plumes.

### 2.3 Smoke Confusing Atmospheric Correction

For Sentinel-2 L2A processing: the Sen2Cor atmospheric correction algorithm can misclassify dense smoke as cloud or aerosol, producing incorrect surface reflectance values near active fires. **Use L1C (TOA) data for fire detection with Sentinel-2**, not L2A.

### 2.4 Sun Glint False Alarms

**Mechanism:** Specular reflection of sunlight off water surfaces, metallic roofs, or solar panels produces high MIR radiance that can mimic a fire signal.

**Rejection approach:**
- Apply land/water mask first (removes water glint)
- Compute sun glint angle; flag pixels within the glint cone
- In the VIIRS algorithm, sun glint rejection uses: if the pixel is over water AND within the glint geometry, reject as non-fire
- Persistent industrial heat sources (refineries, power plants): maintain a static "known hot spot" database and flag detections at those locations separately

### 2.5 Desert/Bare Soil False Alarms

Hot deserts in afternoon can produce MIR brightness temperatures of 320-330K, approaching daytime fire thresholds. The contextual algorithm handles this because the entire desert region is uniformly warm, so no single pixel stands out. Problems arise when:
- There are land cover transitions (e.g., irrigated agriculture adjacent to desert)
- Cloud shadows cool part of the scene, making adjacent sunlit areas appear anomalously warm by comparison

---

## 3. VIIRS Bowtie Artifacts

### 3.1 What the Bowtie Effect Is

VIIRS scans across-track with a whiskbroom scanner. At the edges of the swath, pixels become elongated and adjacent scan lines overlap. This is the "bowtie effect," similar to MODIS.

Unlike MODIS, VIIRS applies **onboard bowtie deletion**: the overlapping rows at the edges of each scan are replaced with fill values before downlink, reducing data volume by ~50% in the overlap regions.

### 3.2 Consequences for Fire Detection

1. **Missing data at scan edges:** The deleted bowtie rows appear as periodic stripes of NaN/fill values in the imagery. Fire pixels falling in these regions are simply lost.

2. **Pixel size variation:** Pixels at scan edge are ~1.6km x 1.6km (I-bands) vs. 375m x 375m at nadir. Larger pixels dilute the fire signal, reducing sensitivity to small fires at the scan edge.

3. **Duplicate observations:** Before onboard deletion, the same ground location would be observed by two adjacent scans in the overlap zone. After deletion, only one scan's observation remains.

### 3.3 How to Handle It

**Do NOT attempt to interpolate across bowtie gaps.** Interpolated values are not real measurements and will corrupt fire detection statistics.

Instead:
- Treat fill values as missing data
- The contextual algorithm should skip fill-value pixels when computing background statistics
- If a fire occurs in a bowtie-deleted region, it will be detected in the adjacent scan (different orbit pass) or by a different sensor (Himawari)

**In satpy:**
```python
scn.load(['I04'])
bt = scn['I04'].values
# Bowtie-deleted pixels are already NaN or fill value
valid = np.isfinite(bt)  # this naturally excludes bowtie deletions
```

### 3.4 VIIRS Pixel Aggregation

VIIRS also performs onboard pixel aggregation: at nadir, 1 sample = 1 pixel. At mid-swath, 2 samples are aggregated. At swath edge, 3 samples are aggregated. This keeps pixel size somewhat more uniform than MODIS but introduces discrete jumps in effective resolution along the scan.

---

## 4. Processing Order Dependencies

### 4.1 Critical Order: Cloud Mask Before Fire Detection

**Never run fire detection before cloud masking.** Cloud pixels will produce false fire detections. The processing order must be:

1. Radiometric calibration (L1b already done)
2. Cloud masking
3. Land/water masking
4. Fire candidate selection (absolute thresholds)
5. Background characterization (using non-cloud, non-water, non-fire pixels)
6. Contextual fire tests
7. False alarm rejection (sun glint, persistent sources)
8. FRP calculation

### 4.2 Cloud Mask Depends on Calibrated Data

Cloud detection algorithms operate on calibrated brightness temperatures and reflectances. You cannot cloud mask uncalibrated DN values. The good news: L1b products are already calibrated, so this dependency is automatically satisfied.

### 4.3 Background Statistics Depend on Cloud and Water Masks

The contextual fire detection algorithm computes background brightness temperature statistics (mean, standard deviation) from neighboring pixels. These statistics MUST exclude:
- Cloud pixels (cold, distort statistics downward)
- Water pixels (different thermal properties than land)
- Other fire candidate pixels (hot, distort statistics upward)

If cloud masking is incomplete (missed clouds), background statistics will be biased cold, producing false fire detections at cloud edges. If cloud masking is too aggressive (clear pixels flagged as cloud), background sample size shrinks, degrading the reliability of background statistics.

### 4.4 Resampling Should Come After Fire Detection (Usually)

For fire detection, work in the sensor's native coordinate system if possible. Resampling introduces:
- **Spatial smoothing** that reduces the peak brightness temperature of fire pixels (sub-pixel fires get averaged with background)
- **Geometric artifacts** at resampling boundaries
- **Processing time** that delays detection

Resample AFTER fire detection if you need results on a uniform grid for mapping or multi-sensor fusion.

**Exception:** If your fire detection algorithm requires a uniform grid (e.g., a CNN trained on gridded data), then resampling is necessary before detection.

### 4.5 Granule Boundary Issues (VIIRS)

VIIRS delivers data in 6-minute granules. The contextual fire algorithm needs neighboring pixels, including those that may be in an adjacent granule.

**Problem:** If you process granules independently, fire pixels at granule boundaries may have truncated background windows, leading to:
- Too few background pixels (algorithm falls back to less reliable fixed thresholds)
- Biased background statistics (one-sided sampling)

**Solution:** Load adjacent granules and concatenate them before running fire detection. In satpy:
```python
# Load multiple granules
sdr_files = glob('/data/viirs/SVI04*_d20260317_t18*.h5')  # all granules at ~18:00
scn = Scene(filenames=sdr_files, reader='viirs_sdr')
scn.load(['I04'])
# satpy handles multi-granule concatenation within a single Scene
```

---

## 5. Geometric / Geolocation Pitfalls

### 5.1 Himawari AHI Navigation Errors

AHI has documented navigation errors of ~0.3 pixels (north-south) and ~1 pixel (east-west) RMS. These errors can vary by scan segment.

**Impact on fire detection:** A 1-pixel shift means the contextual algorithm compares the wrong pixels. For a 2km pixel, this is a 2km geolocation error.

**Mitigation:** JMA applies INR (image navigation and registration) corrections, and the standard HSD products include these corrections. However, residual errors remain. If sub-pixel accuracy is needed:
- Use geometric correction methods that match image features (coastlines, lakes) to a reference
- The satpy AHI reader's `round_actual_position` option (default True) ensures geometric consistency between bands/segments

### 5.2 Parallax in Geostationary Imagery

Geostationary sensors view the Earth at an angle. Elevated features (tall clouds, volcanic plumes) appear displaced from their true ground position. For fire detection, this matters when:
- Using cloud mask products: a cloud at altitude appears shifted relative to the ground position it obscures
- Comparing fire detections against ground-truth coordinates

Parallax correction requires a DEM and the satellite viewing geometry. For routine fire detection, this is usually not worth the complexity.

### 5.3 Sentinel-2 Geometric Accuracy

Sentinel-2 MSI has excellent geometric accuracy (~2-3m absolute for L1C). However:
- Bands at different resolutions (10m, 20m, 60m) may have sub-pixel registration offsets
- The SWIR bands used for fire detection (B11, B12) are at 20m native resolution
- When computing spectral indices mixing 10m and 20m bands, resample to a common resolution first

---

## 6. Data Quality and Edge Cases

### 6.1 Night vs. Day Processing

Fire detection algorithms use different thresholds for day and night:
- Day (solar zenith < 85): T_I4 > 325-330K (higher threshold, more solar contamination)
- Night (solar zenith > 85): T_I4 > 310K (lower threshold, cleaner thermal signal)
- Twilight zone: transitional, some algorithms use interpolated thresholds

**Pitfall:** Incorrect solar zenith angle calculation leads to applying wrong thresholds. Use pyorbital or the solar zenith angle from the geolocation data, not a rough approximation.

### 6.2 Missing Segments (Himawari)

HSD data is split into 10 segments per band. If a segment is missing (download failure, data gap):
- The full-disk image will have a horizontal stripe of missing data
- Fire detection in adjacent segments should not be affected if you handle the NaN boundary correctly
- Monitor for missing segments in your download pipeline

### 6.3 Stale Land/Water Masks

Using an outdated land/water mask can cause:
- New reservoirs flagged as land, producing sun glint false alarms
- Dried lakes flagged as water, suppressing fire detection on newly exposed land
- Seasonal flooding not captured by annual masks

For Australia (XPrize context): seasonal water bodies are common in northern Australia. Consider using a mask that includes maximum water extent, accepting that some valid fire-detection land pixels will be masked during dry season.

### 6.4 Time Zone and Timestamp Confusion

- Himawari-8 timestamps are in UTC
- VIIRS granule timestamps use the form `_dYYYYMMDD_tHHMMSSS` (UTC)
- GOES timestamps encode year, day-of-year, hour, minute, second
- Fire occurrence times in local time must be converted carefully for validation
- Australia spans UTC+8 to UTC+11 depending on state and DST

### 6.5 Coordinate Reference System Mismatches

Common error: mixing lon/lat order or confusing EPSG codes when combining data from different sources.

- Himawari AHI native CRS: geostationary projection centered at 140.7E
- VIIRS native CRS: swath coordinates (lon, lat arrays, no grid projection)
- GOES native CRS: geostationary projection centered at 75.2W (GOES-16), 137.2W (GOES-17)
- Landsat: UTM zones
- MOD44W land/water mask: MODIS sinusoidal projection

Always verify CRS alignment when applying masks or combining datasets. Off-by-one-pixel shifts are easy to introduce and hard to debug.

---

## 7. Summary: Top 10 Pitfalls to Avoid

1. **Running fire detection without cloud masking** -- guaranteed false alarms at cloud edges
2. **Not buffering the cloud mask** -- cloud edges still cause false alarms even with a cloud mask
3. **Interpolating bowtie-deleted pixels** -- introduces fake data
4. **Using L2A (atmospherically corrected) Sentinel-2 near fires** -- smoke confuses the correction
5. **Using Landsat Band 11 for quantitative BT** -- stray light contamination
6. **Processing VIIRS granules independently** -- truncated background windows at boundaries
7. **Resampling before fire detection** -- smooths away the fire signal
8. **Applying daytime thresholds at night or vice versa** -- wrong SZA classification
9. **Ignoring I4 saturation** -- underestimates fire intensity, may misclassify
10. **Assuming sensors agree** -- different spectral response functions produce different BTs for the same scene
