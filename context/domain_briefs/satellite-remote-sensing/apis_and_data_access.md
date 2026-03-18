# APIs and Data Access for Satellite Fire Detection

## Himawari-9 AHI

### AWS Open Data (NODD) -- Lowest Latency for Programmatic Access

JMA produces the data; NOAA has rights to distribute freely. Data is mirrored to AWS S3.

**S3 Buckets:**

| Dataset | Bucket | Region | ARN |
|---------|--------|--------|-----|
| Himawari-8 imagery | `noaa-himawari8` | us-east-1 | `arn:aws:s3:::noaa-himawari8` |
| Himawari-9 imagery | `noaa-himawari9` | us-east-1 | `arn:aws:s3:::noaa-himawari9` |

**Access (no AWS account required):**
```bash
aws s3 ls --no-sign-request s3://noaa-himawari9/
```

**SNS Notification Topics (push-based ingestion):**
- Himawari-8: `arn:aws:sns:us-east-1:123901341784:NewHimawari8Object`
- Himawari-9: `arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject`
- Supported protocols: **Lambda and SQS only** (no HTTP/email)

**Data products available:**
- AHI-L1b-FLDK: Full Disk -- updated every **10 minutes**
- Regions 1, 2, 3: updated every **2.5 minutes**
- Regions 4, 5 (Landmark): updated every **0.5 minutes**
- Archive back to July 2015

**S3 path structure:**
```
s3://noaa-himawari9/AHI-L1b-FLDK/{YYYY}/{MM}/{DD}/{HHMM}/
```

Files are in **Himawari Standard Data (HSD)** format -- a binary format with segments (10 segments per band for full disk).

**Latency:** Data appears in S3 within ~minutes of observation. HimawariCast (broadcast) expects ~16--17 min from observation start to all segments received. AWS mirror latency is similar.

### HimawariCast (DVB Satellite Broadcast)

- Broadcast-based dissemination via DVB-S2 satellite
- Requires a receive station with dish antenna pointed at the broadcast satellite
- Provides a subset of bands at reduced resolution (~4 km for most, ~2 km for one IR channel at night)
- Latency: ~16--17 minutes from observation start to complete reception of all segments
- Primarily designed for National Meteorological and Hydrological Services (NMHS) in the Asia-Pacific region

### HimawariCloud (Full Resolution -- Restricted)

- Full-resolution AHI data distribution system
- **Access restricted primarily to NMHS organizations**
- Requires institutional arrangement with JMA
- Not suitable as a primary source for a competition system unless partnership is established

### JAXA Himawari Monitor (P-Tree)

- URL: https://www.eorc.jaxa.jp/ptree/
- JAXA provides derived products from Himawari
- Free registration required
- Useful for validation and historical analysis, not lowest-latency operational use

### Australia NCI (National Computational Infrastructure)

- NCI hosts Himawari-AHI data including sensor geometry and brightness temperature products
- URL: https://opus.nci.org.au/ (search for Himawari-AHI)
- Pre-computed sensor zenith angle grids available (useful for view geometry corrections)
- Useful if processing is done on Australian compute infrastructure

## VIIRS (NOAA-20, NOAA-21, S-NPP)

### AWS Open Data (NODD) -- Push-Based Ingestion

**S3 Buckets:**

| Satellite | Bucket | ARN | SNS Topic ARN |
|-----------|--------|-----|---------------|
| NOAA-20 | `noaa-nesdis-n20-pds` | `arn:aws:s3:::noaa-nesdis-n20-pds` | `arn:aws:sns:us-east-1:709902155096:NewNOAA20Object` |
| NOAA-21 | `noaa-nesdis-n21-pds` | `arn:aws:s3:::noaa-nesdis-n21-pds` | `arn:aws:sns:us-east-1:709902155096:NewNOAA21Object` |
| Suomi NPP | `noaa-nesdis-snpp-pds` | `arn:aws:s3:::noaa-nesdis-snpp-pds` | `arn:aws:sns:us-east-1:709902155096:NewSNPPObject` |

All in **us-east-1**. No AWS account required for read access. SNS supports Lambda and SQS only.

**Access:**
```bash
aws s3 ls --no-sign-request s3://noaa-nesdis-n20-pds/
```

**Available products include:**
- SDR (Sensor Data Records) -- calibrated radiances
- EDR (Environmental Data Records) -- derived products
- Active fire products (AF/AFP) when available

**Latency considerations:**
- Upstream SDR production: ~80 minutes (worst case baseline)
- Cloud transfer overhead: < 1 second once data is generated
- Total latency from overpass to S3 availability: highly variable, depends on ground station contact and processing priority

### NASA FIRMS (Fire Information for Resource Management System)

**The most practical source for fire point detections.**

**Registration:** Request a free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/

**API Endpoints:**

```
# Area query (CSV output)
GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west},{south},{east},{north}/{DAY_RANGE}

# Area query with specific date
GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west},{south},{east},{north}/{DAY_RANGE}/{DATE}
```

**SOURCE values:**
| Source | Description |
|--------|-------------|
| `VIIRS_SNPP_NRT` | VIIRS on Suomi NPP, near real-time |
| `VIIRS_NOAA20_NRT` | VIIRS on NOAA-20, near real-time |
| `VIIRS_NOAA21_NRT` | VIIRS on NOAA-21, near real-time |
| `VIIRS_NOAA20_SP` | VIIRS on NOAA-20, standard processing |
| `VIIRS_SNPP_SP` | VIIRS on S-NPP, standard processing |
| `MODIS_NRT` | MODIS, near real-time |
| `MODIS_SP` | MODIS, standard processing |
| `LANDSAT_NRT` | Landsat fire product (US/Canada only) |

**Parameters:**
- `DAY_RANGE`: 1--5 days per query
- `DATE`: YYYY-MM-DD format (optional)
- Rate limit: 5,000 transactions per 10-minute interval

**Example: Query NSW for last 2 days of VIIRS NOAA-20 NRT:**
```bash
curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/YOUR_MAP_KEY/VIIRS_NOAA20_NRT/148,-37,154,-28/2"
```

**Latency tiers:**
| Tier | Latency | Availability |
|------|---------|-------------|
| URT (Ultra Real-Time) | < 5 minutes | US/Canada only (not Australia) |
| RT (Real-Time) | ~30 minutes | Regional |
| NRT (Near Real-Time) | ~3 hours | Global (including Australia) |

**Note:** URT is not available for Australia. For NSW, expect **NRT latency of ~3 hours** from FIRMS global processing. RT data when available could arrive in ~30 minutes.

RT and URT data are automatically removed when corresponding NRT detections are processed, or when RT/URT data is older than 6 hours.

**Output columns include:** latitude, longitude, brightness temperature (I4/I5 or B21/B31), scan/track pixel size, acquisition datetime, satellite, instrument, confidence, version, FRP, daynight flag.

### Direct Broadcast

If operating from Australia, a direct broadcast ground station could receive VIIRS data within ~5--15 minutes of overpass:
- Requires an X-band antenna and CSPP (Community Satellite Processing Package) software
- CSPP can produce SDR and active fire products locally
- BOM (Bureau of Meteorology) operates direct broadcast stations in Australia
- This is the lowest-latency path for LEO data over Australia, but requires significant infrastructure

## MODIS (Terra/Aqua)

### FIRMS API

Same API as VIIRS (see above). Use `MODIS_NRT` or `MODIS_SP` as SOURCE.

### NASA Earthdata / LAADS DAAC

- URL: https://ladsweb.modaps.eosdis.nasa.gov/
- MOD14 (Terra) and MYD14 (Aqua) fire products
- Level 2 swath products in HDF4 format
- Requires NASA Earthdata Login (free registration)
- Not lowest-latency; primarily for archive access and validation

### Direct Broadcast

MODIS direct broadcast via CSPP is also possible but less relevant given MODIS's declining status (Terra orbit drift, transition to VIIRS).

## Landsat 8/9

### USGS Earth Explorer

- URL: https://earthexplorer.usgs.gov/
- Registration required (free)
- Level-1 and Level-2 products
- Search by WRS-2 path/row or geographic coordinates
- Level-1 Real-Time products available **4--6 hours** after acquisition

### FIRMS Landsat Fire Product

- Available via FIRMS API using `LANDSAT_NRT` source
- **Currently US/Canada only** -- not available for Australia
- If expanded globally, would provide fire point detections at 30 m resolution

### AWS Open Data

Landsat Collection 2 data is available on AWS:
- Bucket: `usgs-landsat` (us-west-2)
- Path: `s3://usgs-landsat/collection02/level-2/standard/`
- No AWS account required for read access

### Google Earth Engine (GEE)

- Landsat data available as GEE image collections
- `LANDSAT/LC08/C02/T1_L2` (Landsat 8)
- `LANDSAT/LC09/C02/T1_L2` (Landsat 9)
- Processing can be done server-side in GEE
- Not suitable for real-time detection but useful for algorithm development and validation

## Sentinel-2 MSI

### Copernicus Data Space Ecosystem (CDSE)

**Primary access point for Sentinel-2 data since 2023.**

- URL: https://dataspace.copernicus.eu/
- STAC API: https://catalogue.dataspace.copernicus.eu/stac/
- Registration required (free)

**STAC API query example (Python):**
```python
from pystac_client import Client

catalog = Client.open("https://catalogue.dataspace.copernicus.eu/stac/")

results = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=[148, -37, 154, -28],  # NSW bounding box
    datetime="2026-04-01/2026-04-30",
    query={"eo:cloud_cover": {"lt": 30}}
)

items = list(results.items())
```

**Timeliness categories:**
| Category | Latency | Notes |
|----------|---------|-------|
| Nominal | 3--24 hours | Standard processing |
| NRT | 100 min -- 3 hours | Near real-time |
| RT | <= 100 min | Real-time (limited availability) |

### Sentinel Hub (Processing API)

- URL: https://www.sentinel-hub.com/
- OAuth2 authentication via CDSE credentials
- Server-side processing: request specific bands, indices, mosaics
- Evalscript system for custom processing
- Useful for computing NBR, SWIR fire indices without downloading full scenes
- Python library: `sentinelhub-py`

### Google Earth Engine

- Collection: `COPERNICUS/S2_SR_HARMONIZED`
- Server-side processing available
- Not real-time but excellent for development and validation

## Cross-Sensor Data Fusion Access Strategy

For the XPRIZE competition, the recommended data access priority:

1. **Himawari-9 via AWS NODD** (S3 + SNS push) -- continuous monitoring backbone, ~10 min cadence
2. **FIRMS API polling** (VIIRS NOAA-20/21/SNPP NRT) -- every 5--10 min poll for new fire points, ~3 h latency
3. **JPSS VIIRS SDR via AWS NODD** (S3 + SNS push) -- for custom fire detection processing on raw radiances when faster-than-FIRMS is needed
4. **Sentinel-2 via CDSE STAC** -- daily check for new scenes over active fire areas, confirmation and perimeter mapping
5. **Landsat via USGS/AWS** -- opportunistic; check for recent overpasses over detected fires for high-resolution characterization

## Licensing Summary

| Data Source | License | Cost | Key Restrictions |
|-------------|---------|------|-----------------|
| Himawari via NODD (AWS) | Open, attribution requested | Free | No implied endorsement |
| VIIRS/MODIS via NODD | Open, attribution requested | Free | No implied endorsement |
| FIRMS | Open access | Free | Rate limits (5000/10min), MAP_KEY required |
| Landsat | **Public domain** | Free | None |
| Sentinel-2 (Copernicus) | Open access (Copernicus terms) | Free | Attribution required |
| HimawariCloud (full res) | Restricted | Varies | Institutional agreement with JMA required |
