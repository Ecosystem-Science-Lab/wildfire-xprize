# Training Data Catalog

Comprehensive catalog of datasets available for building wildfire detection training data, with metadata for each.

---

## Active Fire Detection Products

### 1. FIRMS MODIS Collection 6.1

| Attribute | Value |
|-----------|-------|
| **Full Name** | MODIS Collection 6.1 Active Fire Product (MCD14DL) |
| **Provider** | NASA LANCE / University of Maryland |
| **Spatial Resolution** | 1 km (at nadir; degrades to ~2x5 km at scan edges) |
| **Temporal Resolution** | ~4 overpasses/day (Terra ~10:30/22:30, Aqua ~13:30/01:30 local) |
| **Coverage** | Global |
| **Time Range** | November 2000 - present |
| **Format** | CSV, Shapefile, KML |
| **Fields** | latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence (0-100), version, bright_t31, frp, type, daynight |
| **Access** | FIRMS API, archive download, GEE (`FIRMS`), GEE community catalog (vector) |
| **Registration** | NASA Earthdata Login + MAP_KEY |
| **URL** | https://firms.modaps.eosdis.nasa.gov/ |
| **License** | Free, no restrictions |
| **Use Case** | Long-term fire climatology, training label source (coarse resolution) |

### 2. FIRMS VIIRS S-NPP 375m

| Attribute | Value |
|-----------|-------|
| **Full Name** | VIIRS S-NPP 375m Active Fire Product (VNP14IMGTDL) |
| **Provider** | NASA LANCE / University of Maryland |
| **Spatial Resolution** | 375 m (at nadir) |
| **Temporal Resolution** | ~2 overpasses/day (~13:30/01:30 local) |
| **Coverage** | Global |
| **Time Range** | January 20, 2012 - present |
| **Format** | CSV, Shapefile |
| **Fields** | latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, confidence (low/nominal/high), version, bright_ti5, frp, daynight |
| **Access** | FIRMS API (source: `VIIRS_SNPP_SP` or `VIIRS_SNPP_NRT`), archive download, GEE community catalog (vector) |
| **Registration** | NASA Earthdata Login + MAP_KEY |
| **License** | Free, no restrictions |
| **Use Case** | Primary fire detection label source; best balance of resolution and coverage |

### 3. FIRMS VIIRS NOAA-20 375m

| Attribute | Value |
|-----------|-------|
| **Full Name** | VIIRS NOAA-20 375m Active Fire Product |
| **Spatial Resolution** | 375 m |
| **Time Range** | April 1, 2018 - present |
| **Access** | FIRMS API (source: `VIIRS_NOAA20_SP` or `VIIRS_NOAA20_NRT`) |
| **Notes** | Same orbit as S-NPP but offset by ~50 minutes; doubles temporal sampling |

### 4. FIRMS VIIRS NOAA-21 375m

| Attribute | Value |
|-----------|-------|
| **Full Name** | VIIRS NOAA-21 375m Active Fire Product |
| **Spatial Resolution** | 375 m |
| **Time Range** | January 17, 2024 - present |
| **Access** | FIRMS API (source: `VIIRS_NOAA21_NRT`) |
| **Notes** | Latest VIIRS sensor; limited historical data |

### 5. FIRMS Landsat 30m

| Attribute | Value |
|-----------|-------|
| **Full Name** | Landsat Active Fire Product |
| **Spatial Resolution** | 30 m |
| **Time Range** | June 20, 2022 - present |
| **Coverage** | US and Canada only |
| **Access** | FIRMS API (source: `LANDSAT_NRT`) |
| **Notes** | Highest resolution active fire product but limited geographic coverage; not available for Australia |

### 6. DEA Hotspots (Australia)

| Attribute | Value |
|-----------|-------|
| **Full Name** | Digital Earth Australia Hotspots |
| **Provider** | Geoscience Australia |
| **Spatial Resolution** | ~375 m (based on VIIRS) |
| **Temporal Resolution** | Updated every 10 minutes |
| **Coverage** | Australia |
| **Time Range** | Near real-time (limited archive) |
| **Format** | WMS, WFS (web services) |
| **Access** | https://hotspots.dea.ga.gov.au/ |
| **Registration** | None for viewing; WFS for programmatic access |
| **License** | CC BY 4.0 |
| **Use Case** | Real-time fire monitoring during competition; Australian fire detection validation |

---

## Burned Area Products

### 7. MCD64A1 v6.1 (MODIS Burned Area)

| Attribute | Value |
|-----------|-------|
| **Full Name** | MODIS/Terra+Aqua Burned Area Monthly L3 Global 500m |
| **Provider** | NASA LP DAAC / University of Maryland |
| **Spatial Resolution** | 500 m |
| **Temporal Resolution** | Monthly |
| **Coverage** | Global |
| **Time Range** | November 2000 - present |
| **Format** | HDF-EOS5, GeoTIFF (via AppEEARS) |
| **Bands** | BurnDate (Julian day), Uncertainty, QA, FirstDay, LastDay |
| **Access** | GEE (`MODIS/061/MCD64A1`), AppEEARS, LP DAAC data pool, UMD SFTP |
| **Registration** | Earthdata Login |
| **License** | Free, no restrictions |
| **Use Case** | Mapping burned area extent; generating fire/no-fire labels at 500m; fire regime analysis |

### 8. Landsat Collection 2 Level-3 Burned Area

| Attribute | Value |
|-----------|-------|
| **Full Name** | Landsat C2 L3 Burned Area Science Product |
| **Provider** | USGS |
| **Spatial Resolution** | 30 m |
| **Temporal Resolution** | Per-scene (16-day revisit) |
| **Coverage** | Primarily CONUS; check Australia availability |
| **Time Range** | 1984 - present (Landsat 4-9) |
| **Format** | GeoTIFF |
| **Bands** | Burn classification, burn probability |
| **Access** | USGS EarthExplorer, GEE community catalog |
| **License** | Free |
| **Use Case** | High-resolution burned area mapping; limited Australian coverage |

### 9. FESM 2019/20 (NSW Black Summer)

| Attribute | Value |
|-----------|-------|
| **Full Name** | Fire Extent and Severity Mapping, 2019/20 Fire Year |
| **Provider** | NSW Department of Planning, Industry and Environment |
| **Spatial Resolution** | 10 m |
| **Temporal Resolution** | Single fire year (Jul 2019 - Jun 2020) |
| **Coverage** | NSW, Australia |
| **Time Range** | July 2019 - June 2020 |
| **Format** | GeoTIFF (.tif), ERDAS Imagine (.img) |
| **Content** | Fire extent and severity classes for all wildfires >10 ha |
| **Access** | https://datasets.seed.nsw.gov.au/dataset/fire-extent-and-severity-mapping-fesm-2019-20 |
| **Registration** | None |
| **License** | Check SEED metadata |
| **Use Case** | Gold-standard validation data for Black Summer; highest resolution fire mapping for NSW |

---

## Fire History Databases

### 10. NPWS Fire History (NSW)

| Attribute | Value |
|-----------|-------|
| **Full Name** | NPWS Fire History - Wildfires and Prescribed Burns |
| **Provider** | NSW National Parks and Wildlife Service |
| **Type** | Vector polygons |
| **Coverage** | NSW, Australia |
| **Time Range** | ~1902 - present |
| **Format** | Shapefile (WGS84/GDA94) |
| **Fields** | FireType (1=Wildfire, 2=Prescribed), Year, Area_ha, geometry |
| **Access** | https://datasets.seed.nsw.gov.au/dataset/fire-history-wildfires-and-prescribed-burns-1e8b6 |
| **Direct Download** | fire_npwsfirehistory.zip |
| **License** | Available under license; check metadata |
| **Use Case** | Historical fire frequency mapping; spatial priors; identifying fire-prone locations |

### 11. NSW Fire History (RFS)

| Attribute | Value |
|-----------|-------|
| **Full Name** | NSW Fire History (Rural Fire Service) |
| **Provider** | NSW Rural Fire Service |
| **Type** | Hosted feature layer |
| **Coverage** | NSW, Australia |
| **Time Range** | 2000s - present |
| **Format** | Feature layer (ArcGIS) |
| **Fields** | fire_id, fire_name, ignition_date, area, source system |
| **Access** | https://data.nsw.gov.au/data/dataset/1-27291ccb6b6a4fe1a32d3bf72a7280c9 |
| **License** | AFAC Fire History Guidelines compliant |
| **Use Case** | Complements NPWS data with RFS operational fire records |

### 12. GlobFire (GWIS)

| Attribute | Value |
|-----------|-------|
| **Full Name** | GlobFire - Global Wildfire Event Database |
| **Provider** | JRC/European Commission (GWIS) |
| **Type** | Fire event polygons with daily progression |
| **Coverage** | Global |
| **Time Range** | 2001 - 2023 |
| **Format** | PostgreSQL dump files, GEE FeatureCollection |
| **Fields** | fire_id, initial_date, end_date, multi-polygon geometry, daily burned areas |
| **Access** | PANGAEA (https://doi.pangaea.de/10.1594/PANGAEA.943975), GEE (`JRC/GWIS/GlobFire/v2/DailyPerimeters`) |
| **License** | CC BY |
| **Use Case** | Global fire regime analysis; individual fire event tracking and progression |

---

## Fire Emissions and Aggregate Products

### 13. GFED5.1

| Attribute | Value |
|-----------|-------|
| **Full Name** | Global Fire Emissions Database Version 5.1 |
| **Provider** | VU Amsterdam / NASA |
| **Spatial Resolution** | 0.25 deg (2001-2022); 1.0 deg (1997-2000) |
| **Temporal Resolution** | Monthly |
| **Coverage** | Global |
| **Time Range** | 1997 - present (with NRT extensions) |
| **Format** | NetCDF4 |
| **Content** | Burned area fractions, fire emissions (CO2, CO, CH4, etc.), fire types |
| **Access** | SFTP via https://www.globalfiredata.org/data.html |
| **Registration** | None |
| **License** | Free for research |
| **Use Case** | Regional fire statistics; emissions analysis; coarse fire climatology |

### 14. ABARES Forest Fire Data

| Attribute | Value |
|-----------|-------|
| **Full Name** | Australian Bureau of Agricultural and Resource Economics Forest Fire Data |
| **Provider** | Australian Government DAFF |
| **Coverage** | Australia |
| **Access** | https://www.agriculture.gov.au/abares/forestsaustralia/forest-data-maps-and-tools/data-by-topic/fire |
| **Use Case** | National forest fire statistics; long-term trends |

---

## Fire Weather and Danger Indices

### 15. Copernicus CEMS Fire Danger Historical

| Attribute | Value |
|-----------|-------|
| **Full Name** | Fire Danger Indices Historical Data from CEMS |
| **Provider** | ECMWF / Copernicus |
| **Spatial Resolution** | ~28 km (0.25 deg ERA5 grid) |
| **Temporal Resolution** | Daily |
| **Coverage** | Global |
| **Time Range** | 1940 - present |
| **Format** | GRIB, NetCDF |
| **Variables** | FWI, FFMC, DMC, DC, ISI, BUI, DSR, FFDI (McArthur), Mark 5 |
| **Access** | CDS API (dataset: `cems-fire-historical-v1`) |
| **Registration** | Copernicus CDS account |
| **DOI** | 10.24381/cds.0e89c522 |
| **License** | Copernicus license (free, attribution required) |
| **Use Case** | Historical fire weather analysis; FFDI reconstruction; fire risk modeling |

### 16. ERA5 Reanalysis

| Attribute | Value |
|-----------|-------|
| **Full Name** | ECMWF Reanalysis v5 |
| **Provider** | ECMWF / Copernicus |
| **Spatial Resolution** | 0.25 deg (~28 km) |
| **Temporal Resolution** | Hourly |
| **Coverage** | Global |
| **Time Range** | 1940 - present (~5 day latency) |
| **Format** | GRIB, NetCDF |
| **Relevant Variables** | 2m temperature, 2m dewpoint, 10m wind (u/v), precipitation, soil moisture, solar radiation |
| **Access** | CDS API (`reanalysis-era5-single-levels`), GEE (`ECMWF/ERA5/DAILY`, `ECMWF/ERA5_LAND/DAILY_AGGR`) |
| **Registration** | Copernicus CDS account |
| **License** | Copernicus license |
| **Use Case** | Compute FFDI from gridded weather; fire weather context for any historical fire |

### 17. BOM FFDI Climatology

| Attribute | Value |
|-----------|-------|
| **Full Name** | Bureau of Meteorology Forest Fire Danger Index Climatology |
| **Provider** | Australian Bureau of Meteorology |
| **Spatial Resolution** | 0.05 deg (~5 km) |
| **Coverage** | Australia |
| **Time Range** | 1950 - 2016+ |
| **Format** | Gridded (maps and data services) |
| **Access** | https://www.bom.gov.au/climate/maps/averages/ffdi/ |
| **Use Case** | Baseline FFDI values; spatial fire risk priors |

### 18. Mendeley FFDI Dataset

| Attribute | Value |
|-----------|-------|
| **Full Name** | Seasonal McArthur FFDI Data for Australia: 1973-2017 |
| **Provider** | Research dataset (Mendeley Data) |
| **Time Range** | 1973 - 2017 |
| **Format** | Tabular |
| **Access** | https://data.mendeley.com/datasets/xf5bv3hcvw/2 |
| **Use Case** | Long-term seasonal FFDI trends for fire risk analysis |

---

## Satellite Imagery Sources (for Matching with Fire Labels)

### 19. Sentinel-2 MSI

| Attribute | Value |
|-----------|-------|
| **Spatial Resolution** | 10m (VNIR), 20m (SWIR/RedEdge), 60m (atmosphere) |
| **Revisit** | 5 days (2 satellites) |
| **Key Bands** | B4 (Red), B8 (NIR), B8A (NIR narrow), B11 (SWIR 1.6um), B12 (SWIR 2.2um) |
| **GEE ID** | `COPERNICUS/S2_SR_HARMONIZED` (surface reflectance) |
| **Use Case** | High-resolution burn scar mapping via NBR/dNBR; training imagery for fire detection models |

### 20. Landsat 8/9

| Attribute | Value |
|-----------|-------|
| **Spatial Resolution** | 30m (multispectral), 15m (panchromatic), 100m (thermal) |
| **Revisit** | 16 days per satellite (8 days combined) |
| **Key Bands** | B5 (NIR), B6 (SWIR 1.6um), B7 (SWIR 2.2um), B10 (TIR) |
| **GEE ID** | `LANDSAT/LC08/C02/T1_L2` (Landsat 8), `LANDSAT/LC09/C02/T1_L2` (Landsat 9) |
| **Use Case** | Longer historical record than Sentinel-2; thermal band for fire detection |

### 21. VIIRS Imagery

| Attribute | Value |
|-----------|-------|
| **Spatial Resolution** | 375m (I-bands), 750m (M-bands) |
| **Key Bands** | I1-I5 (Vis-SWIR-TIR), M11 (SWIR 2.25um) |
| **Access** | NASA LAADS DAAC, GEE |
| **Use Case** | Same sensor as FIRMS detections; direct spectral matching for training |

---

## Pre-Built Training Datasets

### 22. TS-SatFire

| Attribute | Value |
|-----------|-------|
| **Full Name** | Time-Series Satellite Imagery for Wildfire Detection and Prediction |
| **Coverage** | Contiguous US |
| **Time Range** | January 2017 - October 2021 |
| **Size** | 71 GB; 3,552 surface reflectance images; 179 fire events |
| **Sensor** | VIIRS (I1-I5, M11 bands) |
| **Labels** | Active fire and burned area from FIRMS + NIFC |
| **Access** | Kaggle (https://www.kaggle.com/datasets/z789456sx/ts-satfire), GitHub |
| **Use Case** | Pre-built benchmark; US-focused but code/methodology transferable to Australia |

### 23. Wildfire Detection Image Data (Kaggle)

| Attribute | Value |
|-----------|-------|
| **Access** | https://www.kaggle.com/datasets/brsdincer/wildfire-detection-image-data |
| **Content** | RGB images for fire/no-fire classification |
| **Use Case** | Quick prototyping; limited use for satellite-based detection |

---

## GEE Community Catalog (Vector Fire Data)

### 24. FIRMS VIIRS Vector (Community Catalog)

| Attribute | Value |
|-----------|-------|
| **GEE Path** | `projects/sat-io/open-datasets/VIIRS/VNP14IMGTDL_NRT_{YYYY}` |
| **Type** | ee.FeatureCollection (point features) |
| **Time Range** | 2012-2021 |
| **Fields** | Latitude, Longitude, Bright_ti4, Scan, Track, Acq_Date, Acq_Time, Satellite, Confidence, Version, Bright_ti5, FRP, DayNight |
| **Use Case** | Efficient spatial/temporal queries of fire detections within GEE |

### 25. FIRMS MODIS Vector (Community Catalog)

| Attribute | Value |
|-----------|-------|
| **GEE Path** | `projects/sat-io/open-datasets/MODIS_MCD14DL/MCD14DL_{YYYY}` |
| **Type** | ee.FeatureCollection (point features) |
| **Time Range** | 2000-2020 |
| **Fields** | Latitude, Longitude, Brightness, Scan, Track, Acq_Date, Acq_Time, Satellite, Confidence, Version, Bright_T31, FRP, Type, DayNight |
| **Use Case** | Long-term fire detection record in GEE; historical fire analysis |

---

## Quick Reference: Which Dataset for Which Task?

| Task | Recommended Primary Dataset | Recommended Secondary |
|------|----------------------------|----------------------|
| Fire detection labels (high res) | FIRMS VIIRS 375m | DEA Hotspots (Australia) |
| Fire detection labels (long term) | FIRMS MODIS 1km | FIRMS VIIRS (2012+) |
| Burned area mapping | MCD64A1 500m | FESM 10m (NSW only) |
| Burn severity | FESM (NSW) | Sentinel-2 dNBR |
| Fire history / frequency | NPWS Fire History | GlobFire |
| Fire weather context | Copernicus CEMS FFDI | ERA5 + manual FFDI computation |
| Regional fire emissions | GFED5.1 | -- |
| Training imagery | Sentinel-2 (10-20m) | VIIRS imagery (375m) |
| Validation (NSW) | FESM 2019/20 | FIRMS + NPWS Fire History |
