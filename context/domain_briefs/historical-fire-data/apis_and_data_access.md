# APIs and Data Access

## 1. NASA FIRMS (Fire Information for Resource Management System)

### Registration
- **Requirement**: NASA Earthdata Login (free) + FIRMS MAP_KEY
- **Earthdata Login**: https://urs.earthdata.nasa.gov/users/new
- **MAP_KEY**: https://firms.modaps.eosdis.nasa.gov/api/map_key/ (request after Earthdata login)

### FIRMS REST API (v4.0)

**Base URL**: `https://firms.modaps.eosdis.nasa.gov`

**Area endpoint (primary use case):**
```
GET /api/area/csv/{MAP_KEY}/{SOURCE}/{AREA_COORDS}/{DAY_RANGE}
GET /api/area/csv/{MAP_KEY}/{SOURCE}/{AREA_COORDS}/{DAY_RANGE}/{DATE}
```

**Source codes:**
| Code | Description |
|------|-------------|
| `MODIS_NRT` | MODIS Near Real-Time |
| `MODIS_SP` | MODIS Standard Processing (science quality) |
| `VIIRS_SNPP_NRT` | VIIRS S-NPP Near Real-Time |
| `VIIRS_SNPP_SP` | VIIRS S-NPP Standard Processing |
| `VIIRS_NOAA20_NRT` | VIIRS NOAA-20 Near Real-Time |
| `VIIRS_NOAA20_SP` | VIIRS NOAA-20 Standard Processing |
| `VIIRS_NOAA21_NRT` | VIIRS NOAA-21 Near Real-Time |
| `LANDSAT_NRT` | Landsat (US/Canada only) |

**Parameters:**
- `AREA_COORDS`: Bounding box as `west,south,east,north` (e.g., `148,-38,154,-28` for NSW) or `world`
- `DAY_RANGE`: 1-5 days per query
- `DATE`: `YYYY-MM-DD` format; omit for most recent data

**Rate limits**: 5,000 transactions per 10-minute interval. Large requests may consume multiple transactions.

**Other endpoints:**
- `/api/data_availability/` -- check date coverage for SP and NRT
- `/api/kml_fire_footprints/` -- KML format output
- `/api/missing_data/` -- dates with gaps

**Example URLs:**
```
# NSW VIIRS NOAA-20 fires for 5 days starting 2020-01-01
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_NOAA20_SP/148,-38,154,-28/5/2020-01-01

# Global MODIS fires for most recent day
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/MODIS_NRT/world/1
```

### FIRMS Archive Download (Bulk)

For data older than 7 days, use the archive download tool:
- **URL**: https://firms.modaps.eosdis.nasa.gov/download/
- **Formats**: Shapefile (.shp), CSV, JSON
- **Process**: Submit request via web form -> receive email with download link
- **Temporal coverage**: Full archive (MODIS from Nov 2000, VIIRS from Jan 2012)
- **Country-level yearly CSVs** available for quick access

### FIRMS Daily Files (Direct Access)

- **URL**: `https://nrt3.modaps.eosdis.nasa.gov/archive/FIRMS/`
- **Requires**: Earthdata Login
- **Format**: Daily text/CSV files

### FIRMS CSV Column Definitions

**MODIS fields:**
`latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, type, daynight`

**VIIRS fields:**
`latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, confidence, version, bright_ti5, frp, daynight`

Key field descriptions:
- `brightness`/`bright_ti4`: Brightness temperature (Kelvin), channels 21/22 (MODIS) or I-4 (VIIRS)
- `confidence`: MODIS: 0-100% numeric; VIIRS: low/nominal/high categorical
- `frp`: Fire Radiative Power in megawatts
- `type` (MODIS only): 0=vegetation fire, 1=volcano, 2=static land source, 3=offshore
- `scan`/`track`: Pixel dimensions (grow toward scan edges)
- `daynight`: D or N

---

## 2. MCD64A1 Burned Area Product

### Via Google Earth Engine

```
Dataset ID: MODIS/061/MCD64A1
Type: ee.ImageCollection
Resolution: 500m
Cadence: Monthly
Coverage: Nov 2000 - present
```

**Bands:**
| Band | Range | Description |
|------|-------|-------------|
| `BurnDate` | 0-366 | Julian day of burning (0 = unburned) |
| `Uncertainty` | 0-100 | Burn day uncertainty |
| `QA` | bitmask | Quality assurance flags |
| `FirstDay` | 0-366 | First reliable detection day of year |
| `LastDay` | 0-366 | Last reliable detection day of year |

### Via AppEEARS

- **URL**: https://appeears.earthdatacloud.nasa.gov/
- **Product ID**: `MCD64A1.061`
- **API base**: `https://appeears.earthdatacloud.nasa.gov/api/`
- **Authentication**: Earthdata Login -> POST to `/login` -> Bearer token (1-hour expiry)
- **Workflow**: Submit area request -> poll status -> download when complete
- **Output formats**: GeoTIFF, NetCDF4, CSV (point samples)

### Via LP DAAC Direct Download

- **Product page**: https://lpdaac.usgs.gov/products/mcd64a1v061/
- **Data pool**: https://e4ftl01.cr.usgs.gov/MOTA/MCD64A1.061/
- **Format**: HDF-EOS5 in MODIS sinusoidal tile grid
- **Tile calculator**: https://modis-land.gsfc.nasa.gov/MODLAND_grid.html
- **NSW tiles**: approximately h30v12, h31v12, h30v11

### University of Maryland SFTP (Burned Area)

- **Server**: `sftp://fuoco.geog.umd.edu`
- **Formats**: HDF, GeoTIFF, Shapefile
- **Credentials**: In the MCD64A1 User Guide
- **User Guide**: https://lpdaac.usgs.gov/documents/1006/MCD64_User_Guide_V61.pdf

---

## 3. Google Earth Engine Datasets

### Registration
- **URL**: https://earthengine.google.com/
- **Requirement**: Google account, GEE project approval
- **Python API**: `pip install earthengine-api`

### Fire-Related Datasets in GEE

| Dataset ID | Description | Type |
|-----------|-------------|------|
| `FIRMS` | MODIS active fire 1km (raster) | ImageCollection |
| `MODIS/061/MCD64A1` | MODIS burned area 500m | ImageCollection |
| `JRC/GWIS/GlobFire/v2/DailyPerimeters` | GlobFire daily fire perimeters | FeatureCollection |
| `ECMWF/ERA5_LAND/DAILY_AGGR` | ERA5-Land daily aggregates | ImageCollection |
| `ECMWF/ERA5/DAILY` | ERA5 daily aggregates | ImageCollection |

### GEE Community Catalog (FIRMS Vector Data)

These provide FIRMS detections as vector point features (FeatureCollections):

**VIIRS vector data (2012-2021):**
```
projects/sat-io/open-datasets/VIIRS/VNP14IMGTDL_NRT_{YYYY}
```

**MODIS vector data (2000-2020):**
```
projects/sat-io/open-datasets/MODIS_MCD14DL/MCD14DL_{YYYY}
```

Fields match the standard FIRMS CSV columns.

---

## 4. GFED (Global Fire Emissions Database)

### GFED5.1

- **Website**: https://www.globalfiredata.org/data.html
- **Download**: SFTP access (no authentication required)
- **Format**: NetCDF4
- **Resolution**: 0.25 deg x 0.25 deg (2001-2022); 1.0 deg (1997-2000)
- **Cadence**: Monthly
- **Key files**:
  - `GFED5.1_monthly.zip` -- monthly burned area and trace gas emissions (1997-2022)
  - `GFED5.1ext_Beta/` -- extensions for 2023+
  - `GFED5.1ext_NRT_Beta/` -- current year, updated daily
  - `GFED5.1_code.zip` -- Python scripts for reading/processing

### GFED4.1 (older, at ORNL DAAC)

- **URL**: https://daac.ornl.gov/VEGETATION/guides/fire_emissions_v4_R1.html
- **Format**: HDF5 and NetCDF
- **Resolution**: 0.25 deg
- **Period**: 1997-2015

---

## 5. GWIS (Global Wildfire Information System)

### Data Portal
- **URL**: https://gwis.jrc.ec.europa.eu/applications/data-and-services
- **Country profiles**: https://gwis.jrc.ec.europa.eu/apps/country.profile/downloads

### GlobFire Data

- **Fire perimeters**: PostgreSQL dump files containing final fire perimeters
- **Daily evolution**: Separate dumps with daily burned area progression
- **Schema**: fire_id, initial_date, end_date, geometry (multi-polygon), linked daily records
- **PANGAEA archive**: https://doi.pangaea.de/10.1594/PANGAEA.943975 (2021 version)
- **Period**: 2001-2023

### GEE Access

```
Dataset ID: JRC/GWIS/GlobFire/v2/DailyPerimeters
Type: ee.FeatureCollection (table)
```

---

## 6. Copernicus CEMS Fire Danger Indices

### Registration
- **CDS Portal**: https://cds.climate.copernicus.eu/
- **Account**: Free ECMWF/Copernicus account
- **API key**: Available at https://cds.climate.copernicus.eu/how-to-api after login
- **Config file**: `~/.cdsapirc` with URL and key

### Dataset Details

- **Dataset name**: `cems-fire-historical-v1`
- **DOI**: 10.24381/cds.0e89c522
- **Resolution**: ~28 km (ERA5 native grid)
- **Period**: 1940 - present
- **Variables include**: Fire Weather Index (FWI), Fine Fuel Moisture Code (FFMC), Duff Moisture Code (DMC), Drought Code (DC), Initial Spread Index (ISI), Buildup Index (BUI), FFDI (McArthur Forest Fire Danger Index for Australia)
- **Format**: GRIB or NetCDF
- **API**: `pip install cdsapi`

### EWDS (Emergency Weather Data Store)

- **URL**: https://ewds.climate.copernicus.eu/datasets/cems-fire-historical-v1
- **Alternative API endpoint for fire-specific data**

---

## 7. Australian-Specific Data Sources

### SEED NSW Portal (Fire History)

- **Fire History Dataset**: https://datasets.seed.nsw.gov.au/dataset/fire-history-wildfires-and-prescribed-burns-1e8b6
- **Direct shapefile download**: https://datasets.seed.nsw.gov.au/dataset/1d05e145-80cb-4275-af9b-327a1536798d/resource/49075b91-8bcc-46e0-9cd9-2204aa61aeab/download/fire_npwsfirehistory.zip
- **Format**: Shapefile (WGS84)
- **Content**: Fire polygons with FireType (1=Wildfire, 2=Prescribed Burn), year, area
- **License**: Check metadata statement

### FESM 2019/20 (Black Summer)

- **URL**: https://datasets.seed.nsw.gov.au/dataset/fire-extent-and-severity-mapping-fesm-2019-20
- **Format**: GeoTIFF (.tif) and ERDAS Imagine (.img), 10m pixel
- **Content**: Fire extent and severity classes for all wildfires >10 ha, Jul 2019 - Jun 2020
- **Software**: Standard GIS (ArcGIS, QGIS)

### DEA Hotspots (Geoscience Australia)

- **URL**: https://hotspots.dea.ga.gov.au/
- **API**: WMS and WFS endpoints for integration
- **Update frequency**: Every 10 minutes
- **Overlays**: Sentinel-2 NRT, burnt areas, satellite passes
- **Product description**: https://hotspots.dea.ga.gov.au/cache/DEA+Hotspots+-+Product+Description+-+Version+2.0.pdf

### Data.NSW (RFS Fire History)

- **URL**: https://data.nsw.gov.au/data/dataset/1-27291ccb6b6a4fe1a32d3bf72a7280c9
- **Format**: Hosted feature layer
- **Fields**: fire_id, fire_name, ignition_date, area, source system (ICON, BRIMS, GUARDIAN)

### Bureau of Meteorology

- **Climate Data Online**: https://www.bom.gov.au/climate/data/ (temperature, humidity, wind, rainfall)
- **FFDI Climatology maps**: https://www.bom.gov.au/climate/maps/averages/ffdi/
- **FTP products (free)**: https://www.bom.gov.au/catalogue/anon-ftp.shtml
- **Station data**: 72-hour history in JSON/XML format
- **API**: HTTP POST with API key; contact webreg@bom.gov.au for access
- **Station directory**: https://www.bom.gov.au/climate/data/stations/

### NSW RFS Fire Weather Viewer

- **URL**: https://fireweather.aig.apps.rfs.nsw.gov.au/
- **Content**: Real-time fire weather observations and forecasts for NSW

---

## 8. ERA5 Reanalysis

### Via CDS API

- **Dataset**: `reanalysis-era5-single-levels` (hourly) or `reanalysis-era5-single-levels-timeseries`
- **Resolution**: 0.25 deg x 0.25 deg
- **Period**: 1940 - present (with ~5 day latency)
- **Relevant variables**: 2m temperature, 2m dewpoint, 10m wind, total precipitation, soil moisture

### Via Google Earth Engine

```
ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")  # ERA5-Land daily
ee.ImageCollection("ECMWF/ERA5/DAILY")              # ERA5 daily
```

---

## 9. Landsat Burned Area

### USGS Collection 2 Level-3 Burned Area

- **Product page**: https://www.usgs.gov/landsat-missions/landsat-collection-2-level-3-burned-area-science-product
- **Resolution**: 30 m
- **Sensors**: Landsat 4-9
- **Layers**: Burn classification, burn probability
- **Coverage**: Primarily CONUS; check availability for Australia
- **Access**: USGS EarthExplorer or GEE (community catalog)

### GEE Community Catalog

```
Landsat Burned Area: projects/sat-io/open-datasets/landsat-burned-area/
```

---

## 10. Sentinel-2 for Burn Scar Mapping

### Direct Access

- **Copernicus Open Access Hub**: https://scihub.copernicus.eu/
- **GEE**: `ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")`
- **Resolution**: 10-20m (depending on band)
- **Revisit**: 5 days (2 satellites)

### Key Bands for Fire Detection

| Band | Wavelength | Resolution | Use |
|------|-----------|------------|-----|
| B8A (NIR) | 865 nm | 20m | NBR numerator |
| B12 (SWIR) | 2190 nm | 20m | NBR denominator |
| B11 (SWIR) | 1610 nm | 20m | NBR2 |
| B4 (Red) | 665 nm | 10m | Visual, NDVI |
| B8 (NIR) | 842 nm | 10m | NDVI |

### Derived Indices

- **NBR** = (B8A - B12) / (B8A + B12) -- Normalized Burn Ratio
- **dNBR** = NBR_pre - NBR_post -- Differenced NBR (burn severity)
- **NBR2** = (B11 - B12) / (B11 + B12) -- alternative burn ratio
