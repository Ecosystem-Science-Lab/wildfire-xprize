# Satellite Data Preprocessing for Wildfire Detection

## Overview

Satellite data preprocessing converts raw sensor measurements into analysis-ready inputs for fire detection algorithms. The preprocessing chain varies by sensor and use case, but the core question for a real-time fire detection system is: **what is the minimum preprocessing needed to reliably detect thermal anomalies?**

The answer: surprisingly little beyond what L1b products already provide, but cloud masking is non-negotiable and geometric awareness is critical.

## Sensor Inventory and Key Bands

| Sensor | Platform | Fire-relevant bands | Spatial res | Temporal res | Data level typically used |
|--------|----------|-------------------|-------------|--------------|--------------------------|
| AHI | Himawari-8/9 | B07 (3.9um), B13 (10.4um), B14 (11.2um), B15 (12.4um) | 2km IR | 10min full disk | L1b HSD |
| VIIRS | S-NPP, NOAA-20/21 | I4 (3.74um), I5 (11.45um), M13 (4.05um) | 375m (I), 750m (M) | ~12hr revisit | SDR (L1b equivalent) |
| ABI | GOES-16/17/18 | B07 (3.9um), B13 (10.3um), B14 (11.2um), B15 (12.3um) | 2km IR | 5-15min | L1b radiance |
| OLI/TIRS | Landsat 8/9 | B7 (2.2um SWIR), B10 (10.9um), B11 (12.0um) | 30m/100m | 16 days | L1 DN or L2 |
| MSI | Sentinel-2 | B12 (2.19um SWIR), B11 (1.61um SWIR) | 20m | 5 days | L1C (TOA) or L2A (BOA) |

**Note:** Sentinel-2 has no thermal bands. Fire detection with Sentinel-2 relies on SWIR anomalies and spectral indices (e.g., NBR), not brightness temperature.

## Preprocessing Pipeline: What Actually Needs to Happen

### For Geostationary Sensors (Himawari AHI, GOES ABI) -- Real-time Priority

These are the workhorses for early detection due to high temporal resolution.

**Required steps:**
1. **Radiometric calibration** (L1b already done): DN to radiance to brightness temperature. L1b products have calibration applied. You just need the radiance-to-BT conversion using the Planck function.
2. **Cloud masking** (CRITICAL): Clouds obscure fires and cloud edges cause false positives. Must be done.
3. **Land/water masking** (fast, static): Apply a pre-computed mask. Sun glint over water causes false alarms.
4. **Geolocation verification**: AHI has ~0.3-1 pixel navigation errors. Matters for contextual algorithms that compare neighboring pixels.

**Can be skipped for speed:**
- Full atmospheric correction (fire algorithms use brightness temperature directly, not surface temperature)
- Orthorectification (geostationary geometry is relatively stable; parallax only matters for elevated targets like volcanic plumes)

### For Polar-orbiting Sensors (VIIRS, MODIS) -- Higher Resolution

**Required steps:**
1. **Radiometric calibration** (SDR/L1b already done): Calibration coefficients, F-factor correction already applied in SDR products.
2. **Cloud masking**: Use VIIRS Cloud Mask (VCM) or run simplified cloud screening.
3. **Land/water masking**: Use MOD44W or quarterly land/water mask.
4. **Bowtie handling** (VIIRS-specific): Bowtie-deleted pixels are already fill-valued in SDR. Don't interpolate them -- just exclude from analysis.
5. **Granule stitching**: VIIRS delivers 6-minute granules. For contextual algorithms needing neighbor pixels across granule boundaries, you need to stitch adjacent granules.

**Can be skipped for speed:**
- Atmospheric correction
- Terrain correction / orthorectification (unless precise geolocation matters for your downstream product)
- Resampling to a uniform grid (fire algorithms can work in sensor-native coordinates)

### For High-resolution Sensors (Landsat, Sentinel-2) -- Confirmation/Mapping

These are too infrequent for real-time detection but valuable for fire perimeter mapping and confirmation.

**Required steps:**
1. **Radiometric calibration**: L1 products provide DN; convert to TOA radiance/reflectance using MTL metadata coefficients.
2. **Cloud masking**: Landsat QA band or Fmask; Sentinel-2 SCL band or s2cloudless.
3. **For Sentinel-2**: L1C (TOA) is often preferred over L2A (BOA) for fire detection because atmospheric correction can fail in smoky conditions. The correction introduces artifacts near active fires.

**Atmospheric correction considerations:**
- L2A processing can confuse smoke with cloud or introduce false surface reflectance values near fires.
- For fire detection, TOA reflectance with SWIR-based spectral indices works well.

## Key Principle: Fire Algorithms Work on Brightness Temperature

The single most important insight for preprocessing optimization:

**Standard fire detection algorithms (MODIS MOD14, VIIRS VNP14, WF-ABBA) all operate on brightness temperature, NOT surface temperature.** They do NOT require atmospheric correction.

The algorithms use:
- Absolute brightness temperature thresholds (e.g., T_4um > 325K daytime)
- Brightness temperature differences (delta_T = T_4um - T_11um)
- Contextual comparisons (pixel vs. background mean/stdev)

Atmospheric effects are implicitly handled by the contextual approach: neighboring pixels experience the same atmospheric column, so the relative comparison cancels out most atmospheric signal.

## Processing Time Budget (Approximate)

For a real-time system processing Himawari-8 full disk (every 10 minutes):

| Step | Time estimate | Notes |
|------|--------------|-------|
| Download HSD segments | 30-60s | 10 segments per band, ~50MB per IR band |
| Read + calibrate to BT | 2-5s | Satpy handles this; linear transform + Planck function |
| Cloud masking | 5-15s | Depends on algorithm complexity |
| Land/water masking | <1s | Static mask lookup |
| Fire detection algorithm | 5-30s | Depends on algorithm complexity |
| **Total** | **~45-110s** | Fits within 10-minute cadence |

## File Organization in This Brief

- `algorithms.md` -- Calibration equations, atmospheric correction methods, cloud detection algorithms
- `apis_and_data_access.md` -- Data sources, download tools, ancillary data (DEMs, masks)
- `code_patterns.md` -- Working code with satpy, pyresample, rasterio, s2cloudless
- `pitfalls.md` -- Calibration drift, cloud/fire confusion, bowtie artifacts, processing order gotchas
