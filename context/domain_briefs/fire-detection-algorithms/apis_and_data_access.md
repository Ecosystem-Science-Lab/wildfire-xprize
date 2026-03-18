# Fire Detection Algorithms — APIs and Data Access

## Algorithm Reference Documents (ATBDs)

### VIIRS VNP14IMG
- **ATBD**: https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_375m_ATBD.pdf
- **User Guide**: https://lpdaac.usgs.gov/documents/427/VNP14_User_Guide_V1.pdf
- **Product page**: https://lpdaac.usgs.gov/products/vnp14imgv002/
- **Schroeder et al. 2014** (algorithm description paper): https://www.earthdata.nasa.gov/sites/default/files/imported/Schroeder_et_al_2014b_RSE.pdf

### GOES ABI FDCA
- **ATBD**: https://www.star.nesdis.noaa.gov/atmospheric-composition-training/documents/ABI_FDC_ATBD.pdf
- **Product guide**: Available via NOAA NESDIS
- **ABI channel specs**: https://www.star.nesdis.noaa.gov/atmospheric-composition-training/abi_channels.php

### MODIS MOD14/MYD14
- **ATBD**: https://modis-fire.umd.edu/files/MODIS_Fire_C6_C61_ATBD.pdf
- **Product page**: https://lpdaac.usgs.gov/products/mod14v006/

## Pre-computed Fire Detection Products

### NASA FIRMS (Fire Information for Resource Management System)
The easiest way to get fire detection results without running algorithms ourselves.

**Registration**: Request free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/area/

**API Endpoints**:
```
# Active fires by area (CSV)
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{area}/{days}/{date}

# Sources: VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT, MODIS_NRT
# Area: world, country code, or bounding box (west,south,east,north)
# Days: 1-10
# Date: YYYY-MM-DD (optional, defaults to most recent)

# Example: VIIRS NOAA-20 fires in Australia, last 2 days
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/VIIRS_NOAA20_NRT/country/AUS/2

# Example: fires in NSW bounding box
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/VIIRS_SNPP_NRT/148,-37,154,-28/1
```

**Response fields**: latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, instrument, confidence, version, bright_t31, frp, daynight, type

**Timeliness tiers**:
- URT (Ultra Real-Time): <60 seconds, US/Canada only
- RT (Real-Time): ~30 minutes
- NRT (Near Real-Time): ≤3 hours globally

**Rate limits**: Varies by MAP_KEY tier. Standard keys allow reasonable query frequency.

### FIRMS WFS/WMS
For GIS integration:
```
# WFS endpoint
https://firms.modaps.eosdis.nasa.gov/geoserver/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=fires_viirs_snpp_nrt&outputFormat=application/json&CQL_FILTER=latitude>-37 AND latitude<-28 AND longitude>148 AND longitude<154
```

## Raw Satellite Data for Running Our Own Algorithms

### VIIRS SDR/EDR (for custom detection)
If we want to run modified VNP14IMG with tuned thresholds:

**AWS NODD (JPSS)**:
- Bucket: `noaa-jpss`
- SNS topic for new data notifications
- Contains SDR (sensor data records) with I-band radiances
- See streaming-data-engineering domain for ingestion details

**NASA LAADS DAAC**:
- VNP02IMG (calibrated radiances): https://ladsweb.modaps.eosdis.nasa.gov
- VNP03IMG (geolocation): paired with VNP02IMG
- Requires Earthdata login

### Himawari AHI (for custom geostationary detection)
**AWS**: `noaa-himawari` bucket (check availability and coverage)
**JMA**: HimawariCloud for institutional partners, HimawariCast for broadcast
**Format**: Himawari Standard Data (HSD) — 10 segments per full disk per band
See satellite-remote-sensing domain for format details.

### GOES ABI (reference/testing, not for Australia)
**AWS NODD**: `noaa-goes18` and `noaa-goes19` buckets
- L1b-RadC (CONUS), L1b-RadF (Full Disk), L1b-RadM (Mesoscale)
- L2-FDCC (CONUS fire), L2-FDCF (Full Disk fire) — pre-computed detections
- SNS push notifications available

## Ancillary Data Needed by Algorithms

### Land/Water Masks
- **MODIS MCD12Q1** (yearly land cover, 500 m): https://lpdaac.usgs.gov/products/mcd12q1v061/
- **VIIRS land-water mask**: Bundled with VNP14IMG processing
- **Natural Earth**: Simplified vector data, good for coarse masking

### Digital Elevation Models (for terrain effects)
- **SRTM 30m**: https://dwtkns.com/srtm30m/ or AWS terrain tiles
- **Copernicus DEM**: Via Copernicus Data Space STAC API

### Fire Weather Data (for context)
- **Bureau of Meteorology (Australia)**: FFDI gridded products
- **ERA5**: Reanalysis for historical fire weather context

## Key Papers Worth Downloading
These contain the actual algorithm details we need to implement:

1. **Schroeder et al. 2014** — "The New VIIRS 375 m active fire detection data product" (RSE) — Core algorithm paper
2. **VIIRS ATBD** — Full threshold values and pseudocode
3. **GOES ABI FDC ATBD** — Geostationary algorithm with Dozier method
4. **Wooster et al. 2003** — FRP retrieval method used by VIIRS
5. **Xu et al. 2021** — Himawari-8 fire detection validation (if available)
