# APIs, Data Access, and Ancillary Data

## 1. Satellite Data Sources

### 1.1 Himawari-8/9 AHI

**AWS S3 (primary for real-time):**
- Bucket: `noaa-himawari8` (us-east-1)
- Access: anonymous (no credentials needed)
- Path: `AHI-L1b-FLDK/{year}/{month}/{day}/{hour}{minute}/`
- Format: HSD (Himawari Standard Data) -- binary with header blocks
- Latency: ~5-10 minutes after observation
- Cadence: Full disk every 10 minutes, Japan/target regions every 2.5 minutes
- SNS notifications: `arn:aws:sns:us-east-1:123901341784:NewHimawari8Object` (SQS/Lambda only)

```bash
# List available files
aws s3 ls --no-sign-request s3://noaa-himawari8/AHI-L1b-FLDK/2026/03/17/0300/
```

**Python API:**
```bash
pip install himawari-api
```
- Repo: https://github.com/ghiggi/himawari_api
- Supports query, filter, download, and plotting of AHI data

**JMA direct dissemination:**
- HimawariCloud: https://www.data.jma.go.jp/mscweb/en/himawari89/cloud_service/cloud_service.html
- Requires registration; suitable for operational use in western Pacific

### 1.2 VIIRS (S-NPP, NOAA-20, NOAA-21)

**AWS S3:**
- VIIRS data available through NOAA Open Data Dissemination (NODD)
- SDR (sensor data records / L1b equivalent) available on AWS
- Access: anonymous via s3fs or boto3

```python
import s3fs
fs = s3fs.S3FileSystem(anon=True)
# List VIIRS aerosol files (example pattern)
files = fs.ls('noaa-jpss/NOAA20/VIIRS/...')
```

**NASA LANCE (Near Real-Time):**
- URL: https://lance.modaps.eosdis.nasa.gov/
- NRT VIIRS data within 3 hours of observation
- Requires NASA Earthdata login
- Products: VNP14IMG (375m fire), VJ114IMG (NOAA-20 fire)

**NOAA CLASS (Comprehensive Environmental Data Record Service):**
- URL: https://www.avl.class.noaa.gov/
- Bulk ordering for SDR and EDR products
- Higher latency but complete archive

**NASA FIRMS (Fire Information for Resource Management):**
- URL: https://firms.modaps.eosdis.nasa.gov/
- Pre-processed fire detections (not raw imagery)
- NRT with ~3 hour latency
- REST API available for fire point data
- Useful for validation, not for running your own detection

### 1.3 GOES-16/17/18 ABI

**AWS S3 (real-time):**
- Buckets: `noaa-goes16`, `noaa-goes17`, `noaa-goes18` (us-east-1)
- Access: anonymous
- Format: netCDF4
- Path: `ABI-L1b-RadF/{year}/{day_of_year}/{hour}/`
- Latency: minutes after observation
- Cadence: Full disk 10 min, CONUS 5 min, mesoscale 1 min

```python
import s3fs
fs = s3fs.S3FileSystem(anon=True)
# List GOES-16 ABI L1b radiance files for a specific hour
files = fs.ls('noaa-goes16/ABI-L1b-RadF/2026/076/03/')
```

**SNS notifications** for new data available on each bucket.

**Fire products** (ABI L2 FDC -- Fire/Hot Spot Characterization) also on AWS:
```
noaa-goes16/ABI-L2-FDCF/{year}/{day_of_year}/{hour}/
```

### 1.4 Landsat 8/9

**USGS Earth Explorer:**
- URL: https://earthexplorer.usgs.gov/
- Collection 2 Level-1 and Level-2 products

**Google Cloud Storage:**
- Bucket: `gcp-public-data-landsat`
- Format: GeoTIFF with MTL.txt metadata

**AWS S3:**
- Bucket: `usgs-landsat` (us-west-2)
- Requires AWS credentials for some products

**Microsoft Planetary Computer:**
- STAC API: https://planetarycomputer.microsoft.com/api/stac/v1
- Cloud-optimized GeoTIFFs (COGs)

### 1.5 Sentinel-2

**Copernicus Data Space Ecosystem (CDSE):**
- URL: https://dataspace.copernicus.eu/
- STAC API for search and download
- Both L1C and L2A products

**AWS S3:**
- Bucket: `sentinel-s2-l1c`, `sentinel-s2-l2a` (eu-central-1)
- Requester pays

**Microsoft Planetary Computer:**
- STAC API with free access
- COG format, efficient partial reads

---

## 2. Processing Tools and Libraries

### 2.1 Core Python Libraries

| Library | Purpose | Install |
|---------|---------|---------|
| **satpy** | Read/calibrate/resample multi-sensor satellite data | `pip install satpy` |
| **pyresample** | Geospatial image resampling (swath to grid, grid to grid) | `pip install pyresample` |
| **pyspectral** | Spectral calculations (radiance/BT conversion, RSR functions) | `pip install pyspectral` |
| **pyorbital** | Satellite orbit calculations, sun angles | `pip install pyorbital` |
| **rasterio** | Read/write GeoTIFF, reprojection, masking | `pip install rasterio` |
| **xarray** | N-dimensional labeled arrays (good for netCDF data) | `pip install xarray` |
| **netCDF4** | Read netCDF4 files (GOES ABI format) | `pip install netCDF4` |
| **h5py** | Read HDF5 files (VIIRS SDR format) | `pip install h5py` |
| **s2cloudless** | ML cloud detection for Sentinel-2 | `pip install s2cloudless` |
| **s3fs** | S3 filesystem interface for anonymous AWS access | `pip install s3fs` |
| **pykdtree** | Fast KD-tree for nearest-neighbor resampling | `pip install pykdtree` |

### 2.2 Satpy Reader Names

| Sensor/Format | Satpy reader name | File pattern |
|---------------|-------------------|--------------|
| Himawari AHI HSD | `ahi_hsd` | `HS_H08_*_FLDK_*.DAT` |
| VIIRS SDR (HDF5) | `viirs_sdr` | `SVI*.h5`, `GITCO*.h5` |
| VIIRS L1b (netCDF) | `viirs_l1b` | `VNP02IMG.*.nc` |
| GOES ABI L1b | `abi_l1b` | `OR_ABI-L1b-Rad*.nc` |
| Landsat L1 | `generic_image` | GeoTIFF (use rasterio instead) |
| Sentinel-2 L1C | `msi_safe` | `S2*_MSIL1C_*.SAFE` |

### 2.3 Standalone Processing Systems

**CSPP (Community Satellite Processing Package):**
- URL: https://cimss.ssec.wisc.edu/cspp/
- End-to-end processing for direct broadcast VIIRS data
- Produces SDR from raw data record (RDR)
- Includes fire detection algorithms
- Used by direct-broadcast ground stations

**Geo2Grid:**
- URL: https://www.ssec.wisc.edu/software/geo2grid/
- Converts geostationary satellite data (AHI HSD, ABI L1b) to gridded GeoTIFF
- Handles calibration and remapping

---

## 3. Ancillary Data

### 3.1 Digital Elevation Models (DEM)

Needed for: terrain correction, orthorectification, slope/aspect for fire behavior.

**Copernicus DEM GLO-30 (recommended):**
- Resolution: 30m global
- Format: Cloud-Optimized GeoTIFF
- Access: Free, no registration
- AWS: `s3://copernicus-dem-30m/` (eu-central-1, requester pays)
- OpenTopography: https://portal.opentopography.org/raster?opentopoID=OTSDEM.032021.4326.3

**SRTM (legacy):**
- 30m (SRTM1) and 90m (SRTM3)
- Coverage: 60N to 56S
- Available from USGS EarthExplorer

**For fire detection:** DEM is not required for the detection itself but useful for:
- Removing terrain shadow false positives (shadows cause cold BT anomalies)
- Fire spread modeling (slope affects rate of spread)
- Precise geolocation of detected fires

### 3.2 Land/Water Masks

**MOD44W v6.1 (MODIS Land Water Mask):**
- Resolution: 250m global
- Annual product (2000-present)
- Format: HDF4 in MODIS sinusoidal grid
- Source: https://lpdaac.usgs.gov/products/mod44wv061/
- Also available in Google Earth Engine

**Global Surface Water (JRC):**
- Resolution: 30m
- Based on Landsat archive
- Includes water occurrence frequency and seasonality
- Source: https://global-surface-water.appspot.com/

**For fire detection:** A static land/water mask at 250m-1km resolution is sufficient. Download once, reproject to your working grid, keep in memory. Water bodies don't change frequently enough to warrant dynamic updates for fire detection. Exception: seasonal flooding in some regions.

### 3.3 Land Cover

**MODIS Land Cover (MCD12Q1):**
- 500m annual
- IGBP classification
- Useful for: fire likelihood priors, fuel type estimation

**ESA WorldCover:**
- 10m global land cover
- Source: https://esa-worldcover.org/

### 3.4 Cloud Mask Products (Pre-computed)

If you don't want to compute cloud masks yourself:

**VIIRS Cloud Mask (VCM / CLDMSK_L2_VIIRS):**
- Included in VIIRS environmental data records (EDR)
- Available from NASA LANCE NRT

**GOES ABI Cloud Products:**
- ACM (ABI Cloud Mask) available as L2 product on AWS
- Path: `noaa-goes16/ABI-L2-ACMF/{year}/{day}/{hour}/`

**Himawari Cloud Products:**
- CLAVR-x cloud mask available from NCI (Australian National Computational Infrastructure)
- Path: https://opus.nci.org.au for Himawari-AHI Cloud Mask (CMA)

### 3.5 Atmospheric Profiles (If Needed)

If you do need atmospheric correction:

**ERA5 reanalysis:**
- Temperature, humidity, pressure profiles on 37 pressure levels
- ~30km horizontal resolution
- ~5 day latency for final product, but ERA5T (preliminary) available within days
- Source: https://cds.climate.copernicus.eu/

**GFS (Global Forecast System):**
- NWP model output
- Near real-time availability
- Coarser than ERA5 but available with minimal latency
- Source: https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast

**MERRA-2:**
- NASA reanalysis
- Source: https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/

### 3.6 Fire Reference Data (Validation)

**NASA FIRMS Active Fire Archive:**
- Historical MODIS (2000-present) and VIIRS (2012-present) fire detections
- Source: https://firms.modaps.eosdis.nasa.gov/download/

**NIFC Wildfire Perimeters (US):**
- Source: https://data-nifc.opendata.arcgis.com/

**Australian Government Hotspots:**
- Source: https://hotspots.dea.ga.gov.au/
- Sentinel/Himawari-derived fire products for Australia

---

## 4. Data Format Quick Reference

| Format | Sensor | Python reader | Notes |
|--------|--------|--------------|-------|
| HSD | Himawari AHI | satpy (`ahi_hsd`) | Binary with 12 header blocks, 10 segments per band |
| HDF5 | VIIRS SDR | satpy (`viirs_sdr`), h5py | Multiple granules per file possible |
| netCDF4 | GOES ABI, VIIRS L1b | xarray, netCDF4, satpy | Self-describing with Planck constants included |
| GeoTIFF | Landsat, DEM, masks | rasterio | With CRS and transform metadata |
| SAFE/JP2 | Sentinel-2 | satpy (`msi_safe`), rasterio | JPEG2000 compressed tiles in directory structure |
| HDF4 | MODIS, MOD44W | pyhdf, satpy | Legacy format |

## 5. Recommended Data Pipeline for XPrize

For a real-time wildfire detection system targeting Australia:

1. **Primary detection:** Himawari-8/9 AHI from `noaa-himawari8` S3 bucket (10-min cadence, covers all of Australia)
2. **Confirmation:** VIIRS from NASA LANCE NRT (375m resolution, ~3hr latency)
3. **Ancillary:** Pre-download and cache Copernicus DEM GLO-30 and MOD44W land/water mask for Australia coverage area
4. **Cloud masking:** Process AHI cloud mask in-pipeline using fast spectral tests (see algorithms.md)
5. **Monitoring GOES:** Not needed for Australia coverage (GOES covers Americas)
