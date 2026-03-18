# APIs and Data Access for Satellite Fire Detection

## STAC API — Copernicus Data Space

The Copernicus Data Space Ecosystem provides a STAC-compliant catalog for Sentinel
data (Sentinel-2, Sentinel-3, etc.).

**Base URL**: `https://catalogue.dataspace.copernicus.eu/stac`

**Authentication**: Requires an account at `https://dataspace.copernicus.eu`. Access
tokens obtained via OAuth2 from `https://identity.dataspace.copernicus.eu`.

**Collections of interest**:
- `sentinel-2-l2a` — Sentinel-2 L2A (atmospherically corrected, bottom-of-atmosphere)
- `sentinel-2-l1c` — Sentinel-2 L1C (top-of-atmosphere)
- `sentinel-3-slstr-l1b` — Sentinel-3 SLSTR Level-1B (thermal bands)

**Search example with pystac-client**:
```python
from pystac_client import Client

catalog = Client.open("https://catalogue.dataspace.copernicus.eu/stac")

search = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=[148, -37, 154, -28],             # NSW bounding box
    datetime="2026-04-01/2026-04-15",
    query={"eo:cloud_cover": {"lt": 50}},
    max_items=100,
)

items = list(search.items())
for item in items:
    print(item.id, item.datetime, item.properties.get("eo:cloud_cover"))
    # Access assets
    for asset_key, asset in item.assets.items():
        print(f"  {asset_key}: {asset.href}")
```

**Download**: Assets are accessible via signed URLs. Use the S3 endpoint or direct
HTTPS download with authentication headers.

## FIRMS API (Fire Information for Resource Management System)

NASA FIRMS provides near-real-time fire/hotspot data from VIIRS and MODIS.

**Base URL**: `https://firms.modaps.eosdis.nasa.gov`

**API Key**: Register at https://firms.modaps.eosdis.nasa.gov/api/area/ to get a
MAP_KEY. Free tier allows 10 requests/minute.

**Endpoints**:

```
# Active fires for a bounding box (CSV)
GET /api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/{west},{south},{east},{north}/{num_days}

# Active fires for a country
GET /api/country/csv/{MAP_KEY}/VIIRS_SNPP_NRT/AUS/{num_days}

# Supported sources: VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT, MODIS_NRT
```

**Response format (CSV columns)**:
`latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite,
instrument, confidence, version, bright_ti5, frp, daynight`

**Python usage**:
```python
import requests
import pandas as pd
from io import StringIO

MAP_KEY = "your_key_here"
url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/148,-37,154,-28/1"
response = requests.get(url)
df = pd.read_csv(StringIO(response.text))
```

**Limitations**: NRT data has ~3-4 hour latency. Not suitable as the primary detection
source, but valuable for validation and cross-referencing.

## AWS Open Data — GOES ABI

GOES-16/17/18 data is freely available on AWS S3 (no authentication needed).

**Bucket**: `s3://noaa-goes16` (GOES-East), `s3://noaa-goes18` (GOES-West)

**Path pattern**:
```
s3://noaa-goes16/ABI-L1b-RadF/{year}/{day_of_year}/{hour}/
    OR_ABI-L1b-RadF-M6C{band:02d}_G16_s{start}_e{end}_c{created}.nc
```

- `RadF` = Full Disk, `RadC` = CONUS, `RadM` = Mesoscale
- `M6` = Mode 6 (10-min full disk), `M3` = Mode 3 (15-min full disk, 5-min CONUS)
- `C07` = Band 7 (3.9 um shortwave IR), `C14` = Band 14 (11.2 um), `C15` = Band 15 (12.3 um)

**Access (unsigned)**:
```python
import s3fs
import xarray as xr

fs = s3fs.S3FileSystem(anon=True)
files = fs.glob('noaa-goes16/ABI-L1b-RadF/2026/091/00/OR_ABI-L1b-RadF-M6C07_*.nc')
with fs.open(files[0]) as f:
    ds = xr.open_dataset(f)
```

**Real-time subscription**: Use AWS SNS topic `arn:aws:sns:us-east-1:123456789012:NewGOES16Object`
to receive notifications when new files appear. More practical: poll the S3 bucket
with a short interval (GOES full-disk every 10 minutes).

## AWS Open Data — Himawari

**Bucket**: `s3://noaa-himawari8` (also serves Himawari-9 data)

**Path pattern**:
```
s3://noaa-himawari8/AHI-L1b-FLDK/{year}/{month}/{day}/{hour}{minute}/
    HS_H09_{date}_{time}_B{band:02d}_FLDK_R{resolution}_S{segment:02d}10.DAT
```

- 10 segments per band per full-disk scan (S0110 through S1010)
- R20 = 2km resolution, R05 = 0.5km (visible bands)
- Full disk scan every 10 minutes

**HSD format structure** (binary):
Each .DAT file contains a fixed-size header block followed by raw pixel data.
The header includes calibration coefficients, navigation parameters, and observation
time. Use satpy's `ahi_hsd` reader rather than parsing manually.

## VIIRS SDR Data

**Source**: NOAA CLASS (https://www.class.noaa.gov) or direct broadcast reception.

**AWS bucket**: `s3://noaa-nesdis-n20-pds` (NOAA-20), similar for SNPP and NOAA-21.

**File types**:
| Prefix | Content | Resolution |
|--------|---------|------------|
| `SVI01-SVI05` | I-band SDR (radiance/BT) | 375 m |
| `SVM01-SVM16` | M-band SDR | 750 m |
| `GITCO` | I-band terrain-corrected geolocation | 375 m |
| `GMTCO` | M-band terrain-corrected geolocation | 750 m |

**Key variables inside HDF5** (I-band example):
```
/All_Data/VIIRS-I4-SDR_All/BrightnessTemperature     # uint16, scale/offset encoded
/All_Data/VIIRS-I4-SDR_All/BrightnessTemperatureFactors  # [scale, offset]
/All_Data/VIIRS-I4-SDR_All/QF1_VIIRSI4SDR            # quality flags
```

**Geolocation file** (`GITCO`):
```
/All_Data/VIIRS-IMG-GEO-TC_All/Latitude    # float32 [nscans*32, 6400]
/All_Data/VIIRS-IMG-GEO-TC_All/Longitude   # float32
/All_Data/VIIRS-IMG-GEO-TC_All/SolarZenithAngle
/All_Data/VIIRS-IMG-GEO-TC_All/SatelliteZenithAngle
```

## GOES ABI NetCDF4 Variable Reference

**Radiance file variables**:
```
Rad                    # int16, scaled radiance (apply scale_factor and add_offset)
DQF                    # uint8, data quality flags (0 = good)
x                      # float32, E/W scan angle in radians (fixed grid)
y                      # float32, N/S scan angle in radians (fixed grid)
goes_imager_projection # container for CRS attributes
    .perspective_point_height
    .semi_major_axis
    .semi_minor_axis
    .longitude_of_projection_origin
    .sweep_angle_axis
planck_fk1             # first Planck constant (W m^-2 sr^-1 um^4)
planck_fk2             # second Planck constant (K)
bc1                    # band correction 1 (offset)
bc2                    # band correction 2 (slope)
```

**Brightness temperature from radiance**:
```
BT = (planck_fk2 / ln(planck_fk1 / Rad + 1) - bc1) / bc2
```

## Landsat on AWS

**Bucket**: `s3://usgs-landsat` (Collection 2)

**Path pattern**:
```
s3://usgs-landsat/collection02/level-1/standard/oli-tirs/{path_prefix}/{path}/{row}/
    LC08_L1TP_{path}{row}_{date}_{processing_date}_02_T1/
        LC08_L1TP_{path}{row}_{date}_*_B10.TIF   # Thermal band 10
        LC08_L1TP_{path}{row}_{date}_*_MTL.txt    # Metadata
```

**Band numbers** (Landsat 8/9 OLI-TIRS):
| Band | Wavelength (um) | Resolution | Fire Use |
|------|----------------|------------|----------|
| B5   | 0.85-0.88 (NIR) | 30 m | Contextual |
| B6   | 1.57-1.65 (SWIR1) | 30 m | Fire detection |
| B7   | 2.11-2.29 (SWIR2) | 30 m | Fire detection |
| B10  | 10.6-11.2 (TIR1) | 100 m (resampled to 30 m) | Background temp |

**MTL.txt** contains `RADIANCE_MULT_BAND_10`, `RADIANCE_ADD_BAND_10`, `K1_CONSTANT_BAND_10`,
`K2_CONSTANT_BAND_10` for thermal calibration.

## Sentinel-2 SAFE Format

**Directory structure**:
```
S2B_MSIL2A_20260401T002709_N0500_R016_T56HLH_20260401T014523.SAFE/
    GRANULE/
        L2A_T56HLH_A000001_20260401T002709/
            IMG_DATA/
                R10m/  # 10m bands (B02, B03, B04, B08)
                R20m/  # 20m bands (B05, B06, B07, B8A, B11, B12, SCL)
                R60m/  # 60m bands (B01, B09)
            QI_DATA/
                MSK_CLDPRB_20m.jp2  # Cloud probability mask
```

**Bands for fire detection**:
| Band | Wavelength (um) | Resolution | Purpose |
|------|----------------|------------|---------|
| B12  | 2.19 (SWIR)    | 20 m       | Active fire detection |
| B11  | 1.61 (SWIR)    | 20 m       | Fire confirmation |
| B8A  | 0.865 (NIR)    | 20 m       | Vegetation/contextual |
| SCL  | Scene class    | 20 m       | Cloud/shadow mask |

**Tile naming**: `T{UTM_zone}{latitude_band}{grid_square}` — e.g., `T56HLH` is
UTM zone 56, latitude band H, grid square LH. NSW is primarily covered by tiles
in zones 55 and 56.

## Sentinel-3 SLSTR

**Source**: Copernicus Data Space (STAC collection `sentinel-3-slstr-l1b`).

**Key thermal bands**:
| Channel | Wavelength | Resolution | Notes |
|---------|-----------|------------|-------|
| S7      | 3.74 um   | 1 km       | SWIR, primary fire detection |
| S8      | 10.85 um  | 1 km       | TIR, background temperature |
| S9      | 12.0 um   | 1 km       | TIR, split window |
| F1      | 3.74 um   | 1 km       | Fire channel (wider dynamic range) |
| F2      | 10.85 um  | 1 km       | Fire channel (wider dynamic range) |

The F1/F2 channels have a higher saturation temperature than S7/S8, specifically
designed for fire detection (saturate at ~500 K vs ~340 K for standard channels).

**Access via satpy**:
```python
from satpy import Scene
scn = Scene(reader='slstr_l1b', filenames=slstr_files)
scn.load(['S7_BT', 'F1_BT'])
```
