# Historical Fire Data - Domain Overview

## Purpose

Historical fire data serves four critical functions for the XPRIZE wildfire detection system:

1. **Training ML classifiers**: Fire/no-fire binary classifiers and severity models
2. **Validating detection algorithms**: Ground-truth for testing detection latency and accuracy
3. **Building baseline models**: Background thermal/spectral signatures for anomaly detection
4. **Understanding Australian fire behavior**: Season patterns, vegetation-specific fire dynamics, spotting behavior

## Dataset Landscape

### Tier 1: Primary Active Fire Detection Archives

| Dataset | Resolution | Coverage | Period | Access |
|---------|-----------|----------|--------|--------|
| FIRMS MODIS C6.1 | 1 km | Global | Nov 2000 - present | API + archive download |
| FIRMS VIIRS S-NPP | 375 m | Global | Jan 2012 - present | API + archive download |
| FIRMS VIIRS NOAA-20 | 375 m | Global | Apr 2018 - present | API + archive download |
| FIRMS VIIRS NOAA-21 | 375 m | Global | Jan 2024 - present | API + archive download |
| DEA Hotspots (Australia) | ~375 m | Australia | Near real-time | WMS/WFS |

### Tier 2: Burned Area Products

| Dataset | Resolution | Coverage | Period | Access |
|---------|-----------|----------|--------|--------|
| MCD64A1 v6.1 | 500 m | Global, monthly | Nov 2000 - present | GEE, AppEEARS, LP DAAC |
| Landsat C2 L3 Burned Area | 30 m | CONUS (primarily) | 1984 - present | USGS, GEE |
| GFED5 | 0.25 deg | Global, monthly | 1997 - present | SFTP (netCDF) |
| GlobFire (GWIS) | 500 m (derived) | Global | 2001 - 2023 | PostgreSQL dump, GEE |

### Tier 3: Australian-Specific Datasets

| Dataset | Resolution | Coverage | Period | Access |
|---------|-----------|----------|--------|--------|
| NPWS Fire History (NSW) | Vector polygons | NSW | 1902 - present | SEED portal (shapefile) |
| NSW Fire History (RFS) | Vector polygons | NSW | 2000s - present | Data.NSW (feature layer) |
| FESM 2019/20 (Black Summer) | 10 m raster | NSW | Jul 2019 - Jun 2020 | SEED portal (GeoTIFF) |
| ABARES Forest Fire Data | Various | Australia | Multiple years | agriculture.gov.au |

### Tier 4: Fire Weather & Danger Indices

| Dataset | Resolution | Coverage | Period | Access |
|---------|-----------|----------|--------|--------|
| Copernicus CEMS Fire Danger | ~28 km (ERA5) | Global | 1940 - present | CDS API |
| BOM FFDI Climatology | 0.05 deg | Australia | 1950 - 2016+ | BOM data services |
| ERA5 Reanalysis | 0.25 deg | Global | 1940 - present | CDS API, GEE |
| AFDRS (replaces FFDI) | Various | Australia | Sep 2022 - present | BOM, AFDRS viewer |

## XPRIZE-Specific Relevance

### For the NSW Competition Context

The finals take place in NSW, Australia (April 2026). Key considerations:

- **Black Summer 2019-2020** is the gold-standard validation dataset: 5.5M hectares burned in NSW, extensively mapped at 10m resolution (FESM), with FIRMS detections available throughout
- **NPWS Fire History** provides 100+ years of fire polygon boundaries for NSW, essential for understanding fire-prone areas and building spatial priors
- **Fire season**: Typically October-March in NSW, but the competition is in April (shoulder season). Prescribed burns are common in autumn/winter
- **Vegetation**: NSW spans wet sclerophyll (Blue Mountains), dry sclerophyll, grasslands, and coastal heath -- each with distinct fire signatures

### For Training Data Construction

The recommended approach is:

1. **Positive samples**: Match FIRMS active fire detections to contemporaneous satellite imagery (Sentinel-2, Landsat, VIIRS). Use high-confidence FIRMS points only
2. **Negative samples**: Sample from confirmed fire-free periods at same locations (temporal negatives) and from areas with no fire history (spatial negatives)
3. **Validation set**: Reserve Black Summer 2019-2020 NSW fires as a held-out validation dataset using FESM ground truth
4. **Class balance**: Fire pixels are <1% of any scene; use stratified sampling with fire-centered patches

### Critical Data Gaps

- Active fire products (MODIS/VIIRS) only have a few overpasses per day -- they capture fire presence, not ignition
- Geostationary satellite data (Himawari-8/9) provides higher temporal resolution but at coarser spatial resolution (~2 km)
- No single dataset captures the full lifecycle of a fire from ignition through suppression
- NRT data quality is lower than standard processing (SP) data; SP data has ~5 month latency

## Key Access Requirements

| Resource | Registration Needed |
|----------|-------------------|
| FIRMS API | NASA Earthdata Login + MAP_KEY |
| AppEEARS | NASA Earthdata Login |
| Google Earth Engine | Google account + GEE approval |
| Copernicus CDS | ECMWF/Copernicus account + API key |
| GFED | None (public SFTP) |
| SEED NSW | None (public download) |
| BOM Data | Account for some products |
