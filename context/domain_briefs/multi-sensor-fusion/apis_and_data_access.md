# APIs and Data Access for Multi-Sensor Fire Detection

## 1. FIRMS API (Primary Cross-Check Source)

NASA FIRMS provides near-real-time active fire data from MODIS, VIIRS, and Landsat.

### API Overview

| Property | Value |
|----------|-------|
| Base URL | `https://firms.modaps.eosdis.nasa.gov/api/` |
| Authentication | MAP_KEY (free registration) |
| Rate limit | 5,000 transactions per 10-minute interval |
| Latency | ~3 hours globally; real-time for US/Canada |
| Formats | CSV (primary), KML (footprints) |

### Obtaining a MAP_KEY

Register at `https://firms.modaps.eosdis.nasa.gov/api/map_key/` -- free, instant, provides a 32-character alphanumeric key.

### Area API (Primary Endpoint)

**URL pattern:**
```
GET /api/area/csv/{MAP_KEY}/{SOURCE}/{WEST,SOUTH,EAST,NORTH}/{DAY_RANGE}
GET /api/area/csv/{MAP_KEY}/{SOURCE}/{WEST,SOUTH,EAST,NORTH}/{DAY_RANGE}/{DATE}
```

**Parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `MAP_KEY` | Your API key | `08bb7df1150969505da0ee309fa52ef2` |
| `SOURCE` | Sensor/processing level | `VIIRS_SNPP_NRT` |
| `WEST,SOUTH,EAST,NORTH` | Bounding box (decimal degrees) | `148,-37,154,-28` (NSW) |
| `DAY_RANGE` | Number of days (1-5) | `1` |
| `DATE` | Specific date (optional) | `2026-04-15` |

**Available data sources:**

| Source ID | Sensor | Type | Notes |
|-----------|--------|------|-------|
| `VIIRS_SNPP_NRT` | VIIRS S-NPP | Near Real-Time | 375 m, primary |
| `VIIRS_SNPP_SP` | VIIRS S-NPP | Standard Processing | Higher quality, ~2 month lag |
| `VIIRS_NOAA20_NRT` | VIIRS NOAA-20 | Near Real-Time | 375 m |
| `VIIRS_NOAA21_NRT` | VIIRS NOAA-21 | Near Real-Time | 375 m |
| `MODIS_NRT` | MODIS (Terra+Aqua) | Near Real-Time | 1 km |
| `MODIS_SP` | MODIS | Standard Processing | Higher quality |
| `LANDSAT_NRT` | Landsat 8/9 OLI | Near Real-Time | 30 m, US/Canada only |

### Python Example: Querying FIRMS

```python
import pandas as pd
import requests
from datetime import datetime

FIRMS_MAP_KEY = "YOUR_MAP_KEY_HERE"
FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

def query_firms_area(source: str, bbox: tuple, days: int = 1,
                      date: str = None) -> pd.DataFrame:
    """Query FIRMS Area API for fire detections.

    Args:
        source: e.g. 'VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'MODIS_NRT'
        bbox: (west, south, east, north) in decimal degrees
        days: 1-5 day range
        date: optional YYYY-MM-DD string for specific date

    Returns:
        DataFrame with fire detections
    """
    west, south, east, north = bbox
    coords = f"{west},{south},{east},{north}"

    if date:
        url = f"{FIRMS_BASE_URL}/{FIRMS_MAP_KEY}/{source}/{coords}/{days}/{date}"
    else:
        url = f"{FIRMS_BASE_URL}/{FIRMS_MAP_KEY}/{source}/{coords}/{days}"

    df = pd.read_csv(url)
    return df

# Example: Query VIIRS S-NPP NRT for NSW, last 2 days
NSW_BBOX = (148.0, -37.0, 154.0, -28.0)
df_viirs = query_firms_area('VIIRS_SNPP_NRT', NSW_BBOX, days=2)

# Combine multiple VIIRS sources
def query_all_viirs_nrt(bbox, days=1, date=None):
    """Query all VIIRS NRT sources and concatenate."""
    sources = ['VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'VIIRS_NOAA21_NRT']
    frames = []
    for src in sources:
        try:
            df = query_firms_area(src, bbox, days, date)
            df['source'] = src
            frames.append(df)
        except Exception as e:
            print(f"Warning: {src} query failed: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
```

### FIRMS Response Fields

**VIIRS 375m fields:**

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `latitude` | float | degrees | Center of 375 m fire pixel |
| `longitude` | float | degrees | Center of 375 m fire pixel |
| `bright_ti4` | float | Kelvin | I-4 channel (3.9 um) brightness temperature |
| `bright_ti5` | float | Kelvin | I-5 channel (11.0 um) brightness temperature |
| `scan` | float | meters | Pixel dimension along scan |
| `track` | float | meters | Pixel dimension along track |
| `acq_date` | str | YYYY-MM-DD | Acquisition date |
| `acq_time` | str | HHMM (UTC) | Acquisition time |
| `satellite` | str | -- | N (S-NPP), N20 (NOAA-20), N21 (NOAA-21) |
| `confidence` | str | -- | low, nominal, high |
| `version` | str | -- | Collection + processing level |
| `frp` | float | MW | Fire Radiative Power |
| `daynight` | str | -- | D or N |

**MODIS fields (differences from VIIRS):**

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `brightness` | float | Kelvin | Channel 21/22 (3.9 um) |
| `bright_t31` | float | Kelvin | Channel 31 (11.0 um) |
| `confidence` | int | 0-100 | Numeric confidence percentage |
| `type` | int | -- | 0=vegetation, 1=volcano, 2=static/industrial, 3=offshore |
| `satellite` | str | -- | T (Terra), A (Aqua) |

### FIRMS Data Availability API

Check which dates have data before querying:

```python
def check_firms_availability():
    """Check date ranges for NRT and SP data."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{FIRMS_MAP_KEY}/all"
    return pd.read_csv(url)
```

### FIRMS Static Thermal Anomaly (STA) Mask

FIRMS provides pre-computed masks of persistent thermal sources:

- **STA-Mask**: Polygon layer of persistent thermal activity areas, derived from 2023 cumulative detections on a 400 m grid (cells with 5+ detections/year)
- **STA-Detections**: Real-time flagging of detections matching the STA mask
- **Sources**: Cross-referenced with WRI power plant database, volcanic databases

Download from: `https://firms.modaps.eosdis.nasa.gov/` (Layers section)

```python
import geopandas as gpd

def load_sta_mask(sta_shapefile_path: str) -> gpd.GeoDataFrame:
    """Load FIRMS Static Thermal Anomaly mask for false positive filtering."""
    sta = gpd.read_file(sta_shapefile_path)
    return sta

def check_against_sta(detection_lat, detection_lon, sta_gdf):
    """Check if a detection falls within a known static thermal anomaly area."""
    from shapely.geometry import Point
    point = Point(detection_lon, detection_lat)
    return sta_gdf.contains(point).any()
```

## 2. Himawari AHI Data Access

### Data Sources

| Source | URL | Format | Latency | Notes |
|--------|-----|--------|---------|-------|
| AWS Archive | `s3://noaa-himawari8/` | HSD (Himawari Standard Data) | ~30 min | Free, full disk, July 2015+ |
| JMA HimawariCloud | `https://www.data.jma.go.jp/mscweb/en/himawari89/cloud_service/` | HSD | ~15 min | Requires NMHS registration |
| JAXA FTP | Via `ftp-himawari8-hsd` Python package | HSD | ~30 min | Research access |

### Python Libraries for AHI

```python
# Install: pip install himawari_api satpy

# Option 1: himawari_api for download management
import himawari_api

# Option 2: satpy for reading and processing HSD files
from satpy import Scene

def load_ahi_fire_bands(hsd_file_paths: list) -> dict:
    """Load AHI bands relevant to fire detection using Satpy.

    Key bands for fire detection:
      B07 (3.9 um) - MIR, primary fire detection
      B14 (11.2 um) - TIR, background temperature
      B15 (12.4 um) - TIR, split window
      B03 (0.64 um) - VIS, cloud masking (daytime)
    """
    scene = Scene(filenames=hsd_file_paths, reader='ahi_hsd')
    scene.load(['B07', 'B14', 'B15', 'B03'])

    return {
        'bt_mir': scene['B07'].values,     # Band 7: 3.9 um brightness temp
        'bt_tir1': scene['B14'].values,    # Band 14: 11.2 um brightness temp
        'bt_tir2': scene['B15'].values,    # Band 15: 12.4 um brightness temp
        'ref_vis': scene['B03'].values,    # Band 3: 0.64 um reflectance
        'area_def': scene['B07'].attrs['area'],  # Projection/geolocation
    }
```

### AHI Band Reference (Fire-Relevant)

| Band | Wavelength (um) | Resolution | Use |
|------|----------------|------------|-----|
| B03 | 0.64 | 500 m | Cloud masking, daytime |
| B04 | 0.86 | 1 km | Cloud masking, vegetation |
| B07 | 3.9 | 2 km | **Primary fire detection (MIR)** |
| B13 | 10.4 | 2 km | Background temperature |
| B14 | 11.2 | 2 km | **Background temperature / BTD** |
| B15 | 12.4 | 2 km | Split window, cloud masking |

### AHI Scan Timing

| Mode | Interval | Coverage |
|------|----------|----------|
| Full disk | 10 min | Entire visible hemisphere |
| Japan area | 2.5 min | Target area scan |
| Landmark | 0.5 min | 1000x1000 km mesoscale |

## 3. Ancillary Data for False Positive Filtering

### Land Cover / Land Use

| Dataset | Resolution | Source | Use |
|---------|-----------|--------|-----|
| ESA WorldCover | 10 m | Sentinel-1/2 derived | Identify vegetation vs bare soil vs urban |
| MODIS MCD12Q1 | 500 m | Annual, IGBP classes | Broad land cover classification |
| LANDFIRE | 30 m | US only | Vegetation type, fuel model |
| Copernicus Land Cover | 100 m | Global | Land cover classes, forest type |

```python
def load_landcover_for_bbox(bbox, dataset='worldcover'):
    """Load land cover data for false positive filtering.

    Returns array where classes indicate fire-susceptible vegetation.
    """
    # WorldCover classes relevant to fire:
    # 10 = Tree cover
    # 20 = Shrubland
    # 30 = Grassland
    # 40 = Cropland
    # 50 = Built-up  (-> potential industrial FP)
    # 60 = Bare/sparse vegetation (-> potential hot ground FP)
    # 80 = Permanent water (-> potential sun glint FP)
    pass  # Implementation depends on data access method
```

### Digital Elevation Model (DEM)

Used for terrain correction of satellite geolocation and view angle calculations:

| Dataset | Resolution | Source |
|---------|-----------|--------|
| Copernicus DEM | 30 m | ESA OpenSearch API |
| SRTM | 30 m | USGS EarthExplorer |
| NASADEM | 30 m | NASA LP DAAC |

### Solar Geometry / Glint Angle

```python
from datetime import datetime
import numpy as np

def compute_glint_angle(lat, lon, timestamp: datetime,
                         sat_lon=140.7, sat_lat=0.0):
    """Compute specular reflection (glint) angle between sun and sensor.

    For geostationary satellites, sensor position is fixed.
    Glint angle < 10 degrees -> high risk of sun glint false positive.
    """
    # Solar position (simplified)
    day_of_year = timestamp.timetuple().tm_yday
    hour_utc = timestamp.hour + timestamp.minute / 60.0

    # Solar declination
    solar_declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365))

    # Hour angle
    solar_noon_lon = -15.0 * (hour_utc - 12.0)  # degrees
    hour_angle = lon - solar_noon_lon

    # Solar zenith and azimuth
    lat_r = np.radians(lat)
    dec_r = np.radians(solar_declination)
    ha_r = np.radians(hour_angle)

    cos_sza = (np.sin(lat_r) * np.sin(dec_r) +
               np.cos(lat_r) * np.cos(dec_r) * np.cos(ha_r))
    sza = np.degrees(np.arccos(np.clip(cos_sza, -1, 1)))

    # Satellite zenith angle (for geostationary)
    # VZA from Himawari at NSW (~33S) with sub-satellite point at 140.7E, 0N
    dlon = np.radians(lon - sat_lon)
    dlat = np.radians(lat - sat_lat)
    # Simplified VZA calculation
    cos_vza = np.cos(dlat) * np.cos(dlon)
    vza = np.degrees(np.arccos(np.clip(cos_vza, -1, 1)))

    # Glint angle approximation (angle between specular reflection and sensor)
    # This is simplified; production code should use full 3D geometry
    glint_angle = abs(sza - vza)  # First-order approximation

    return {
        'solar_zenith_angle': sza,
        'satellite_view_zenith_angle': vza,
        'glint_angle': glint_angle,
        'is_daytime': sza < 85.0,
        'high_glint_risk': glint_angle < 10.0,
    }
```

### Volcano Database

| Database | Coverage | Access |
|----------|----------|--------|
| Smithsonian GVP | Global, ~1,400 Holocene volcanoes | `https://volcano.si.edu/` API/download |
| MODVOLC | Global thermal alerts from MODIS | `http://modis.higp.hawaii.edu/` |

### Industrial Heat Source Databases

| Source | Coverage | Notes |
|--------|----------|-------|
| WRI Global Power Plant DB | Global, ~35,000 plants | CSV download, includes location + fuel type |
| FIRMS STA Mask | Global | Derived from cumulative fire detections |
| DMSP-OLS Stable Night Lights | Global | Persistent lights = urban/industrial areas |

### Fire Weather Index

| Source | Coverage | Resolution | Access |
|--------|----------|-----------|--------|
| GWIS Fire Danger Forecast | Global | ~10 km | `https://gwis.jrc.ec.europa.eu/` |
| BOM Fire Weather Forecast | Australia | State-level | Bureau of Meteorology API |
| CAMS GFAS | Global | ~80 km | Copernicus API |

## 4. GWIS API

The Global Wildfire Information System provides complementary fire information:

| Endpoint | Data | Latency |
|----------|------|---------|
| Active fire map | MODIS + VIIRS detections | ~3-6 hours |
| Fire danger forecast | FWI up to 10 days | Daily |
| Burnt area | Near-real-time perimeters | ~1-3 days |
| Emissions | CAMS GFAS fire emissions | ~1 day |

Access: `https://gwis.jrc.ec.europa.eu/applications/data-and-services`

## 5. Sentinel-2 and Landsat Access for High-Res Confirmation

### Sentinel Hub / Copernicus Data Space

```python
# For Sentinel-2 SWIR band access (B11: 1.6um, B12: 2.2um at 20m)
# Use Copernicus Data Space Ecosystem API
# Register at: https://dataspace.copernicus.eu/

# Key bands for fire detection:
# B04 (Red, 10m) - burn scar
# B08 (NIR, 10m) - vegetation state
# B11 (SWIR, 20m) - fire/burn detection
# B12 (SWIR, 20m) - fire/burn detection
```

### Landsat via USGS

Landsat fire data is now integrated into FIRMS for US/Canada via `LANDSAT_NRT` source.

For global Landsat thermal data:
- USGS EarthExplorer for archive data
- Landsat Level-2 Surface Temperature product (Band 10, 100 m thermal at 30 m resampled)

## 6. Data Latency Summary for Pipeline Design

| Data Source | Typical Latency | Best Case | Pipeline Stage |
|-------------|----------------|-----------|----------------|
| Himawari AHI (AWS) | 20-40 min | ~15 min | Stage 1: Trigger |
| Himawari AHI (HimawariCloud) | 10-20 min | ~10 min | Stage 1: Trigger |
| FIRMS VIIRS NRT | 2-4 hours | ~2 hours | Stage 3: Confirm |
| FIRMS MODIS NRT | 2-4 hours | ~2 hours | Stage 3: Confirm |
| VIIRS direct (LANCE) | 1-3 hours | ~1 hour | Stage 3: Confirm |
| Sentinel-2 | 2-12 hours | ~2 hours | Stage 3: High-res confirm |
| Landsat | 4-24 hours | ~4 hours | Stage 3: High-res confirm |
| GWIS | 3-6 hours | ~3 hours | Cross-check |
